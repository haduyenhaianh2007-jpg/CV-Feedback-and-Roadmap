"""
LLM-based Structured CV Extraction
Combines Regex Layer + LLM Layer + Validation Layer
"""

import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from cv_schema import CV, PersonalInfo, Education, Experience, Project, Skill, Certification, Award, Language
from regex_extractor import RegexExtractor
from json_repairer import JSONRepairer
from section_splitter import SectionSplitter

logger = logging.getLogger(__name__)


@dataclass
class ExtractionConfig:
    """Configuration for CV extraction"""
    use_ollama: bool = True  # Use local Qwen vs Anthropic
    use_anthropic: bool = False  # Use Anthropic Claude API
    
    # For Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct-q4_K_M"
    
    # For Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    
    # Extraction settings
    aggressive_extraction: bool = False  # More aggressive = more hallucination risk
    validate_output: bool = True  # Validate against schema
    repair_json: bool = True  # Try to fix malformed JSON


class CVExtractor:
    """Main CV extraction orchestrator"""
    
    def __init__(self, config: Optional[ExtractionConfig] = None):
        """
        Initialize extractor
        
        Args:
            config: Extraction configuration
        """
        self.config = config or ExtractionConfig()
        self.regex_extractor = RegexExtractor()
        self.section_splitter = SectionSplitter()
        
        # Initialize LLM client
        self.llm = self._init_llm()
    
    def _init_llm(self):
        """Initialize LLM client (Ollama or Anthropic)"""
        if self.config.use_ollama:
            try:
                from ollama_client import OllamaClient, OllamaConfig
                
                config = OllamaConfig(
                    base_url=self.config.ollama_base_url,
                    model=self.config.ollama_model,
                )
                return OllamaClient(config)
            except Exception as e:
                logger.warning(f"Failed to initialize Ollama: {e}")
                return None
        
        elif self.config.use_anthropic:
            try:
                from anthropic import Anthropic
                
                return Anthropic(api_key=self.config.anthropic_api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic: {e}")
                return None
        
        return None
    
    def extract(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract CV from text
        
        Args:
            text: Raw CV text
        
        Returns:
            Extracted CV data as dictionary
        """
        logger.info("Starting CV extraction...")
        
        # Step 1: Split into sections
        logger.info("Step 1: Splitting into sections...")
        sections = self.section_splitter.split(text)
        
        # Step 2: Regex extraction (deterministic fields)
        logger.info("Step 2: Regex extraction...")
        regex_data = self._extract_with_regex(sections)
        
        # Step 3: LLM extraction (structured fields)
        logger.info("Step 3: LLM extraction...")
        llm_data = self._extract_with_llm(sections)
        
        # Step 4: Merge results
        logger.info("Step 4: Merging results...")
        merged_data = self._merge_extraction_results(regex_data, llm_data)
        
        # Step 5: Validate
        if self.config.validate_output:
            logger.info("Step 5: Validating output...")
            merged_data = self._validate_output(merged_data)
        
        logger.info("Extraction complete!")
        return merged_data
    
    def _extract_with_regex(self, sections: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract deterministic fields using regex
        
        Args:
            sections: Sections from text
        
        Returns:
            Extracted data
        """
        pre_text = sections.get('_pre_text', '')
        
        return {
            'email': self.regex_extractor.extract_email(pre_text),
            'phone': self.regex_extractor.extract_phone(pre_text),
            'github': self.regex_extractor.extract_github(pre_text),
            'linkedin': self.regex_extractor.extract_linkedin(pre_text),
        }
    
    def _extract_with_llm(self, sections: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract structured fields using LLM
        
        Args:
            sections: Sections from text
        
        Returns:
            Extracted structured data
        """
        if not self.llm:
            logger.warning("LLM not available, skipping LLM extraction")
            return {}
        
        extracted = {}
        
        # Extract education
        if 'education' in sections:
            logger.info("Extracting education...")
            edu_json = self._llm_extract_section(
                'education',
                sections['education'],
                self._get_education_prompt()
            )
            if edu_json:
                extracted['education'] = edu_json
        
        # Extract skills
        if 'skills' in sections:
            logger.info("Extracting skills...")
            skills_json = self._llm_extract_section(
                'skills',
                sections['skills'],
                self._get_skills_prompt()
            )
            if skills_json:
                extracted['skills'] = skills_json
        
        # Extract experience
        if 'experience' in sections:
            logger.info("Extracting experience...")
            exp_json = self._llm_extract_section(
                'experience',
                sections['experience'],
                self._get_experience_prompt()
            )
            if exp_json:
                extracted['experience'] = exp_json
        
        # Extract projects
        if 'projects' in sections:
            logger.info("Extracting projects...")
            proj_json = self._llm_extract_section(
                'projects',
                sections['projects'],
                self._get_projects_prompt()
            )
            if proj_json:
                extracted['projects'] = proj_json
        
        # Extract achievements
        if 'achievements' in sections:
            logger.info("Extracting achievements...")
            ach_json = self._llm_extract_section(
                'achievements',
                sections['achievements'],
                self._get_achievements_prompt()
            )
            if ach_json:
                extracted['achievements'] = ach_json
        
        return extracted
    
    def _llm_extract_section(self, section_name: str, content: str, prompt_template: str) -> Optional[Any]:
        """
        Extract single section using LLM
        
        Args:
            section_name: Name of section (for logging)
            content: Section content
            prompt_template: Prompt template
        
        Returns:
            Parsed JSON or None
        """
        if not content.strip():
            return None
        
        # Fill prompt
        full_prompt = prompt_template.format(text=content)
        
        try:
            if self.config.use_ollama and self.llm:
                # Use Ollama
                response = self.llm.generate(
                    full_prompt,
                    system="You are an expert CV parser. Extract information accurately. Return ONLY valid JSON.",
                    temperature=0.2,
                    json_mode=True
                )
            
            elif self.config.use_anthropic and self.llm:
                # Use Anthropic
                response = self.llm.messages.create(
                    model=self.config.anthropic_model,
                    max_tokens=2000,
                    messages=[
                        {"role": "user", "content": full_prompt}
                    ]
                ).content[0].text
            
            else:
                logger.warning("No LLM available")
                return None
            
            # Repair JSON if needed
            if self.config.repair_json:
                data = JSONRepairer.repair(response)
            else:
                data = json.loads(response)
            
            return data
        
        except Exception as e:
            logger.error(f"Error extracting {section_name}: {e}")
            return None
    
    def _merge_extraction_results(self, regex_data: Dict[str, Any], llm_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge regex and LLM extraction results
        
        Args:
            regex_data: Results from regex extraction
            llm_data: Results from LLM extraction
        
        Returns:
            Merged data
        """
        # Start with LLM data (more comprehensive)
        merged = dict(llm_data)
        
        # Merge regex fields (override if LLM didn't extract)
        personal_info = merged.get('personal_info', {})
        if isinstance(personal_info, dict):
            personal_info.update(regex_data)
            merged['personal_info'] = personal_info
        else:
            merged['personal_info'] = regex_data
        
        return merged
    
    def _validate_output(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate output against CV schema
        
        Args:
            data: Extracted data
        
        Returns:
            Validated data (with defaults for missing required fields)
        """
        try:
            # Ensure required fields exist
            if 'education' not in data or not data['education']:
                logger.warning("No education data extracted")
                data['education'] = []
            
            if 'skills' not in data or not data['skills']:
                logger.warning("No skills data extracted")
                data['skills'] = []
            
            # Try to validate with schema
            cv = CV.model_validate(data)
            return cv.model_dump(exclude_none=True)
        
        except Exception as e:
            logger.warning(f"Schema validation failed: {e}")
            logger.warning("Returning data without full validation")
            return data
    
    # Prompt templates
    
    def _get_education_prompt(self) -> str:
        return """Extract education information from the text.

Return ONLY a JSON array where each object has:
{
  "school": "University name",
  "major": "Field of study",
  "gpa": "GPA if mentioned",
  "start_date": "Start date (e.g., '09/2025')",
  "end_date": "End date (e.g., '2026' or 'Present')",
  "currently_studying": true/false,
  "description": "Any additional details"
}

Rules:
- Output ONLY valid JSON
- Missing fields -> null
- Preserve original text
- Do not invent information

Text:

{text}"""
    
    def _get_skills_prompt(self) -> str:
        return """Extract skills from the text.

Return ONLY a JSON array where each object has:
{
  "name": "Skill name",
  "category": "Category (e.g., Programming, AI/ML, Tools)",
  "proficiency": "Proficiency level if mentioned"
}

Rules:
- Output ONLY valid JSON
- Include all mentioned skills
- Group by category if possible
- Do not invent skills

Text:

{text}"""
    
    def _get_experience_prompt(self) -> str:
        return """Extract work experience from the text.

Return ONLY a JSON array where each object has:
{
  "company": "Company name",
  "position": "Job title",
  "start_date": "Start date",
  "end_date": "End date (or 'Present')",
  "currently_working": true/false,
  "description": ["Bullet point 1", "Bullet point 2"],
  "technologies": ["Tech 1", "Tech 2"]
}

Rules:
- Output ONLY valid JSON
- Extract bullet points as array
- Extract technologies/tools mentioned
- Missing fields -> null

Text:

{text}"""
    
    def _get_projects_prompt(self) -> str:
        return """Extract projects from the text.

Return ONLY a JSON array where each object has:
{
  "name": "Project name",
  "role": "Your role",
  "description": ["Bullet point 1", "Bullet point 2"],
  "technologies": ["Tech 1", "Tech 2"],
  "url": "Project URL if mentioned",
  "start_date": "Start date if mentioned",
  "end_date": "End date if mentioned"
}

Rules:
- Output ONLY valid JSON
- Extract descriptions as bullet points
- Extract all technologies mentioned
- Missing fields -> null

Text:

{text}"""
    
    def _get_achievements_prompt(self) -> str:
        return """Extract awards and achievements from the text.

Return ONLY a JSON array where each object has:
{
  "title": "Award/Achievement title",
  "description": "Details or context",
  "date": "Date if mentioned"
}

Rules:
- Output ONLY valid JSON
- Include rankings and placements
- Missing fields -> null

Text:

{text}"""


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Test with sample text
    sample_text = """
Ha Duyen Hai Anh
+(84) 971 190 707 | haduyenhaianh2007@gmail.com | Github

EDUCATION
Hanoi University of Science and Technology – HUST
Major: Computer Science – CPA: 3.47/4.0
09/2025 – Present

SKILLS
Programming: Python, C/C++
AI/ML: PyTorch, Scikit-learn, Hugging Face Transformers

PROJECTS
MEdPilot – AI Dermatology Diagnosis Support Suite
Team Project; Lead + AI Engineer | FastAPI, React, Qwen2.5
"""
    
    config = ExtractionConfig(use_ollama=True)
    extractor = CVExtractor(config)
    
    result = extractor.extract(sample_text)
    print(json.dumps(result, indent=2, ensure_ascii=False))
