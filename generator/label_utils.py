# # ============================================
# # FILE: generator/label_utils.py
# # Meesho Label Cropper - PRINT SAFE FINAL
# # ============================================

# import fitz  # PyMuPDF


# class MeeshoLabelCropper:
#     """
#     Crops Meesho shipping labels for 3-inch thermal printers
#     - Completely removes TAX INVOICE
#     - Prevents bottom cut during thermal printing
#     - Keeps all borders, barcodes & order numbers safe
#     """

#     LABEL_WIDTH_PT = 216        # 3 inches @ 72 DPI
#     LABEL_HEIGHT_PT = 360       # 5 inches max
#     SAFETY_MARGIN = 6           # Prevents line clipping
#     PRINT_SCALE_FIX = 0.96      # Shrinks content slightly (thermal-safe)
#     BOTTOM_PADDING_PT = 10      # ~3.5mm bottom safety

#     def __init__(self):
#         self.labels_found = 0
#         self.debug = True

#     # --------------------------------------------------
#     # Skip extra tax / terms pages
#     # --------------------------------------------------
#     def should_skip_page(self, page: fitz.Page) -> bool:
#         text = page.get_text()

#         skip_words = [
#             "Tax is not payable on reverse charge",
#             "This is a computer generated invoice",
#             "logistics fee",
#             "applicable to your order",
#         ]

#         has_skip = any(w in text for w in skip_words)
#         has_customer = "Customer Address" in text

#         return has_skip and not has_customer

#     # --------------------------------------------------
#     # Find crop Y ABOVE TAX INVOICE (text removed)
#     # --------------------------------------------------
#     def find_crop_point(self, page: fitz.Page) -> float:
#         page_rect = page.rect

#         tax_rects = page.search_for("TAX INVOICE")

#         if tax_rects:
#             tax_y = min(r.y0 for r in tax_rects)

#             search_top = tax_y - 40
#             search_bottom = tax_y - 6

#             drawings = page.get_drawings()
#             lines = []

#             for drawing in drawings:
#                 for item in drawing.get("items", []):
#                     if item[0] == "l":  # line
#                         p1, p2 = item[1], item[2]

#                         if abs(p1.y - p2.y) < 2:
#                             if search_top < p1.y < search_bottom:
#                                 if abs(p2.x - p1.x) > page_rect.width * 0.7:
#                                     lines.append(p1.y)

#             if lines:
#                 line_y = max(lines)
#                 crop_y = line_y + 3  # keep line, remove text

#                 if self.debug:
#                     print(f"  ✓ Border line at y={line_y:.1f}")
#                     print(f"  ✓ TAX INVOICE removed, crop y={crop_y:.1f}")

#                 return crop_y

#             # fallback if line not detected
#             return tax_y - 8

#         # Fallback: Product Details
#         prod_rects = page.search_for("Product Details")
#         if prod_rects:
#             return min(r.y0 for r in prod_rects) + 80

#         # Absolute fallback
#         return page_rect.height * 0.5

#     # --------------------------------------------------
#     # Main PDF processing
#     # --------------------------------------------------
#     def create_label_pdf(self, pdf_file) -> bytes:

#         if hasattr(pdf_file, "read"):
#             pdf_bytes = pdf_file.read()
#             pdf_file.seek(0)
#             input_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
#         else:
#             input_doc = fitz.open(pdf_file)

#         output_pdf = fitz.open()

#         if self.debug:
#             print("\n" + "=" * 70)
#             print(f"Processing {len(input_doc)} page(s)")
#             print("=" * 70)

#         for page_no in range(len(input_doc)):
#             page = input_doc[page_no]

#             if self.should_skip_page(page):
#                 if self.debug:
#                     print("  ⚠ Skipped extra tax/terms page")
#                 continue

#             crop_y = self.find_crop_point(page)
#             if crop_y <= 0:
#                 continue

#             # Safe clipping
#             clip_rect = fitz.Rect(
#                 0,
#                 0,
#                 page.rect.width,
#                 crop_y + self.SAFETY_MARGIN
#             )

