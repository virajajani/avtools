# ============================================
# FILE: generator/label_utils.py
# Meesho Shipping Label Crop Tool - PDF Output
# ============================================

import io
import fitz  # PyMuPDF
import cv2
import numpy as np
from typing import List, Tuple
from PIL import Image


class MeeshoLabelCropper:
    """
    Crops Meesho shipping labels from PDF and outputs as PDF
    Standard Meesho label size: 4x6 inches (10.16 x 15.24 cm)
    """
    
    # Standard label dimensions in points (72 points = 1 inch)
    LABEL_WIDTH_PT = 288   # 4 inches * 72
    LABEL_HEIGHT_PT = 432  # 6 inches * 72
    
    # Detection parameters
    MIN_LABEL_AREA = 500000
    BORDER_MARGIN = 20
    
    def __init__(self):
        self.labels_found = 0
    
    def pdf_to_images(self, pdf_file) -> List[Tuple[np.ndarray, fitz.Page]]:
        """
        Convert PDF pages to images while keeping page references
        
        Args:
            pdf_file: Django UploadedFile object or file path
            
        Returns:
            List of tuples (numpy array image, fitz page object)
        """
        images = []
        
        # Handle Django UploadedFile
        if hasattr(pdf_file, 'read'):
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        else:
            doc = fitz.open(pdf_file)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Render page to image at 300 DPI for detection
            mat = fitz.Matrix(300/72, 300/72)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to numpy array
            img = np.frombuffer(pix.samples, dtype=np.uint8)
            img = img.reshape(pix.height, pix.width, pix.n)
            
            # Convert RGBA to RGB if needed
            if pix.n == 4:
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
            
            images.append((img, page))
        
        return images, doc
    
    def detect_labels(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """
        Detect label boundaries in image
        
        Args:
            image: Input image as numpy array
            
        Returns:
            List of bounding boxes (x, y, width, height)
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        # Apply Gaussian blur
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Edge detection
        edges = cv2.Canny(blurred, 50, 150)
        
        # Dilate edges
        kernel = np.ones((5, 5), np.uint8)
        dilated = cv2.dilate(edges, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(
            dilated, 
            cv2.RETR_EXTERNAL, 
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        labels = []
        
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w * h
            
            if area > self.MIN_LABEL_AREA:
                aspect_ratio = h / w if w > 0 else 0
                
                # Meesho labels are typically 4:6 ratio
                if 0.5 < aspect_ratio < 0.8 or 1.2 < aspect_ratio < 2.0:
                    labels.append((x, y, w, h))
        
        # Sort by position
        labels.sort(key=lambda box: (box[1], box[0]))
        
        return labels
    
    def create_label_pdf(self, pdf_file) -> bytes:
        """
        Process PDF and create new PDF with cropped labels
        
        Args:
            pdf_file: Input PDF file
            
        Returns:
            PDF bytes
        """
        images_and_pages, input_doc = self.pdf_to_images(pdf_file)
        
        # Create new PDF document
        output_pdf = fitz.open()
        
        for page_num, (image, original_page) in enumerate(images_and_pages):
            # Detect labels on this page
            labels = self.detect_labels(image)
            
            if not labels:
                # If no labels detected, use entire page
                h, w = image.shape[:2]
                labels = [(0, 0, w, h)]
            
            # Process each detected label
            for label_idx, bbox in enumerate(labels):
                x, y, w, h = bbox
                
                # Add margins
                x = max(0, x - self.BORDER_MARGIN)
                y = max(0, y - self.BORDER_MARGIN)
                w = min(image.shape[1] - x, w + 2 * self.BORDER_MARGIN)
                h = min(image.shape[0] - y, h + 2 * self.BORDER_MARGIN)
                
                # Convert pixel coordinates to points (300 DPI to 72 DPI)
                scale = 72 / 300
                rect = fitz.Rect(
                    x * scale,
                    y * scale,
                    (x + w) * scale,
                    (y + h) * scale
                )
                
                # Create new page with standard label size
                new_page = output_pdf.new_page(
                    width=self.LABEL_WIDTH_PT,
                    height=self.LABEL_HEIGHT_PT
                )
                
                # Copy the cropped area from original page
                new_page.show_pdf_page(
                    new_page.rect,
                    input_doc,
                    page_num,
                    clip=rect
                )
                
                self.labels_found += 1
        
        # Get PDF bytes
        pdf_bytes = output_pdf.tobytes()
        
        # Clean up
        output_pdf.close()
        input_doc.close()
        
        return pdf_bytes


def crop_meesho_labels_to_pdf(pdf_file) -> bytes:
    """
    Main function to crop Meesho labels and return as PDF
    
    Args:
        pdf_file: Uploaded PDF file
        
    Returns:
        PDF bytes with cropped labels
    """
    cropper = MeeshoLabelCropper()
    pdf_bytes = cropper.create_label_pdf(pdf_file)
    return pdf_bytes

