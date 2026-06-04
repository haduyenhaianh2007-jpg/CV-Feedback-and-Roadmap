"""
Regex Extraction Layer - Extract deterministic fields
Email, Phone, Links, etc.
"""

import re
from typing import Optional, List, Dict


class RegexExtractor:
    """Extract structured data using regex patterns"""
    
    # Email pattern
    EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    
    # Phone patterns (Vietnamese + International)
    PHONE_PATTERNS = [
        r'\+84[\s\-]?[0-9]{1,2}[\s\-]?[0-9]{3,4}[\s\-]?[0-9]{3,4}',  # +84 ...
        r'0[0-9]{1,2}[\s\-]?[0-9]{3,4}[\s\-]?[0-9]{3,4}',  # 0... (VN local)
        r'\+[0-9]{1,3}[\s\-]?[0-9]{6,14}',  # International
    ]
    
    # URL patterns
    GITHUB_PATTERN = r'(?:https?://)?(?:www\.)?github\.com/[a-zA-Z0-9._-]+'
    LINKEDIN_PATTERN = r'(?:https?://)?(?:www\.)?linkedin\.com/in/[a-zA-Z0-9._-]+'
    URL_PATTERN = r'https?://[^\s]+'
    
    # GPA/Score patterns
    GPA_PATTERN = r'\b(?:GPA|CPA|CGPA)[\s:]*([0-9]+\.[0-9]{2})/([0-9]+\.[0-9]{1,2})\b'
    
    @staticmethod
    def extract_email(text: str) -> Optional[str]:
        """Extract first email from text"""
        match = re.search(RegexExtractor.EMAIL_PATTERN, text)
        return match.group(0) if match else None
    
    @staticmethod
    def extract_phone(text: str) -> Optional[str]:
        """Extract first phone number from text"""
        for pattern in RegexExtractor.PHONE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
    
    @staticmethod
    def extract_github(text: str) -> Optional[str]:
        """Extract GitHub profile URL"""
        match = re.search(RegexExtractor.GITHUB_PATTERN, text)
        if match:
            url = match.group(0)
            if not url.startswith('http'):
                url = 'https://' + url
            return url
        return None
    
    @staticmethod
    def extract_linkedin(text: str) -> Optional[str]:
        """Extract LinkedIn profile URL"""
        match = re.search(RegexExtractor.LINKEDIN_PATTERN, text)
        if match:
            url = match.group(0)
            if not url.startswith('http'):
                url = 'https://' + url
            return url
        return None
    
    @staticmethod
    def extract_urls(text: str) -> List[str]:
        """Extract all URLs from text"""
        return re.findall(RegexExtractor.URL_PATTERN, text)
    
    @staticmethod
    def extract_gpa(text: str) -> Optional[str]:
        """Extract GPA/CPA from text"""
        match = re.search(RegexExtractor.GPA_PATTERN, text, re.IGNORECASE)
        if match:
            return f"{match.group(1)}/{match.group(2)}"
        return None
    
    @staticmethod
    def extract_all_personal_info(text: str) -> Dict[str, any]:
        """Extract all personal info deterministically"""
        return {
            'email': RegexExtractor.extract_email(text),
            'phone': RegexExtractor.extract_phone(text),
            'github': RegexExtractor.extract_github(text),
            'linkedin': RegexExtractor.extract_linkedin(text),
        }