#             # 🔴 Thermal-safe scaling
#             scale = (self.LABEL_WIDTH_PT / clip_rect.width) * self.PRINT_SCALE_FIX

#             content_height = clip_rect.height * scale
#             final_height = content_height + self.BOTTOM_PADDING_PT

#             if final_height > self.LABEL_HEIGHT_PT:
#                 scale = (self.LABEL_HEIGHT_PT / clip_rect.height) * self.PRINT_SCALE_FIX
#                 content_height = clip_rect.height * scale
#                 final_height = self.LABEL_HEIGHT_PT

#             final_width = clip_rect.width * scale

#             new_page = output_pdf.new_page(
#                 width=final_width,
#                 height=final_height
#             )

#             # 🔴 CENTER content vertically (prevents bottom cut)
#             y_offset = (final_height - content_height) / 2

#             target_rect = fitz.Rect(
#                 0,
#                 y_offset,
#                 final_width,
#                 y_offset + content_height
#             )

#             new_page.show_pdf_page(
#                 target_rect,
#                 input_doc,
#                 page_no,
#                 clip=clip_rect
#             )

#             self.labels_found += 1

#             if self.debug:
#                 print(
#                     f"  ✓ Label size: "
#                     f"{final_width/72:.2f} x {final_height/72:.2f} inch"
#                 )

#         if self.labels_found == 0:
#             input_doc.close()
#             output_pdf.close()
#             raise ValueError("No valid labels found")

#         result = output_pdf.tobytes()

#         if self.debug:
#             print("\n✓ Labels created:", self.labels_found)

#         input_doc.close()
#         output_pdf.close()
#         return result


# # --------------------------------------------------
# # Django helper
# # --------------------------------------------------
# def crop_meesho_labels_to_pdf(pdf_file) -> bytes:
#     """
#     Crop Meesho shipping labels for thermal printers
#     (Print-safe, TAX INVOICE removed)
#     """
#     return MeeshoLabelCropper().create_label_pdf(pdf_file)

# # ============================================
# # FILE: generator/label_utils.py
# # Meesho Label Cropper - PRINT SAFE FINAL
# # ============================================

# import fitz  # PyMuPDF
# import re
# from collections import defaultdict


# class MeeshoLabelCropper:
#     """
#     Crops Meesho shipping labels for 3-inch thermal printers
#     - Completely removes TAX INVOICE
#     - Prevents bottom cut during thermal printing
#     - Keeps all borders, barcodes & order numbers safe
#     """

#     LABEL_WIDTH_PT = 216        # 3 inches @ 72 DPI
#     LABEL_HEIGHT_PT = 360       # 5 inches max
#     SAFETY_MARGIN = 6           # Prevents line clipping
#     PRINT_SCALE_FIX = 0.96      # Shrinks content slightly (thermal-safe)
#     BOTTOM_PADDING_PT = 10      # ~3.5mm bottom safety

#     def __init__(self):
#         self.labels_found = 0
#         self.debug = True

#     # --------------------------------------------------
#     # Skip extra tax / terms pages
#     # --------------------------------------------------
#     def should_skip_page(self, page: fitz.Page) -> bool:

#         text = page.get_text()

#         skip_words = [

#             "Tax is not payable on reverse charge",

#             "This is a computer generated invoice",

#             "logistics fee",

#             "applicable to your order",

#         ]

#         has_skip = any(
#             w in text for w in skip_words
#         )

#         has_customer = (
#             "Customer Address" in text
#         )

#         return has_skip and not has_customer

#     # --------------------------------------------------
#     # Detect courier partner
#     # --------------------------------------------------
#     def get_courier_name(self, page: fitz.Page) -> str:

#         text = page.get_text().lower()

#         courier_list = [

#             "delhivery",

#             "valmo",

#             "shadowfax",

#             "xpressbees",

#             "ecom express",

#             "ekart",

#         ]

#         for courier in courier_list:

#             if courier in text:

