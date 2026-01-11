# ============================================
# FILE: generator/label_utils.py
# Meesho Label Cropper - 3x5 inch format
# ============================================

import fitz  # PyMuPDF


class MeeshoLabelCropper:
    """
    Crops Meesho shipping labels for 3x5 inch thermal paper
    Removes everything from TAX INVOICE onwards
    Scales to fit 3x5 inch (216 x 360 pt)
    """

    LABEL_WIDTH_PT = 216   # 3 inches at 72 DPI
    LABEL_HEIGHT_PT = 360  # 5 inches at 72 DPI

    def __init__(self):
        self.labels_found = 0
        self.debug = True

    def find_crop_point(self, page: fitz.Page) -> float:
        """
        Find where to crop - include Product Details with bottom border
        Returns Y coordinate
        """
        page_rect = page.rect
        
        # Search for "TAX INVOICE" text
        tax_invoice_rects = page.search_for("TAX INVOICE")
        
        if tax_invoice_rects:
            tax_y = min(rect.y0 for rect in tax_invoice_rects)
            
            if self.debug:
                print(f"  ✓ Found 'TAX INVOICE' at y = {tax_y:.1f}")
            
            # Look for "Product Details" text
            product_details_rects = page.search_for("Product Details")
            
            if product_details_rects:
                # Get the bottom of Product Details section
                product_y = max(rect.y1 for rect in product_details_rects)
                
                # Search for horizontal lines after Product Details but before TAX INVOICE
                search_start = product_y
                search_end = tax_y
                
                drawings = page.get_drawings()
                lines_found = []
                
                for drawing in drawings:
                    for item in drawing.get("items", []):
                        if item[0] == "l":  # line
                            p1, p2 = item[1], item[2]
                            line_y = p1.y
                            
                            # Check if horizontal line between Product Details and TAX INVOICE
                            if abs(p1.y - p2.y) < 3 and search_start < line_y < search_end:
                                line_width = abs(p2.x - p1.x)
                                if line_width > page_rect.width * 0.4:
                                    lines_found.append(line_y)
                
                if lines_found:
                    # Get the last line (closest to TAX INVOICE)
                    line_y = max(lines_found)
                    crop_y = line_y + 5  # Include the line with margin
                    if self.debug:
                        print(f"  ✓ Found Product Details border at y = {line_y:.1f}")
                        print(f"  ✓ Cropping at y = {crop_y:.1f}")
                    return crop_y
                else:
                    # No line found, add margin after Product Details text
                    crop_y = product_y + 60
                    if self.debug:
                        print(f"  ⚠ No border line, cropping at y = {crop_y:.1f}")
                    return crop_y
            
            # Fallback: crop before TAX INVOICE
            crop_y = tax_y - 15
            if self.debug:
                print(f"  ⚠ Using fallback, cropping at y = {crop_y:.1f}")
            return crop_y
        
        # Last fallback
        crop_y = page_rect.height * 0.55
        if self.debug:
            print(f"  ⚠ Using default crop at y = {crop_y:.1f}")
        return crop_y

    def create_label_pdf(self, pdf_file) -> bytes:
        """Create PDF with cropped and scaled labels for 3x5 inch paper"""
        
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
            print(f"Target size: 3x5 inch ({self.LABEL_WIDTH_PT} x {self.LABEL_HEIGHT_PT} pt)")
            print(f"{'='*70}")
        
        output_pdf = fitz.open()
        
        # Process each page
        for page_num in range(len(input_doc)):
            source_page = input_doc[page_num]
            page_rect = source_page.rect
            
            if self.debug:
                print(f"\nPage {page_num + 1}:")
                print(f"  Original: {page_rect.width:.1f} x {page_rect.height:.1f} pt")
            
            # Find crop point (where to stop)
            crop_y = self.find_crop_point(source_page)
            
            # Define the area to crop (from top to crop point)
            clip_rect = fitz.Rect(0, 0, page_rect.width, crop_y)
            
            if self.debug:
                print(f"  Cropped area: {clip_rect.width:.1f} x {clip_rect.height:.1f} pt")
            
            # Create new page at 3 inch width, but with actual content height (no fixed 5 inch)
            # Scale to 3 inch width
            scale = self.LABEL_WIDTH_PT / clip_rect.width
            final_width = self.LABEL_WIDTH_PT
            final_height = clip_rect.height * scale
            
            # Create page with actual content size (no white space)
            new_page = output_pdf.new_page(
                width=final_width,
                height=final_height
            )
            
            target_rect = fitz.Rect(0, 0, final_width, final_height)
            
            if self.debug:
                print(f"  Scale factor: {scale:.3f}x")
                print(f"  Final page: {final_width:.1f} x {final_height:.1f} pt")
                print(f"  ({final_width/72:.2f} x {final_height/72:.2f} inches)")
            
            # Copy the content
            new_page.show_pdf_page(
                target_rect,
                input_doc,
                page_num,
                clip=clip_rect
            )
            
            self.labels_found += 1
        
        if self.debug:
            print(f"\n{'='*70}")
            print(f"✓ Created {self.labels_found} label(s) for 3x5 inch paper")
            print(f"{'='*70}\n")
        
        if self.labels_found == 0:
            output_pdf.close()
            input_doc.close()
            raise ValueError("No labels found in PDF")
        
        pdf_bytes = output_pdf.tobytes()
        
        if self.debug:
            print(f"Output PDF size: {len(pdf_bytes):,} bytes\n")
        
        output_pdf.close()
        input_doc.close()
        
        return pdf_bytes


def crop_meesho_labels_to_pdf(pdf_file) -> bytes:
    """
    Crop and resize Meesho labels for 3x5 inch thermal paper
    
    Args:
        pdf_file: Django UploadedFile or file path
    
    Returns:
        bytes: PDF formatted for 3x5 inch paper
    """
    cropper = MeeshoLabelCropper()
    return cropper.create_label_pdf(pdf_file)