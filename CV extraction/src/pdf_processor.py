import fitz  # PyMuPDF
import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional, Union
import os


class PDFProcessor:
    """Handle PDF processing with PyMuPDF for digital PDFs and image extraction for scanned PDFs"""

    def __init__(self):
        self.dpi = 300

    def is_digital_pdf(self, file_path: str) -> bool:
        """Check if PDF is digital (has text layer) or scanned (image-based)"""
        try:
            doc = fitz.open(file_path)
            text_content = ""
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text = page.get_text()
                text_content += text
            # If text content is substantial (>100 characters), it's likely digital
            return len(text_content.strip()) > 100
        except Exception as e:
            print(f"Error checking PDF type: {e}")
            return False

    def extract_text_from_digital_pdf(self, file_path: str) -> str:
        """Extract text from digital PDF using PyMuPDF"""
        try:
            doc = fitz.open(file_path)
            text_parts = []
            for page_num, page in enumerate(doc):
                page_text = page.get_text()
                text_parts.append(page_text)
            # Join pages with double newline to separate them clearly
            full_text = "\n\n".join(text_parts)
            return full_text.strip()
        except Exception as e:
            raise Exception(f"Failed to extract text from digital PDF: {e}")

    def extract_images_from_pdf(self, file_path: str) -> List[np.ndarray]:
        """Extract images from PDF (for scanned PDFs)"""
        try:
            doc = fitz.open(file_path)
            images = []

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                image_list = page.get_images(full=True)

                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    # Convert to numpy array
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img_cv is not None:
                        images.append(img_cv)

            # If no images extracted, try rendering pages as images
            if not images:
                for page_num, page in enumerate(doc):
                    mat = fitz.Matrix(self.dpi / 72, self.dpi / 72)
                    pix = page.get_pixmap(matrix=mat)
                    img_data = pix.tobytes("png")
                    nparr = np.frombuffer(img_data, np.uint8)
                    img_cv = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img_cv is not None:
                        images.append(img_cv)

            return images
        except Exception as e:
            raise Exception(f"Failed to extract images: {e}")

    def get_layout_info(self, file_path: str) -> Dict:
        """Extract layout information (bounding boxes, fonts, etc.)"""
        try:
            doc = fitz.open(file_path)
            layout_info = {
                "pages": [],
                "total_pages": len(doc)
            }

            for page_num, page in enumerate(doc):
                blocks = page.get_text("dict")["blocks"]
                page_layout = {
                    "page_number": page_num + 1,
                    "blocks": [],
                    "width": page.rect.width,
                    "height": page.rect.height
                }

                for block in blocks:
                    if block["type"] == 0:  # Text block
                        bbox = block["bbox"]
                        page_layout["blocks"].append({
                            "type": "text",
                            "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                            "text": self._extract_text_from_block(block),
                            "font_size": self._get_font_size(block)
                        })

                layout_info["pages"].append(page_layout)

            return layout_info
        except Exception as e:
            print(f"Warning: Could not extract layout info: {e}")
            return {"pages": [], "total_pages": 0}

    def _extract_text_from_block(self, block: dict) -> str:
        """Helper to extract text from a block"""
        lines_text = []
        for line in block.get("lines", []):
            spans_text = []
            for span in line.get("spans", []):
                spans_text.append(span.get("text", ""))
            lines_text.append("".join(spans_text))
        return "\n".join(lines_text).strip()

    def _get_font_size(self, block: dict) -> float:
        """Get font size from block"""
        if block.get("lines"):
            first_line = block["lines"][0]
            if first_line.get("spans"):
                first_span = first_line["spans"][0]
                return first_span.get("size", 12.0)
        return 12.0