#                 return courier.title()

#         return "Unknown"

#     # --------------------------------------------------
#     # Extract product name / SKU
#     # --------------------------------------------------
#     def get_product_name(self, page: fitz.Page) -> str:

#         text = page.get_text()

#         # ---------------------------------------------
#         # CLEAN LINES
#         # ---------------------------------------------
#         lines = [

#             line.strip()

#             for line in text.splitlines()

#             if line.strip()

#         ]

#         # ---------------------------------------------
#         # FIND PRODUCT AFTER SKU
#         # ---------------------------------------------
#         for i, line in enumerate(lines):

#             if line.lower() == "sku":

#                 # Check next few lines
#                 for j in range(
#                     i + 1,
#                     min(i + 6, len(lines))
#                 ):

#                     candidate = (
#                         lines[j].strip()
#                     )

#                     # Skip invalid words
#                     skip_words = [

#                         "size",

#                         "qty",

#                         "color",

#                         "free size",

#                         "pink",

#                         "order no.",

#                         "order no",

#                         "order",

#                     ]

#                     if (
#                         candidate.lower()
#                         in skip_words
#                     ):
#                         continue

#                     # Skip small words
#                     if len(candidate) < 4:
#                         continue

#                     return candidate

#         # ---------------------------------------------
#         # FALLBACK REGEX
#         # ---------------------------------------------
#         match = re.search(

#             r"(\d+\s+[A-Za-z0-9\s\-]+)",

#             text,

#             re.IGNORECASE

#         )

#         if match:

#             value = (
#                 match.group(1).strip()
#             )

#             if value.lower() != "size":

#                 return value

#         return "Unknown Product"

#     # --------------------------------------------------
#     # Find crop Y ABOVE TAX INVOICE
#     # --------------------------------------------------
#     def find_crop_point(
#         self,
#         page: fitz.Page
#     ) -> float:

#         page_rect = page.rect

#         tax_rects = page.search_for(
#             "TAX INVOICE"
#         )

#         if tax_rects:

#             tax_y = min(
#                 r.y0 for r in tax_rects
#             )

#             search_top = tax_y - 40

#             search_bottom = tax_y - 6

#             drawings = page.get_drawings()

#             lines = []

#             for drawing in drawings:

#                 for item in drawing.get(
#                     "items", []
#                 ):

#                     if item[0] == "l":

#                         p1, p2 = (
#                             item[1],
#                             item[2]
#                         )

#                         # Horizontal line
#                         if abs(
#                             p1.y - p2.y
#                         ) < 2:

#                             if (
#                                 search_top
#                                 < p1.y
#                                 < search_bottom
#                             ):

#                                 if abs(
#                                     p2.x - p1.x
#                                 ) > (
#                                     page_rect.width
#                                     * 0.7
#                                 ):

#                                     lines.append(
#                                         p1.y
#                                     )

#             if lines:

#                 line_y = max(lines)

#                 crop_y = line_y + 3

#                 if self.debug:

#                     print(
#                         f"  ✓ Border line at y={line_y:.1f}"
#                     )

#                     print(
#                         f"  ✓ TAX INVOICE removed, crop y={crop_y:.1f}"
#                     )

#                 return crop_y

#             return tax_y - 8

#         # fallback
#         prod_rects = page.search_for(
#             "Product Details"
#         )

#         if prod_rects:

#             return (
#                 min(r.y0 for r in prod_rects)
#                 + 80
#             )

#         return page_rect.height * 0.5

#     # --------------------------------------------------
#     # Main PDF processing
#     # --------------------------------------------------
#     def create_label_pdf(self, pdf_file):

#         # ---------------------------------------------
#         # Open PDF
#         # ---------------------------------------------
#         if hasattr(pdf_file, "read"):

#             pdf_bytes = pdf_file.read()

#             pdf_file.seek(0)

#             input_doc = fitz.open(
#                 stream=pdf_bytes,
#                 filetype="pdf"
#             )

#         else:

#             input_doc = fitz.open(pdf_file)

