"""
CV Text Cleaner - Handle OCR/PDF newlines intelligently
Preserves structure while merging broken lines
"""

import re
from typing import List, Tuple, Optional


class CVTextCleaner:
    """Clean CV text from OCR/PDF while preserving structure"""
    
    # Section headers in Vietnamese & English
    SECTION_HEADERS = {
        # Vietnamese
        'GIÁO DỤC', 'EDUCATION', 'KINH NGHIỆM', 'EXPERIENCE',
        'KỸ NĂNG', 'SKILLS', 'DỰ ÁN', 'PROJECTS', 'AWARDS',
        'GIẢI THƯỞNG', 'CHỨNG CHỈ', 'CERTIFICATIONS',
        'HOẠT ĐỘNG', 'ACTIVITIES', 'NGÔN NGỮ', 'LANGUAGES',
        'ĐẠI HỌC', 'CÔNG VIỆC', 'NHÀ TUYỂN DỤNG',
        'CUỘC THI', 'COMPETITIONS', 'THÀNH Tích', 'ACHIEVEMENTS',
        'THÔNG TIN CÁ NHÂN', 'PERSONAL INFO', 'TÓM TẮT',
        'SUMMARY', 'LIÊN HỆ', 'CONTACT', 'LIÊN KẾT', 'LINKS'
    }
    
    # Bullet point patterns
    BULLET_PATTERNS = [
        r'^\s*[•\-\*]\s+',  # •, -, *
        r'^\s*\d+\.\s+',     # 1., 2.,
        r'^\s*[a-zA-Z]\.\s+', # a., b.,
    ]
    
    # Date patterns to detect line breaks
    DATE_PATTERNS = [
        r'\d{1,2}/\d{4}',           # 09/2025
        r'\d{4}-\d{2}',              # 2025-09
        r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}',
        r'(Tháng|Năm|January|February)',
    ]
    
    def __init__(self, aggressive_merge: bool = False):
        """
        Args:
            aggressive_merge: If True, aggressively merge lines. If False, conservative.
        """
        self.aggressive_merge = aggressive_merge
        self.compiled_bullets = [re.compile(p) for p in self.BULLET_PATTERNS]
        self.compiled_dates = [re.compile(p, re.IGNORECASE) for p in self.DATE_PATTERNS]
    
    def clean(self, text: str) -> str:
        """
        Main cleaning pipeline:
        1. Split into lines
        2. Detect sections
        3. Merge broken lines
        4. Clean whitespace
        """
        if not text:
            return ""
        
        lines = text.split('\n')
        cleaned_lines = self._merge_lines(lines)
        
        # Remove extra whitespace
        cleaned_lines = [line.strip() for line in cleaned_lines]
        cleaned_lines = [line for line in cleaned_lines if line]
        
        return '\n'.join(cleaned_lines)
    
    def _is_section_header(self, line: str) -> bool:
        """Check if line is a section header"""
        line_upper = line.strip().upper()
        
        # Exact match in headers
        if line_upper in self.SECTION_HEADERS:
            return True
        
        # Check if line is mostly uppercase (section-like)
        if len(line_upper) > 2:
            upper_ratio = sum(1 for c in line if c.isupper()) / len(line)
            if upper_ratio > 0.7:
                return True
        
        return False
    
    def _is_bullet_line(self, line: str) -> bool:
        """Check if line starts with bullet point"""
        stripped = line.lstrip()
        for pattern in self.compiled_bullets:
            if pattern.match(stripped):
                return True
        return False
    
    def _ends_incomplete(self, line: str) -> bool:
        """Check if line ends incomplete (no punctuation)"""
        line = line.strip()
        if not line:
            return False
        
        # Line ends with incomplete punctuation
        incomplete_endings = (',', '-', 'and', 'or', '&', ';')
        return any(line.lower().endswith(end) for end in incomplete_endings) or not line[-1] in '.!?);'
    
    def _is_short_line(self, line: str) -> bool:
        """Check if line is unusually short (might be continuation)"""
        words = len(line.split())
        return words < 3 and len(line.strip()) > 0
    
    def _has_date(self, line: str) -> bool:
        """Check if line contains date pattern"""
        for pattern in self.compiled_dates:
            if pattern.search(line):
                return True
        return False
    
    def _merge_lines(self, lines: List[str]) -> List[str]:
        """
        Merge lines intelligently based on context
        """
        if not lines:
            return []
        
        merged = []
        i = 0
        
        while i < len(lines):
            current = lines[i].strip()
            
            # Empty line - keep as separator
            if not current:
                if merged and merged[-1]:  # Only add if previous line exists
                    merged.append('')
                i += 1
                continue
            
            # Section header - always keep
            if self._is_section_header(current):
                if merged and merged[-1] != '':
                    merged.append('')  # Add separator before header
                merged.append(current)
                i += 1
                continue
            
            # Bullet line - keep as is
            if self._is_bullet_line(current):
                merged.append(current)
                i += 1
                continue
            
            # Try to merge with next line
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                if next_line and not self._is_section_header(next_line) and not self._is_bullet_line(next_line):
                    # Merge conditions:
                    # 1. Current line ends incomplete
                    # 2. Next line is very short
                    # 3. Current doesn't have date ending
                    
                    should_merge = False
                    
                    if self._ends_incomplete(current):
                        should_merge = True
                    elif self._is_short_line(next_line) and not self._has_date(current):
                        should_merge = True
                    elif not current[-1] in '.!?;:' and self._is_short_line(next_line):
                        should_merge = True
                    
                    if should_merge:
                        merged.append(f"{current} {next_line}")
                        i += 2
                        continue
            
            # Default: add current line
            merged.append(current)
            i += 1
        
        return merged
    
    def get_sections(self, text: str) -> dict:
        """
        Split cleaned text into sections
        Returns: {"EDUCATION": "...", "EXPERIENCE": "...", ...}
        """
        cleaned = self.clean(text)
        lines = cleaned.split('\n')
        
        sections = {}
        current_section = None
        current_content = []
        
        for line in lines:
            if self._is_section_header(line):
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = line.strip().upper()
                current_content = []
            else:
                if current_section:
                    current_content.append(line)
        
        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections
    
    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize internal whitespace"""
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove trailing spaces
        text = re.sub(r'\s+$', '', text, flags=re.MULTILINE)
        return text.strip()


# Utility functions
def clean_cv_text(text: str, aggressive: bool = False) -> str:
    """Quick function to clean CV text"""
    cleaner = CVTextCleaner(aggressive_merge=aggressive)
    return cleaner.clean(text)


def split_cv_sections(text: str) -> dict:
    """Quick function to split text into sections"""
    cleaner = CVTextCleaner()
    return cleaner.get_sections(text)
