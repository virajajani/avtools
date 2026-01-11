# ============================================
# FILE: generator/label_utils.py
# Meesho Label Cropper - Crop and Resize
# ============================================

import fitz  # PyMuPDF


class MeeshoLabelCropper:
    """
    Crops Meesho shipping labels from PDF
    Removes everything from "TAX INVOICE" onwards
    Resizes to standard 4x6 inch if needed
    """

    LABEL_WIDTH_PT = 288   # 4 inches at 72 DPI
    LABEL_HEIGHT_PT = 432  # 6 inches at 72 DPI
    MAX_HEIGHT_PT = 500    # Maximum height before resizing

    def __init__(self):
        self.labels_found = 0
        self.debug = True

    def find_crop_point(self, page: fitz.Page) -> float:
        """
        Find where to crop - at the line above TAX INVOICE
        Returns Y coordinate
        """
        page_rect = page.rect
        
        # Search for "TAX INVOICE" text
        tax_invoice_rects = page.search_for("TAX INVOICE")
        
        if tax_invoice_rects:
            # Get the topmost occurrence of TAX INVOICE
            tax_y = min(rect.y0 for rect in tax_invoice_rects)
            
            if self.debug:
                print(f"  ✓ Found 'TAX INVOICE' at y = {tax_y:.1f}")
            
            # Look for horizontal line above TAX INVOICE
            # Search in the area 20-50 pixels above the text
            search_start = tax_y - 50
            search_end = tax_y - 5
            
            drawings = page.get_drawings()
            lines_found = []
            
            for drawing in drawings:
                for item in drawing.get("items", []):
                    if item[0] == "l":  # line
                        p1, p2 = item[1], item[2]
                        line_y = p1.y
                        
                        # Check if it's a horizontal line in our search area
                        if abs(p1.y - p2.y) < 3 and search_start < line_y < search_end:
                            # Check if line spans significant width
                            line_width = abs(p2.x - p1.x)
                            if line_width > page_rect.width * 0.5:
                                lines_found.append(line_y)
            
            if lines_found:
                # Get the line closest to TAX INVOICE
                line_y = max(lines_found)
                # Add small margin to include the line itself
                crop_y = line_y + 3
                if self.debug:
                    print(f"  ✓ Found separator line at y = {line_y:.1f}")
                    print(f"  ✓ Cropping at y = {crop_y:.1f} (including line)")
                return crop_y
            
            # No line found, use position just above TAX INVOICE
            crop_y = tax_y - 15
            if self.debug:
                print(f"  ⚠ No line found, cropping at y = {crop_y:.1f}")
            return crop_y
        
        # Fallback: 55% of page height
        crop_y = page_rect.height * 0.55
        if self.debug:
            print(f"  ⚠ Using default: 55% of page = {crop_y:.1f}")
        
        return crop_y

    def create_label_pdf(self, pdf_file) -> bytes:
        """Create PDF with cropped labels"""
        
        # Open input PDF
        if hasattr(pdf_file, 'read'):
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            input_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        else:
            input_doc = fitz.open(pdf_file)
        
        if self.debug:
            print(f"\n{'='*70}")
            print(f"Processing PDF: {len(input_doc)} page(s)")
            print(f"{'='*70}")
        
        # Create output PDF
        output_pdf = fitz.open()
        
        # Process each page
        for page_num in range(len(input_doc)):
            source_page = input_doc[page_num]
            page_rect = source_page.rect
            
            if self.debug:
                print(f"\nPage {page_num + 1}:")
                print(f"  Original size: {page_rect.width:.1f} x {page_rect.height:.1f} pt")
            
            # Find where to crop
            crop_y = self.find_crop_point(source_page)
            
            # Calculate cropped dimensions
            cropped_width = page_rect.width
            cropped_height = crop_y
            
            if self.debug:
                print(f"  Cropped size: {cropped_width:.1f} x {cropped_height:.1f} pt")
            
            # Decide if we need to resize
            needs_resize = cropped_height > self.MAX_HEIGHT_PT
            
            if needs_resize:
                # Resize to fit 4x6 inch label
                final_width = self.LABEL_WIDTH_PT
                final_height = self.LABEL_HEIGHT_PT
                
                if self.debug:
                    print(f"  ⚠ Too large! Resizing to: {final_width:.1f} x {final_height:.1f} pt (4x6 inch)")
            else:
                # Keep original cropped size
                final_width = cropped_width
                final_height = cropped_height
                
                if self.debug:
                    print(f"  ✓ Size OK, keeping original dimensions")
            
            # Create new page
            new_page = output_pdf.new_page(
                width=final_width,
                height=final_height
            )
            
            # Define the area to copy (from top to crop point)
            clip_rect = fitz.Rect(0, 0, cropped_width, crop_y)
            
            # Define where to place it (full new page)
            target_rect = fitz.Rect(0, 0, final_width, final_height)
            
            # Copy content
            new_page.show_pdf_page(
                target_rect,
                input_doc,
                page_num,
                clip=clip_rect
            )
            
            self.labels_found += 1
        
        if self.debug:
            print(f"\n{'='*70}")
            print(f"✓ Processed {self.labels_found} label(s)")
            print(f"{'='*70}\n")
        
        if self.labels_found == 0:
            output_pdf.close()
            input_doc.close()
            raise ValueError("No labels found in PDF")
        
        # Convert to bytes
        pdf_bytes = output_pdf.tobytes()
        
        if self.debug:
            print(f"Output PDF size: {len(pdf_bytes):,} bytes\n")
        
        # Close documents
        output_pdf.close()
        input_doc.close()
        
        return pdf_bytes


def crop_meesho_labels_to_pdf(pdf_file) -> bytes:
    """
    Crop Meesho labels - remove TAX INVOICE section
    Resize to 4x6 inch if label is too large
    
    Args:
        pdf_file: Django UploadedFile or file path
    
    Returns:
        bytes: Cropped PDF as bytes
    """
    cropper = MeeshoLabelCropper()
    return cropper.create_label_pdf(pdf_file)