#!/usr/bin/env python3
# main.py - Main entry point for Document Understanding layer

import sys
import os
import json
from pathlib import Path

# Add document_understanding to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from document_understanding import PDFProcessor, OCREngine, SectionDetector, SkillExtractor, CareerProfileBuilder

def main():
    """Main function to demonstrate Document Understanding pipeline"""

    # Check if CV file exists
    # Cho phép chỉ định tên file CV qua tham số dòng lệnh
    cv_file = sys.argv[1] if len(sys.argv) > 1 else "cv.pdf"
    cv_path = Path(cv_file)

    if not cv_path.exists():
        print(f"Lỗi: Tệp CV '{cv_file}' không tìm thấy trong thư mục hiện tại.")
        print("Vui lòng đặt tệp CV vào thư mục hiện tại và chạy lại.")
        return

    print("Starting Document Understanding pipeline...")
    print(f"Processing CV: {cv_file}")

    try:
        # Initialize components
        pdf_processor = PDFProcessor()
        ocr_engine = OCREngine()
        section_detector = SectionDetector()
        skill_extractor = SkillExtractor()
        career_builder = CareerProfileBuilder()

        # Step 1: Detect PDF type
        print("\nStep 1: Detecting PDF type...")
        is_digital = pdf_processor.is_digital_pdf(cv_file)
        print(f"PDF type: {'Digital' if is_digital else 'Scanned'}")

        # Step 2: Extract content
        print("\nStep 2: Extracting content...")
        if is_digital:
            text_content = pdf_processor.extract_text_from_digital_pdf(cv_file)
            print(f"Extracted {len(text_content)} characters of text")

            # Get layout info
            layout_info = pdf_processor.get_layout_info(cv_file)
            print(f"Layout info: {layout_info['total_pages']} pages")

        else:
            # Extract images for scanned PDF
            images = pdf_processor.extract_images_from_pdf(cv_file)
            print(f"Extracted {len(images)} images")

            # Process images with OCR
            # Xử lý OCR với ngôn ngữ tiếng Việt (vi)
            ocr_results = ocr_engine.ocr_multiple_images(images, lang="vie")
            text_content = "\n".join([result["text"] for result in ocr_results])
            print(f"OCR extracted: {len(text_content)} characters")

        # Step 3: Detect sections
        print("\nStep 3: Detecting sections...")
        sections = section_detector.detect_sections(text_content)

        # Normalize section names
        # Chuẩn hóa tên các phần theo cấu trúc CV tiếng Việt
        sections = section_detector.normalize_section_names(sections)

        # Step 4: Extract and normalize skills
        print("\nStep 4: Extracting and normalizing skills...")
        # Handle case where skills section might not be detected
        if "skills" in sections:
            normalized_skills = skill_extractor.normalize_skills(sections["skills"])
            sections["skills"] = normalized_skills
        else:
            sections["skills"] = []
            normalized_skills = []

        # Process project technologies
        # Handle case where projects section might not be detected
        if "projects" in sections:
            for i, project in enumerate(sections["projects"]):
                sections["projects"][i] = skill_extractor.process_project_technologies(project)
        else:
            sections["projects"] = []

        # Step 5: Building career profile...
        print("\nStep 5: Building career profile...")
        career_profile = career_builder.build(sections)  # ✅ ĐÃ SỬA: dùng build(), không phải build_career_profile

        # Output results
        print("\n" + "="*60)
        print("DOCUMENT UNDERSTANDING RESULTS")
        print("="*60)

        print(f"\nCareer Profile:")
        print(f"  Current Role: {career_profile['current_role']}")
        print(f"  Career Stage: {career_profile['career_stage']}")
        print(f"  Experience: {career_profile['experience_years']} years")
        print(f"  Domains: {', '.join(career_profile['domains'])}")

        print(f"\nSkills ({len(career_profile['skills'])}):")
        for skill in career_profile['skills'][:10]:  # Show first 10
            print(f"  - {skill}")
        if len(career_profile['skills']) > 10:
            print(f"  ... and {len(career_profile['skills']) - 10} more")

        print(f"\nTechnology Stack ({len(career_profile['technology_stack'])}):")
        for tech in career_profile['technology_stack'][:10]:
            print(f"  - {tech}")
        if len(career_profile['technology_stack']) > 10:
            print(f"  ... and {len(career_profile['technology_stack']) - 10} more")

        # Save results to JSON
        output_data = {
            "pdf_type": "digital" if is_digital else "scanned",
            "structured_data": sections,
            "career_profile": career_profile
        }

        with open("document_understanding_output.json", "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        print(f"\nResults saved to: document_understanding_output.json")
        print("\nPipeline completed successfully!")

    except Exception as e:
        print(f"Error during document understanding: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
