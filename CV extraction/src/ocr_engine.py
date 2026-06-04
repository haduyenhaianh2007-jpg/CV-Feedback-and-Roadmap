import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
import os

class OCREngine:
    """OCR Engine using PaddleOCR (simulated for now - will be replaced with actual PaddleOCR integration)"""

    def __init__(self):
        # In real implementation, this would initialize PaddleOCR
        # For now, we'll simulate with basic OpenCV OCR capabilities
        pass

    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for better OCR results"""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (3, 3), 0)

        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )

        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)

        return denoised

    def calculate_image_quality(self, image: np.ndarray) -> Dict[str, float]:
        """Calculate image quality metrics"""
        # Blur score (Laplacian variance)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()

        # Contrast score (standard deviation of pixel intensities)
        contrast_score = np.std(gray)

        # Resolution score
        height, width = image.shape[:2]
        resolution_score = (height * width) / 1000000  # normalized by 1M pixels

        # Calculate skew angle
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        lines = cv2.HoughLines(edges, 1, np.pi/180, 100)
        skew_angle = 0.0
        if lines is not None:
            angles = [line[0][1] for line in lines]
            skew_angle = np.median(angles) * 180/np.pi - 90

        return {
            "blur_score": float(blur_score),
            "contrast_score": float(contrast_score),
            "resolution_score": float(resolution_score),
            "skew_angle": float(skew_angle),
            "quality_level": self._determine_quality_level(blur_score, contrast_score)
        }

    def _determine_quality_level(self, blur_score: float, contrast_score: float) -> str:
        """Determine quality level based on metrics"""
        if blur_score < 50 and contrast_score < 30:
            return "low"
        elif blur_score < 100 and contrast_score < 50:
            return "medium"
        else:
            return "high"

    def enhance_image(self, image: np.ndarray) -> np.ndarray:
        """Enhance image quality for OCR"""
        # Get quality metrics
        quality = self.calculate_image_quality(image)

        enhanced = image.copy()

        # Apply enhancements based on quality
        if quality["quality_level"] == "low":
            # Strong enhancement for low quality
            enhanced = cv2.GaussianBlur(enhanced, (5, 5), 0)

            # CLAHE for contrast enhancement
            lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            lab = cv2.merge((l_enhanced, a, b))
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

            # Deskew if needed
            if abs(quality["skew_angle"]) > 1.0:
                (h, w) = enhanced.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, quality["skew_angle"], 1.0)
                enhanced = cv2.warpAffine(enhanced, M, (w, h),
                                        flags=cv2.INTER_CUBIC,
                                        borderMode=cv2.BORDER_REPLICATE)

        elif quality["quality_level"] == "medium":
            # Moderate enhancement
            enhanced = cv2.GaussianBlur(enhanced, (3, 3), 0)

            # CLAHE for contrast
            lab = cv2.cvtColor(enhanced, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l_enhanced = clahe.apply(l)
            lab = cv2.merge((l_enhanced, a, b))
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

        return enhanced

    def ocr_single_image(self, image: np.ndarray, lang: str = "en") -> Dict:
        """Simulate OCR on a single image (will be replaced with PaddleOCR)"""
        # In real implementation, this would call PaddleOCR
        # For simulation, we'll use simple text detection
        preprocessed = self.preprocess_image(image)

        # Simulate OCR results with confidence scores
        # This is just a placeholder - actual implementation would use PaddleOCR
        simulated_results = {
            "text": "",
            "confidence": 0.85,
            "boxes": []
        }

        # For demo purposes, we'll return some sample text
        # In real implementation, this would be actual OCR output
        if lang == "vi":
            simulated_results["text"] = "Kỹ năng\\nPython\\nDocker\\nKubernetes\\nFastAPI"
        else:
            simulated_results["text"] = "Skills\\nPython\\nDocker\\nKubernetes\\nFastAPI"

        return simulated_results

    def ocr_multiple_images(self, images: List[np.ndarray], lang: str = "en") -> List[Dict]:
        """OCR on multiple images"""
        results = []
        for i, image in enumerate(images):
            enhanced = self.enhance_image(image)
            result = self.ocr_single_image(enhanced, lang)
            result["page"] = i + 1
            results.append(result)
        return results