#         output_pdf = fitz.open()

#         # ---------------------------------------------
#         # SUMMARY
#         # ---------------------------------------------
#         product_summary = defaultdict(
#             lambda: defaultdict(int)
#         )

#         grouped_labels = defaultdict(list)

#         if self.debug:

#             print("\n" + "=" * 70)

#             print(
#                 f"Processing {len(input_doc)} page(s)"
#             )

#             print("=" * 70)

#         # ---------------------------------------------
#         # FIRST PASS
#         # ---------------------------------------------
#         for page_no in range(len(input_doc)):

#             page = input_doc[page_no]

#             # Skip extra pages
#             if self.should_skip_page(page):

#                 if self.debug:

#                     print(
#                         "  ⚠ Skipped extra tax/terms page"
#                     )

#                 continue

#             # Courier
#             courier = self.get_courier_name(page)

#             # Product
#             product = self.get_product_name(page)

#             # Store grouped labels
#             grouped_labels[courier].append({

#                 "product": product,

#                 "page_no": page_no,

#             })

#             # Summary count
#             product_summary[courier][product] += 1

#         # ---------------------------------------------
#         # SECOND PASS
#         # ---------------------------------------------
#         for courier in sorted(
#             grouped_labels.keys()
#         ):

#             if self.debug:

#                 print(
#                     f"\n📦 Courier Group: {courier}"
#                 )

#             # Sort product-wise
#             sorted_labels = sorted(

#                 grouped_labels[courier],

#                 key=lambda x: x["product"]

#             )

#             for item in sorted_labels:

#                 page_no = item["page_no"]

#                 product = item["product"]

#                 page = input_doc[page_no]

#                 crop_y = self.find_crop_point(
#                     page
#                 )

#                 if crop_y <= 0:
#                     continue

#                 # ---------------------------------------------
#                 # SAFE CLIP
#                 # ---------------------------------------------
#                 clip_rect = fitz.Rect(

#                     0,

#                     0,

#                     page.rect.width,

#                     crop_y + self.SAFETY_MARGIN

#                 )

#                 # ---------------------------------------------
#                 # THERMAL SCALE
#                 # ---------------------------------------------
#                 scale = (

#                     self.LABEL_WIDTH_PT
#                     / clip_rect.width

#                 ) * self.PRINT_SCALE_FIX

#                 content_height = (
#                     clip_rect.height * scale
#                 )

#                 final_height = (
#                     content_height
#                     + self.BOTTOM_PADDING_PT
#                 )

#                 # Prevent oversize
#                 if (
#                     final_height
#                     > self.LABEL_HEIGHT_PT
#                 ):

#                     scale = (

#                         self.LABEL_HEIGHT_PT
#                         / clip_rect.height

#                     ) * self.PRINT_SCALE_FIX

#                     content_height = (
#                         clip_rect.height * scale
#                     )

#                     final_height = (
#                         self.LABEL_HEIGHT_PT
#                     )

#                 final_width = (
#                     clip_rect.width * scale
#                 )

#                 # ---------------------------------------------
#                 # NEW PAGE
#                 # ---------------------------------------------
#                 new_page = output_pdf.new_page(

#                     width=final_width,

#                     height=final_height

#                 )

#                 # ---------------------------------------------
#                 # CENTER CONTENT
#                 # ---------------------------------------------
#                 y_offset = (

#                     final_height
#                     - content_height

#                 ) / 2

#                 target_rect = fitz.Rect(

#                     0,

#                     y_offset,

#                     final_width,

#                     y_offset + content_height

#                 )

#                 new_page.show_pdf_page(

#                     target_rect,

#                     input_doc,

#                     page_no,

#                     clip=clip_rect

#                 )

#                 # ---------------------------------------------
#                 # LABEL CREATED
#                 # ---------------------------------------------
#                 self.labels_found += 1

#                 if self.debug:

#                     print(
#                         f"  ✓ {courier} | {product}"
#                     )

