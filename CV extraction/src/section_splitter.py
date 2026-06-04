"""
Section Splitter - Divide CV text into logical sections
Handles both Vietnamese and English section headers
"""

import re
from typing import Dict, List, Tuple, Optional


class SectionSplitter:
    """Split CV text into structured sections"""
    
    # Section headers with aliases (Vietnamese & English)
    SECTION_PATTERNS = {
        'personal_info': r'(PERSONAL\s+INFO|THÔNG\s+TIN\s+CÁ\s+NHÂN|LIÊN\s+HỆ|CONTACT)',
        'summary': r'(SUMMARY|OBJECTIVE|TÓM\s+TẮT|GIỚI\s+THIỆU|MỤC\s+TIÊU)',
        'education': r'(EDUCATION|GIÁO\s+DỤC|ĐẠI\s+HỌC|ACADEMIC)',
        'skills': r'(SKILLS|KỸ\s+NĂNG|TECHNICAL|CÔNG\s+NGHỆ)',
        'experience': r'(EXPERIENCE\s+&\s+ACTIVITIES|EXPERIENCE|KINH\s+NGHIỆM|CÔNG\s+VIỆC|HOẠT\s+ĐỘNG)',
        'projects': r'(PROJECTS|DỰ\s+ÁN|RESEARCH|NGHIÊN\s+CỨU)',
        'achievements': r'(COMPETITION\s+AND\s+AWARD|AWARDS|GIẢI\s+THƯỞNG|THÀNH\s+TÍCH|CUỘC\s+THI)',
        'certifications': r'(CERTIFICATIONS|CHỨNG\s+CHỈ|CERTIFICATES)',
        'languages': r'(LANGUAGES|NGÔN\s+NGỮ)',
    }
    
    def __init__(self, case_insensitive: bool = True):
        """Initialize section splitter"""
        self.case_insensitive = case_insensitive
        flags = re.IGNORECASE | re.MULTILINE if case_insensitive else re.MULTILINE
        
        # Compile patterns
        self.compiled_patterns = {
            section: re.compile(pattern, flags)
            for section, pattern in self.SECTION_PATTERNS.items()
        }
    
    def split(self, text: str) -> Dict[str, str]:
        """
        Split text into sections
        
        Args:
            text: Full CV text
        
        Returns:
            Dictionary mapping section names to content
        """
        sections = {}
        
        # Find all section headers with their positions
        # Key fix: Track which sections we've already found to avoid duplicates
        header_positions = []
        sections_found = set()
        
        for section_name, pattern in self.compiled_patterns.items():
            for match in pattern.finditer(text):
                # Only add if we haven't found this section type yet
                # (ignore duplicate "Project", "education", "activity" inside content)
                if section_name not in sections_found:
                    header_positions.append({
                        'section': section_name,
                        'start': match.start(),
                        'end': match.end(),
                        'header': match.group()
                    })
                    sections_found.add(section_name)
                    break  # Only take first match for this section pattern
        
        # Sort by position
        header_positions.sort(key=lambda x: x['start'])
        
        # Extract section content
        for i, header_info in enumerate(header_positions):
            section_name = header_info['section']
            content_start = header_info['end']
            
            # Find next section start
            if i + 1 < len(header_positions):
                content_end = header_positions[i + 1]['start']
            else:
                content_end = len(text)
            
            # Extract content
            content = text[content_start:content_end].strip()
            
            # Clean up content
            content = self._clean_section_content(content)
            
            if content:
                sections[section_name] = content
        
        # Store remaining text (before first section)
        if header_positions:
            first_section_start = header_positions[0]['start']
            pre_text = text[:first_section_start].strip()
            if pre_text:
                sections['_pre_text'] = pre_text
        else:
            # No sections found, treat all as pre_text
            sections['_pre_text'] = text.strip()
        
        return sections
    
    def _clean_section_content(self, content: str) -> str:
        """
        Clean section content by removing extra whitespace
        while preserving bullet points and structure
        
        Args:
            content: Raw section content
        
        Returns:
            Cleaned content
        """
        # Split into lines
        lines = content.split('\n')
        
        # Remove empty lines at start/end
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        
        # Rejoin
        return '\n'.join(lines)
    
    def get_personal_info(self, pre_text: str) -> Dict[str, Optional[str]]:
        """
        Extract personal info from pre-text (before sections)
        
        Args:
            pre_text: Text before first section
        
        Returns:
            Personal info dictionary
        """
        from regex_extractor import RegexExtractor
        
        extractor = RegexExtractor()
        
        return {
            'name': self._extract_name(pre_text),
            'email': extractor.extract_email(pre_text),
            'phone': extractor.extract_phone(pre_text),
            'github': extractor.extract_github(pre_text),
            'linkedin': extractor.extract_linkedin(pre_text),
        }
    
    def extract_personal_info_header(self, text: str) -> str:
        """Extract the header part (personal info) before first major section"""
        # Find first section header
        first_match = None
        for section_name, pattern in self.compiled_patterns.items():
            match = pattern.search(text)
            if match and (first_match is None or match.start() < first_match.start()):
                first_match = match
        
        if first_match:
            return text[:first_match.start()].strip()
        else:
            # If no section found, return first 1000 chars
            return text[:1000].strip()
    
    def split_by_sections(self, text: str) -> Dict[str, str]:
        """
        Split CV into sections, alias for split()
        Returns: {"education": "...", "experience": "...", ...}
        """
        sections = self.split(text)
        
        # Remove the _pre_text key if present
        if '_pre_text' in sections:
            del sections['_pre_text']
        
        return sections
    
    def _extract_name(self, text: str) -> Optional[str]:
        """
        Extract name (usually first 1-2 lines before email/phone)
        
        Args:
            text: Pre-text content
        
        Returns:
            Name or None
        """
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            
            # Skip if line contains email, phone, or special symbols
            if any(x in line for x in ['@', '+', '|', '§', '—']):
                continue
            
            # Skip if too short
            if len(line) < 3:
                continue
            
            # Skip if looks like title
            if any(x in line.lower() for x in ['student', 'engineer', 'developer', 'candidate']):
                continue
            
            # Found likely name
            return line
        
        return None


def split_text_to_sections(text: str) -> Dict[str, str]:
    """
    Convenience function to split text into sections
    
    Args:
        text: Full CV text
    
    Returns:
        Dictionary of sections
    """
    splitter = SectionSplitter()
    return splitter.split(text)


if __name__ == "__main__":
    # Test
    sample_text = """
Ha Duyen Hai Anh
Computer Science Student
+(84) 971 190 707 | haduyenhaianh2007@gmail.com | Github

EDUCATION
Hanoi University of Science and Technology – HUST
Major: Computer Science – CPA: 3.47/4.0
09/2025 – Present

SKILLS
Programming: Python, C/C++
AI/ML: PyTorch, Scikit-learn

PROJECTS
MEdPilot – AI Dermatology Diagnosis Support Suite
Team Project; Lead + AI Engineer
"""
    
    sections = split_text_to_sections(sample_text)
    for section, content in sections.items():
        print(f"\n{'='*50}")
        print(f"SECTION: {section}")
        print(f"{'='*50}")
        print(content[:200] + "..." if len(content) > 200 else content)
