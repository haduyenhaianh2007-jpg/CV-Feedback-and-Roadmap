"""
Main CV Extractor - Orchestrate entire extraction pipeline
Structured extraction + LLM validation + JSON validation
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any

from cv_schema import CV, PersonalInfo, Education, Experience, Project, Skill, Certification, Award
from regex_extractor import RegexExtractor
from text_cleaner import CVTextCleaner
from section_splitter import SectionSplitter
from llm_client import ClaudeLLMClient
from json_repair import JSONRepair, JSONValidator


class CVExtractor:
    """Main CV extraction pipeline"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize extractor
        Args:
            api_key: Anthropic API key (or set ANTHROPIC_API_KEY env)
        """
        self.regex_extractor = RegexExtractor()
        self.text_cleaner = CVTextCleaner(aggressive_merge=False)
        self.section_splitter = SectionSplitter()
        self.llm_client = ClaudeLLMClient(api_key=api_key)
        self.validator = JSONValidator()
    
    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Main extraction pipeline
        """
        print("=" * 60)
        print("STEP 1: Clean text")
        print("=" * 60)
        cleaned_text = self.text_cleaner.clean(text)
        print(f"✓ Cleaned text: {len(cleaned_text)} characters")
        
        print("\n" + "=" * 60)
        print("STEP 2: Extract personal info (Regex layer)")
        print("=" * 60)
        personal_header = self.section_splitter.extract_personal_info_header(cleaned_text)
        regex_personal = self.regex_extractor.extract_all_personal_info(personal_header)
        print(f"✓ Extracted via regex: {regex_personal}")
        
        print("\n" + "=" * 60)
        print("STEP 3: Split into sections")
        print("=" * 60)
        sections = self.section_splitter.split_by_sections(cleaned_text)
        print(f"✓ Found sections: {list(sections.keys())}")
        
        print("\n" + "=" * 60)
        print("STEP 4: Extract each section via LLM")
        print("=" * 60)
        
        # Extract personal info details
        print("\nExtracting: PERSONAL INFO...")
        personal_info_llm = self.llm_client.extract_personal_info(personal_header)
        personal_info = {**regex_personal, **(personal_info_llm or {})}
        print(f"✓ Personal info: {personal_info}")
        
        # Extract education
        education = []
        if 'education' in sections:
            print("\nExtracting: EDUCATION...")
            education_data = self.llm_client.extract_education(sections['education'])
            education = [Education(**e) for e in education_data] if education_data else []
            print(f"✓ Found {len(education)} education entries")
        
        # Extract experience (merged with activities)
        experience = []
        experience_text = sections.get('experience', '')
        if 'activities' in sections:
            experience_text = experience_text + '\n\n' + sections['activities']
        
        if experience_text.strip():
            print("\nExtracting: EXPERIENCE & ACTIVITIES...")
            experience_data = self.llm_client.extract_experience(experience_text)
            experience = [Experience(**e) for e in experience_data] if experience_data else []
            print(f"✓ Found {len(experience)} experience entries")
        
        # Extract projects
        projects = []
        if 'projects' in sections:
            print("\nExtracting: PROJECTS...")
            projects_data = self.llm_client.extract_projects(sections['projects'])
            projects = [Project(**p) for p in projects_data] if projects_data else []
            print(f"✓ Found {len(projects)} projects")
        
        # Extract skills
        skills = []
        if 'skills' in sections:
            print("\nExtracting: SKILLS...")
            skills_data = self.llm_client.extract_skills(sections['skills'])
            skills = [Skill(**s) for s in skills_data] if skills_data else []
            print(f"✓ Found {len(skills)} skill categories")
        
        # Extract certifications
        certifications = []
        if 'certifications' in sections:
            print("\nExtracting: CERTIFICATIONS...")
            certs_data = self.llm_client.extract_certifications(sections['certifications'])
            certifications = [Certification(**c) for c in certs_data] if certs_data else []
            print(f"✓ Found {len(certifications)} certifications")
        
        # Extract awards (section name is 'achievements' from splitter)
        awards = []
        if 'achievements' in sections:
            print("\nExtracting: ACHIEVEMENTS...")
            awards_data = self.llm_client.extract_awards(sections['achievements'])
            awards = [Award(**a) for a in awards_data] if awards_data else []
            print(f"✓ Found {len(awards)} awards")
        
        print("\n" + "=" * 60)
        print("STEP 5: Create structured CV object")
        print("=" * 60)
        
        cv = CV(
            personal_info=PersonalInfo(**personal_info) if personal_info else None,
            education=education,
            experience=experience,
            projects=projects,
            skills=skills,
            certifications=certifications,
            awards=awards,
        )
        
        print("✓ CV object created")
        
        print("\n" + "=" * 60)
        print("STEP 6: Convert to JSON")
        print("=" * 60)
        
        cv_dict = cv.model_dump(exclude_none=True)
        json_str = self.validator.ensure_ascii_false_dump(cv_dict)
        print("✓ Converted to JSON (Vietnamese support enabled)")
        print(f"✓ JSON size: {len(json_str)} characters")
        
        return cv_dict
    
    def extract_from_file(self, filepath: str) -> Optional[Dict[str, Any]]:
        """Extract from text file"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
            return self.extract(text)
        except Exception as e:
            print(f"Error reading file: {e}")
            return None
    
    def extract_and_save(self, filepath: str, output_json: str) -> bool:
        """Extract and save to JSON file"""
        cv_dict = self.extract_from_file(filepath)
        
        if cv_dict is None:
            print("Extraction failed")
            return False
        
        # Save to JSON
        if self.validator.safe_write(output_json, cv_dict):
            print(f"✓ Saved to: {output_json}")
            return True
        else:
            print(f"✗ Failed to save to: {output_json}")
            return False


def main():
    """Main entry point"""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python cv_structured_extractor.py <input_text_file> [output_json]")
        print("\nExample:")
        print("  python cv_structured_extractor.py cv_extracted.txt cv_output.json")
        return
    
    input_file = sys.argv[1]
    output_json = sys.argv[2] if len(sys.argv) > 2 else "cv_output.json"
    
    # Check if input file exists
    if not Path(input_file).exists():
        print(f"Error: File '{input_file}' not found")
        return
    
    print(f"\nProcessing: {input_file}")
    print(f"Output: {output_json}")
    
    # Extract and save
    extractor = CVExtractor()
    success = extractor.extract_and_save(input_file, output_json)
    
    if success:
        print("\n✓ Extraction complete!")
    else:
        print("\n✗ Extraction failed")


if __name__ == '__main__':
    main()
