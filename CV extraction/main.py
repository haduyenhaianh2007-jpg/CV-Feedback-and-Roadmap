#!/usr/bin/env python3
"""
Main entry point for CV Processing Pipeline (Module 1).
Supports dynamic CV input via CLI arguments for Backend integration.
"""

import sys
import json
import argparse
from pathlib import Path

# Add src to path for local imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src import (
    PDFProcessor,
    OCREngine,
    SectionDetector,
    SkillExtractor,
    CareerProfileBuilder,
)


def process_cv(cv_file: str, output_file: str = None) -> dict:
    """
    Process a single CV PDF and return structured career profile.

    Args:
        cv_file: Path to input CV PDF
        output_file: Optional path to save JSON output

    Returns:
        Dict containing pdf_type, structured_data, and career_profile
    """
    cv_path = Path(cv_file)
    if not cv_path.exists():
        raise FileNotFoundError(f"CV file not found: {cv_file}")

    print(f"Processing CV: {cv_file}")

    # Initialize components
    pdf_processor = PDFProcessor()
    ocr_engine = OCREngine()
    section_detector = SectionDetector()
    skill_extractor = SkillExtractor()
    career_builder = CareerProfileBuilder()

    # Step 1: Detect PDF type
    is_digital = pdf_processor.is_digital_pdf(cv_file)
    print(f"PDF type: {'Digital' if is_digital else 'Scanned'}")

    # Step 2: Extract content
    if is_digital:
        text_content = pdf_processor.extract_text_from_digital_pdf(cv_file)
        print(f"Extracted {len(text_content)} characters")
    else:
        images = pdf_processor.extract_images_from_pdf(cv_file)
        print(f"Extracted {len(images)} images for OCR")
        ocr_results = ocr_engine.ocr_multiple_images(images, lang="vie")
        text_content = "\n".join([r["text"] for r in ocr_results])
        print(f"OCR extracted: {len(text_content)} characters")

    # Step 3: Detect and normalize sections
    sections = section_detector.detect_sections(text_content)
    sections = section_detector.normalize_section_names(sections)

    # Step 4: Extract and normalize skills
    if "skills" in sections:
        sections["skills"] = skill_extractor.normalize_skills(sections["skills"])
    else:
        sections["skills"] = []

    if "projects" in sections:
        for i, project in enumerate(sections["projects"]):
            sections["projects"][i] = skill_extractor.process_project_technologies(project)
    else:
        sections["projects"] = []

    # Step 5: Build career profile
    career_profile = career_builder.build(sections)

    # Assemble output
    output_data = {
        "pdf_type": "digital" if is_digital else "scanned",
        "structured_data": sections,
        "career_profile": career_profile,
    }

    # Save to file if requested
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {output_file}")

    return output_data


def main():
    parser = argparse.ArgumentParser(description="CV Processing Pipeline - Module 1")
    parser.add_argument("--input", "-i", default="examples/sample_cv.pdf",
                        help="Path to input CV PDF (default: examples/sample_cv.pdf)")
    parser.add_argument("--output", "-o", default=None,
                        help="Path to output JSON file (optional, prints to stdout if omitted)")
    args = parser.parse_args()

    try:
        result = process_cv(args.input, args.output)
        if not args.output:
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
