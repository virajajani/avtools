# ============================================
# FILE: generator/label_utils.py
# Meesho Label Cropper - Final Fixed Version
# ============================================

import fitz  # PyMuPDF


class MeeshoLabelCropper:
    """
    Crops Meesho shipping labels for 3 inch width thermal paper
    Removes TAX INVOICE and extra pages
    """

    LABEL_WIDTH_PT = 216   # 3 inches at 72 DPI
    LABEL_HEIGHT_PT = 360  # 5 inches at 72 DPI (maximum)

    def __init__(self):
        self.labels_found = 0
        self.debug = True

    def should_skip_page(self, page: fitz.Page) -> bool:
        """
        Check if this page should be skipped (extra terms/tax page)
        Returns True if page should be skipped
        """
        text = page.get_text()
        
        # Skip pages that have these indicators of extra content
        skip_indicators = [
            "Tax is not payable on reverse charge",
            "This is a computer generated invoice",
            "applicable to your order",
            "logistics fee"
        ]
        
        # If page has these terms but no Customer Address, it's an extra page
        has_skip_text = any(indicator in text for indicator in skip_indicators)
        has_customer = "Customer Address" in text
        
        if has_skip_text and not has_customer:
            return True
        
        return False

    def find_crop_point(self, page: fitz.Page) -> float:
        """
        Find where to crop - before TAX INVOICE text
        Returns Y coordinate
        """
        page_rect = page.rect
        
        # Method 1: Search for "TAX INVOICE" text directly
        tax_invoice_rects = page.search_for("TAX INVOICE")
        
        if tax_invoice_rects:
            # Get the topmost TAX INVOICE occurrence
            tax_y = min(rect.y0 for rect in tax_invoice_rects)
            
            # Look for horizontal line ABOVE TAX INVOICE (within 5-30 pixels)
            search_start = tax_y - 30
            search_end = tax_y - 3
            
            drawings = page.get_drawings()
            lines_above = []
            
            for drawing in drawings:
                for item in drawing.get("items", []):
                    if item[0] == "l":  # line
                        p1, p2 = item[1], item[2]
                        line_y = p1.y
                        
                        # Check if horizontal line above TAX INVOICE
                        if abs(p1.y - p2.y) < 3 and search_start < line_y < search_end:
                            line_width = abs(p2.x - p1.x)
                            if line_width > page_rect.width * 0.7:
                                lines_above.append(line_y)
            
            if lines_above:
                # Get the line closest to TAX INVOICE
                line_y = max(lines_above)
                # Crop AFTER this line to include it
                crop_y = line_y + 3
                
                if self.debug:
                    print(f"  ✓ Found 'TAX INVOICE' at y = {tax_y:.1f}")
                    print(f"  ✓ Found border line at y = {line_y:.1f}")
                    print(f"  ✓ Cropping at y = {crop_y:.1f} (including line)")
                
                return crop_y
            
            # No line found, crop slightly above TAX INVOICE
            crop_y = tax_y - 5
            
            if self.debug:
                print(f"  ✓ Found 'TAX INVOICE' at y = {tax_y:.1f}")
                print(f"  ⚠ No border line found, cropping at y = {crop_y:.1f}")
            
            return crop_y
        
        # Method 2: If no TAX INVOICE found, look for Product Details
        product_details_rects = page.search_for("Product Details")
        
        if product_details_rects:
            product_y = min(rect.y0 for rect in product_details_rects)
            crop_y = product_y + 80  # Fixed offset
            
            if self.debug:
                print(f"  ✓ Found 'Product Details' at y = {product_y:.1f}")
                print(f"  ⚠ No TAX INVOICE, using offset, cropping at y = {crop_y:.1f}")
            
            return crop_y
        
        # Fallback
        crop_y = page_rect.height * 0.50
        if self.debug:
            print(f"  ⚠ Using default crop at y = {crop_y:.1f}")
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
            print(f"Target width: 3 inch ({self.LABEL_WIDTH_PT} pt)")
            print(f"{'='*70}")
        
        output_pdf = fitz.open()
        
        # Process each page
        for page_num in range(len(input_doc)):
            source_page = input_doc[page_num]
            
            if self.debug:
                print(f"\nPage {page_num + 1}:")
            
            # Check if this page should be skipped
            if self.should_skip_page(source_page):
                if self.debug:
                    print(f"  ⚠ Skipping extra page (tax/terms content)")
                continue
            
            page_rect = source_page.rect
            
            if self.debug:
                print(f"  Original: {page_rect.width:.1f} x {page_rect.height:.1f} pt")
            
            # Find crop point
            crop_y = self.find_crop_point(source_page)
            
            if crop_y <= 0:
                if self.debug:
                    print(f"  ⚠ Invalid crop point, skipping page")
                continue
            
            # Define crop area
            clip_rect = fitz.Rect(0, 0, page_rect.width, crop_y)
            
            if self.debug:
                print(f"  Cropped area: {clip_rect.width:.1f} x {clip_rect.height:.1f} pt")
            
            # Scale to fit 3 inch width (fill the width completely)
            scale = self.LABEL_WIDTH_PT / clip_rect.width
            
            final_width = self.LABEL_WIDTH_PT  # Always use full 3 inches
            final_height = clip_rect.height * scale
            
            # If height exceeds 5 inches, scale down to fit
            if final_height > self.LABEL_HEIGHT_PT:
                scale = self.LABEL_HEIGHT_PT / clip_rect.height
                final_width = clip_rect.width * scale
                final_height = self.LABEL_HEIGHT_PT
            
            # Create new page with actual content size (no fixed 5 inch)
            new_page = output_pdf.new_page(
                width=final_width,
                height=final_height
            )
            
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
                print(f"  Scale: {scale:.3f}x")
                print(f"  Final: {final_width:.1f} x {final_height:.1f} pt ({final_width/72:.2f} x {final_height/72:.2f} in)")
        
        if self.debug:
            print(f"\n{'='*70}")
            print(f"✓ Created {self.labels_found} label(s)")
            print(f"{'='*70}\n")
        
        if self.labels_found == 0:
            output_pdf.close()
            input_doc.close()
            raise ValueError("No valid labels found in PDF")
        
        pdf_bytes = output_pdf.tobytes()
        
        if self.debug:
            print(f"Output PDF size: {len(pdf_bytes):,} bytes\n")
        
        output_pdf.close()
        input_doc.close()
        
        return pdf_bytes


def crop_meesho_labels_to_pdf(pdf_file) -> bytes:
    """
    Crop Meesho labels for 3 inch thermal paper
    Removes TAX INVOICE sections and extra pages
    
    Args:
        pdf_file: Django UploadedFile or file path
    
    Returns:
        bytes: Cropped PDF as bytes
    """
    cropper = MeeshoLabelCropper()
    return cropper.create_label_pdf(pdf_file)