# ============================================
# FILE: generator/label_utils.py
# Meesho Label Cropper - PRINT SAFE FINAL
# ============================================

import fitz  # PyMuPDF


class MeeshoLabelCropper:
    """
    Crops Meesho shipping labels for 3-inch thermal printers
    - Completely removes TAX INVOICE
    - Prevents bottom cut during thermal printing
    - Keeps all borders, barcodes & order numbers safe
    """

    LABEL_WIDTH_PT = 216        # 3 inches @ 72 DPI
    LABEL_HEIGHT_PT = 360       # 5 inches max
    SAFETY_MARGIN = 6           # Prevents line clipping
    PRINT_SCALE_FIX = 0.96      # Shrinks content slightly (thermal-safe)
    BOTTOM_PADDING_PT = 10      # ~3.5mm bottom safety

    def __init__(self):
        self.labels_found = 0
        self.debug = True

    # --------------------------------------------------
    # Skip extra tax / terms pages
    # --------------------------------------------------
    def should_skip_page(self, page: fitz.Page) -> bool:
        text = page.get_text()

        skip_words = [
            "Tax is not payable on reverse charge",
            "This is a computer generated invoice",
            "logistics fee",
            "applicable to your order",
        ]

        has_skip = any(w in text for w in skip_words)
        has_customer = "Customer Address" in text

        return has_skip and not has_customer

    # --------------------------------------------------
    # Find crop Y ABOVE TAX INVOICE (text removed)
    # --------------------------------------------------
    def find_crop_point(self, page: fitz.Page) -> float:
        page_rect = page.rect

        tax_rects = page.search_for("TAX INVOICE")

        if tax_rects:
            tax_y = min(r.y0 for r in tax_rects)

            search_top = tax_y - 40
            search_bottom = tax_y - 6

            drawings = page.get_drawings()
            lines = []

            for drawing in drawings:
                for item in drawing.get("items", []):
                    if item[0] == "l":  # line
                        p1, p2 = item[1], item[2]

                        if abs(p1.y - p2.y) < 2:
                            if search_top < p1.y < search_bottom:
                                if abs(p2.x - p1.x) > page_rect.width * 0.7:
                                    lines.append(p1.y)

            if lines:
                line_y = max(lines)
                crop_y = line_y + 3  # keep line, remove text

                if self.debug:
                    print(f"  ✓ Border line at y={line_y:.1f}")
                    print(f"  ✓ TAX INVOICE removed, crop y={crop_y:.1f}")

                return crop_y

            # fallback if line not detected
            return tax_y - 8

        # Fallback: Product Details
        prod_rects = page.search_for("Product Details")
        if prod_rects:
            return min(r.y0 for r in prod_rects) + 80

        # Absolute fallback
        return page_rect.height * 0.5

    # --------------------------------------------------
    # Main PDF processing
    # --------------------------------------------------
    def create_label_pdf(self, pdf_file) -> bytes:

        if hasattr(pdf_file, "read"):
            pdf_bytes = pdf_file.read()
            pdf_file.seek(0)
            input_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        else:
            input_doc = fitz.open(pdf_file)

        output_pdf = fitz.open()

        if self.debug:
            print("\n" + "=" * 70)
            print(f"Processing {len(input_doc)} page(s)")
            print("=" * 70)

        for page_no in range(len(input_doc)):
            page = input_doc[page_no]

            if self.should_skip_page(page):
                if self.debug:
                    print("  ⚠ Skipped extra tax/terms page")
                continue

            crop_y = self.find_crop_point(page)
            if crop_y <= 0:
                continue

            # Safe clipping
            clip_rect = fitz.Rect(
                0,
                0,
                page.rect.width,
                crop_y + self.SAFETY_MARGIN
            )

            # 🔴 Thermal-safe scaling
            scale = (self.LABEL_WIDTH_PT / clip_rect.width) * self.PRINT_SCALE_FIX

            content_height = clip_rect.height * scale
            final_height = content_height + self.BOTTOM_PADDING_PT

            if final_height > self.LABEL_HEIGHT_PT:
                scale = (self.LABEL_HEIGHT_PT / clip_rect.height) * self.PRINT_SCALE_FIX
                content_height = clip_rect.height * scale
                final_height = self.LABEL_HEIGHT_PT

            final_width = clip_rect.width * scale

            new_page = output_pdf.new_page(
                width=final_width,
                height=final_height
            )

            # 🔴 CENTER content vertically (prevents bottom cut)
            y_offset = (final_height - content_height) / 2

            target_rect = fitz.Rect(
                0,
                y_offset,
                final_width,
                y_offset + content_height
            )

            new_page.show_pdf_page(
                target_rect,
                input_doc,
                page_no,
                clip=clip_rect
            )

            self.labels_found += 1

            if self.debug:
                print(
                    f"  ✓ Label size: "
                    f"{final_width/72:.2f} x {final_height/72:.2f} inch"
                )

        if self.labels_found == 0:
            input_doc.close()
            output_pdf.close()
            raise ValueError("No valid labels found")

        result = output_pdf.tobytes()

        if self.debug:
            print("\n✓ Labels created:", self.labels_found)

        input_doc.close()
        output_pdf.close()
        return result


# --------------------------------------------------
# Django helper
# --------------------------------------------------
def crop_meesho_labels_to_pdf(pdf_file) -> bytes:
    """
    Crop Meesho shipping labels for thermal printers
    (Print-safe, TAX INVOICE removed)
    """
    return MeeshoLabelCropper().create_label_pdf(pdf_file)