#                     print(
#                         f"  ✓ Label size: "
#                         f"{final_width/72:.2f} x "
#                         f"{final_height/72:.2f} inch"
#                     )

#         # ---------------------------------------------
#         # NO LABELS
#         # ---------------------------------------------
#         if self.labels_found == 0:

#             input_doc.close()

#             output_pdf.close()

#             raise ValueError(
#                 "No valid labels found"
#             )

#         # ---------------------------------------------
#         # FINAL PDF
#         # ---------------------------------------------
#         result = output_pdf.tobytes()

#         # ---------------------------------------------
#         # DEBUG SUMMARY
#         # ---------------------------------------------
#         if self.debug:

#             print(
#                 "\n✓ Labels created:",
#                 self.labels_found
#             )

#             print("\n📦 PRODUCT SUMMARY")

#             for courier, products in (
#                 product_summary.items()
#             ):

#                 print(f"\n🚚 {courier}")

#                 for product, qty in (
#                     products.items()
#                 ):

#                     print(
#                         f"   {product} = {qty}"
#                     )

#         input_doc.close()

#         output_pdf.close()

#         # ---------------------------------------------
#         # RETURN
#         # ---------------------------------------------
#         return {

#             "pdf_bytes": result,

#             "product_summary": {

#                 courier: dict(products)

#                 for courier, products

#                 in product_summary.items()

#             },

#             "total_labels": self.labels_found,

#         }


# # --------------------------------------------------
# # Django helper
# # --------------------------------------------------
# def crop_meesho_labels_to_pdf(pdf_file):
#     """
#     Crop Meesho shipping labels
#     """
#     return MeeshoLabelCropper().create_label_pdf(
#         pdf_file
#     )


# ============================================================
# FILE: generator/label_utils.py
# Meesho Label Cropper — size-aware crop + exact output size
#
# Crop boundary logic:
#   • 3x5  → crop ABOVE TAX INVOICE (removed), page height fits
#             content (thermal-printer safe, no fixed height)
#   • 4x4 / 4x6 / A4 → fixed page size, include TAX INVOICE,
#             content scaled to fill page width; extra content
#             is clipped by the page boundary naturally.
# ============================================================

import fitz          # PyMuPDF
import re
from collections import defaultdict


# ----------------------------------------------------------
# Output size definitions  (width_pt, height_pt)
# 1 inch = 72 pt  |  1 mm ≈ 2.835 pt
# ----------------------------------------------------------
LABEL_SIZES = {
    "3x5": (3 * 72,        5 * 72),        # 216   × 360   pt
    "4x4": (4 * 72,        4 * 72),        # 288   × 288   pt
    "4x6": (4 * 72,        6 * 72),        # 288   × 432   pt
    "A4":  (210 * 2.83465, 297 * 2.83465), # 595.3 × 841.9 pt
}

DEFAULT_SIZE = "3x5"

# Sizes where TAX INVOICE section is EXCLUDED (crop above it)
EXCLUDE_TAX_INVOICE_SIZES = {"3x5"}

# 3x5 thermal-specific constants (from original working code)
THERMAL_SAFETY_MARGIN  = 6      # pt — prevents last-line clipping
THERMAL_PRINT_SCALE    = 0.96   # shrinks slightly for thermal-safe print
THERMAL_BOTTOM_PADDING = 10     # pt — ~3.5 mm bottom safety gap

# Padding inside fixed-size output pages (4x4 / 4x6 / A4)
PAGE_PADDING = 10


# ----------------------------------------------------------
# Merge multiple PDF file-like objects → one fitz.Document
# ----------------------------------------------------------
def merge_pdf_files(pdf_file_list):
    merged = fitz.open()
    for f in pdf_file_list:
        data = f.read()
        try:
            doc = fitz.open(stream=data, filetype="pdf")
            merged.insert_pdf(doc)
            doc.close()
        except Exception as e:
            raise ValueError(
                f"Could not read PDF '{getattr(f, 'name', '?')}': {e}"
            )
    return merged


class MeeshoLabelCropper:
    """
    Crops Meesho shipping labels from one merged fitz.Document.

    Parameters
    ----------
    label_size : str   — "3x5" | "4x4" | "4x6" | "A4"
    debug      : bool  — print progress to stdout
    """

    def __init__(self, label_size: str = DEFAULT_SIZE, debug: bool = True):
        size_key = label_size if label_size in LABEL_SIZES else DEFAULT_SIZE
        self.out_w, self.out_h = LABEL_SIZES[size_key]
        self.size_key          = size_key
        self.debug             = debug
        self.labels_found      = 0
        self.exclude_tax       = size_key in EXCLUDE_TAX_INVOICE_SIZES

    # ── Skip extra tax / terms-only pages ──────────────────────────
    def should_skip_page(self, page: fitz.Page) -> bool:
        text = page.get_text()
        skip_words = [
            "Tax is not payable on reverse charge",
            "This is a computer generated invoice",
            "logistics fee",
            "applicable to your order",
        ]
        return (
            any(w in text for w in skip_words)
            and "Customer Address" not in text
        )

    # ── Detect courier partner ──────────────────────────────────────
    def get_courier_name(self, page: fitz.Page) -> str:
        text = page.get_text().lower()
        for courier in ["delhivery", "valmo", "shadowfax",
                        "xpressbees", "ecom express", "ekart"]:
            if courier in text:
                return courier.title()
        return "Unknown"

    # ── Extract product name / SKU ──────────────────────────────────
    def get_product_name(self, page: fitz.Page) -> str:
        text  = page.get_text()
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        skip  = {"size", "qty", "color", "free size", "pink",
                 "order no.", "order no", "order"}

        for i, line in enumerate(lines):
            if line.lower() == "sku":
                for j in range(i + 1, min(i + 6, len(lines))):
                    c = lines[j].strip()
                    if c.lower() in skip or len(c) < 4:
                        continue
                    return c

        m = re.search(r"(\d+\s+[A-Za-z0-9\s\-]+)", text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if val.lower() != "size":
                return val
        return "Unknown Product"

    # ==============================================================
    # 3x5  THERMAL PATH
    # ==============================================================

    def _find_crop_y_above_tax(self, page: fitz.Page) -> float:
        """
        Original thermal logic:
        Finds the horizontal separator line just above TAX INVOICE
        and returns crop_y (just below that line).
        Falls back gracefully if line / TAX INVOICE not found.
        """
        page_rect = page.rect

        tax_rects = page.search_for("TAX INVOICE")
        if tax_rects:
            tax_y         = min(r.y0 for r in tax_rects)
            search_top    = tax_y - 40
            search_bottom = tax_y - 6

            lines = []
            for drawing in page.get_drawings():
                for item in drawing.get("items", []):
                    if item[0] != "l":
                        continue
                    p1, p2 = item[1], item[2]
                    if (abs(p1.y - p2.y) < 2
                            and search_top < p1.y < search_bottom
                            and abs(p2.x - p1.x) > page_rect.width * 0.7):
                        lines.append(p1.y)

            if lines:
                line_y = max(lines)
                crop_y = line_y + 3
                if self.debug:
                    print(f"    border line y={line_y:.1f}  crop_y={crop_y:.1f}")
                return crop_y

            # No separator line found — use text position
            return tax_y - 8

        # TAX INVOICE text not found — fallback
        pd = page.search_for("Product Details")
        if pd:
            return min(r.y0 for r in pd) + 80
        return page_rect.height * 0.5

    def _make_thermal_page(self, out_doc, in_doc, page_no, crop_y):
        """
        3x5 thermal output:
          • Page width  = 3 inches (216 pt) exactly
          • Page height = content height + BOTTOM_PADDING (not fixed 5 inches)
          • Content scaled with THERMAL_PRINT_SCALE (0.96) to stay print-safe
        Matches original working thermal-printer behaviour exactly.
        """
        page_w = in_doc[page_no].rect.width

        clip_rect = fitz.Rect(
            0, 0,
            page_w,
            crop_y + THERMAL_SAFETY_MARGIN
        )

        # Scale to 3-inch width with thermal safety shrink
        scale     = (self.out_w / clip_rect.width) * THERMAL_PRINT_SCALE
        content_h = clip_rect.height * scale
        final_h   = content_h + THERMAL_BOTTOM_PADDING

        # Cap at 5 inches if somehow taller
        if final_h > self.out_h:
            scale     = (self.out_h / clip_rect.height) * THERMAL_PRINT_SCALE
            content_h = clip_rect.height * scale
            final_h   = self.out_h

        final_w = clip_rect.width * scale

        # Centre content vertically within the small padding gap
        y_offset    = (final_h - content_h) / 2
        target_rect = fitz.Rect(0, y_offset, final_w, y_offset + content_h)

        new_page = out_doc.new_page(width=final_w, height=final_h)
        new_page.show_pdf_page(target_rect, in_doc, page_no, clip=clip_rect)

        if self.debug:
            print(f"    thermal page: {final_w/72:.2f} x {final_h/72:.2f} inch")

        return new_page

    # ==============================================================
    # 4x4 / 4x6 / A4  FIXED-SIZE PATH
    # ==============================================================

    def _find_full_content_bottom_y(self, page: fitz.Page) -> float:
        """
        Returns the y of the lowest content on the page (text + drawings),
        so TAX INVOICE and everything below it is included.
        """
        page_h   = page.rect.height
        lowest_y = 0.0

        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    lowest_y = max(lowest_y, span["bbox"][3])

        for drawing in page.get_drawings():
            rect = drawing.get("rect")
            if rect:
                lowest_y = max(lowest_y, rect.y1)

        return min(lowest_y + 6, page_h)

    def _find_label_top_y(self, page: fitz.Page) -> float:
        """
        Returns the y of the topmost border line above 'Customer Address'.
        Falls back to the text y itself if no drawing line found.
        """
        page_w = page.rect.width
        top_y  = None

        ca_rects = page.search_for("Customer Address")
        if ca_rects:
            ca_y = min(r.y0 for r in ca_rects)

            candidates = []
            for drawing in page.get_drawings():
                for item in drawing.get("items", []):
                    if item[0] != "l":
                        continue
                    p1, p2 = item[1], item[2]
                    if (abs(p1.y - p2.y) < 2
                            and abs(p2.x - p1.x) > page_w * 0.65
                            and p1.y < ca_y + 5
                            and p1.y > 0):
                        candidates.append(p1.y)

            top_y = min(candidates) if candidates else max(0.0, ca_y - 4)

        return top_y if top_y is not None else 0.0

    def _make_fixed_size_page(self, out_doc, in_doc, page_no, label_rect):
        """
        4x4 / 4x6 / A4 output:
          • Page is EXACTLY out_w × out_h pt
          • Content scaled to fill page width
          • If content is taller than the page, the page boundary
            clips it naturally — "fit to selected page size"
        """
        pad     = PAGE_PADDING
        avail_w = self.out_w - 2 * pad

        clip_w = label_rect.width
        clip_h = label_rect.height

        if clip_w <= 0 or clip_h <= 0:
            return

        # Scale to fill width; height may overflow page (gets clipped)
        scale     = avail_w / clip_w
        content_w = clip_w * scale
        content_h = clip_h * scale

        # Centre horizontally, pin to top padding vertically
        x0 = pad + (avail_w - content_w) / 2
        y0 = pad

        target_rect = fitz.Rect(x0, y0, x0 + content_w, y0 + content_h)

        new_page = out_doc.new_page(width=self.out_w, height=self.out_h)
        new_page.show_pdf_page(target_rect, in_doc, page_no, clip=label_rect)

        if self.debug:
            print(f"    fixed page: {self.out_w/72:.2f} x {self.out_h/72:.2f} inch  "
                  f"scale={scale:.3f}")

        return new_page

    # ==============================================================
    # Main processing
    # ==============================================================
    def create_label_pdf(self, input_doc: fitz.Document):
        output_doc      = fitz.open()
        product_summary = defaultdict(lambda: defaultdict(int))
        grouped_labels  = defaultdict(list)

        if self.debug:
            tax_mode = "excluded — crop above TAX INVOICE (thermal)" \
                       if self.exclude_tax \
                       else "included — fit to page size"
            print(f"\n{'='*70}")
            print(f"📐 Output size : {self.size_key}  "
                  f"({self.out_w:.0f} × {self.out_h:.0f} pt)")
            print(f"🧾 TAX INVOICE : {tax_mode}")
            print(f"📄 Input pages : {len(input_doc)}")
            print(f"{'='*70}")

        # ── Pass 1: scan all pages ────────────────────────────────────
        for pno in range(len(input_doc)):
            page = input_doc[pno]
            if self.should_skip_page(page):
                if self.debug:
                    print(f"  ⚠ Page {pno+1}: skipped (tax/terms)")
                continue
            courier = self.get_courier_name(page)
            product = self.get_product_name(page)
            grouped_labels[courier].append({"product": product, "page_no": pno})
            product_summary[courier][product] += 1

        # ── Pass 2: render sorted output ──────────────────────────────
        for courier in sorted(grouped_labels.keys()):
            if self.debug:
                print(f"\n📦 {courier}")

            for item in sorted(grouped_labels[courier], key=lambda x: x["product"]):
                pno  = item["page_no"]
                page = input_doc[pno]

                if self.exclude_tax:
                    # ── 3x5 THERMAL PATH ──────────────────────────────
                    crop_y = self._find_crop_y_above_tax(page)
                    if crop_y <= 0:
                        if self.debug:
                            print(f"  ✗ Page {pno+1}: invalid crop_y, skipped")
                        continue
                    self._make_thermal_page(output_doc, input_doc, pno, crop_y)

                else:
                    # ── FIXED SIZE PATH (4x4 / 4x6 / A4) ─────────────
                    top_y    = self._find_label_top_y(page)
                    bottom_y = self._find_full_content_bottom_y(page)

                    if top_y >= bottom_y:
                        top_y = max(0.0, bottom_y - 200)

                    label_rect = fitz.Rect(0, top_y, page.rect.width, bottom_y)

                    if label_rect.height < 10 or label_rect.width < 10:
                        if self.debug:
                            print(f"  ✗ Page {pno+1}: degenerate rect, skipped")
                        continue

                    if self.debug:
                        print(f"    label rect: top_y={top_y:.1f}  "
                              f"bottom_y={bottom_y:.1f}  "
                              f"height={bottom_y - top_y:.1f} pt")

                    self._make_fixed_size_page(output_doc, input_doc, pno, label_rect)

                self.labels_found += 1
                if self.debug:
                    print(f"  ✓ {item['product']}")

        if self.labels_found == 0:
            output_doc.close()
            raise ValueError(
                "No valid Meesho labels found in the uploaded PDF(s). "
                "Please upload a Meesho shipping label PDF."
            )

        result = output_doc.tobytes()
        output_doc.close()

        if self.debug:
            print(f"\n✅ Total labels: {self.labels_found}")

        return {
            "pdf_bytes":       result,
            "product_summary": {c: dict(p) for c, p in product_summary.items()},
            "total_labels":    self.labels_found,
        }


# ── Public helper ───────────────────────────────────────────────────
def crop_meesho_labels_to_pdf(pdf_file_list, label_size: str = DEFAULT_SIZE):
    """
    pdf_file_list : list[UploadedFile] or single UploadedFile
    label_size    : "3x5" | "4x4" | "4x6" | "A4"
    """
    if not isinstance(pdf_file_list, (list, tuple)):
        pdf_file_list = [pdf_file_list]

    merged = merge_pdf_files(pdf_file_list)
    try:
        result = MeeshoLabelCropper(
            label_size=label_size, debug=True
        ).create_label_pdf(merged)
    finally:
        merged.close()

    return result