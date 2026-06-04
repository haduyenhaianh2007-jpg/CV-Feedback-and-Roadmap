import re


class SectionDetector:
    """Detect và phân loại các section trong CV text."""

    def __init__(self):
        # Từ khóa section tiếng Việt & Anh (ưu tiên thứ tự khớp)
        self.section_keywords = {
            'personal_info': ['contact', 'personal information', 'liên hệ', 'thông tin cá nhân'],
            'summary': ['summary', 'objective', 'profile', 'mục tiêu', 'tổng quan', 'giới thiệu', 'about me'],
            'education': ['education', 'học vấn', 'academic', 'giáo dục', 'trình độ học vấn'],
            'experience': ['experience', 'work experience', 'kinh nghiệm', 'công việc', 'thực tập',
                           'activities', 'hoạt động', 'experience & activities', 'làm việc'],
            'projects': ['projects', 'dự án', 'research', 'nghiên cứu', 'sản phẩm', 'portfolio'],
            'skills': ['skills', 'kỹ năng', 'technical skills', 'công nghệ', 'chuyên môn', 'competencies'],
            'certifications': ['certifications', 'chứng chỉ', 'licenses', 'giấy chứng nhận'],
            'achievements': ['achievements', 'awards', 'giải thưởng', 'thành tích', 'khen thưởng',
                             'showcase', 'competition', 'honors'],
        }

    def detect_sections(self, text):
        """
        Phân tách CV text thành các section.

        Args:
            text: String nội dung CV (đã extract từ PDF)

        Returns:
            Dict với key là tên section chuẩn, value là list các dòng nội dung
        """
        if not isinstance(text, str):
            return {key: [] for key in self.section_keywords}

        lines = text.split('\n')
        sections = {key: [] for key in self.section_keywords}
        current_section = None

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Kiểm tra xem dòng này có phải tiêu đề section không
            matched_section = self._match_section(stripped)
            if matched_section and self._is_likely_header(stripped):
                current_section = matched_section
                continue

            # Thêm nội dung vào section hiện tại
            if current_section:
                sections[current_section].append(stripped)
            else:
                # Nội dung trước section đầu tiên → personal_info
                sections['personal_info'].append(stripped)

        return sections

    def normalize_section_names(self, sections):
        """
        Chuẩn hóa tên các section về dạng chuẩn.
        Gộp các section trùng lặp và loại bỏ section rỗng.
        """
        normalized = {key: [] for key in self.section_keywords}

        for section_name, content in sections.items():
            if not content:
                continue

            # Nếu đã là key chuẩn, giữ nguyên
            if section_name in normalized:
                normalized[section_name].extend(content)
            else:
                # Thử ánh xạ về section chuẩn
                matched = self._match_section(section_name)
                if matched:
                    normalized[matched].extend(content)
                else:
                    # Giữ nguyên nếu không khớp (ví dụ: custom section)
                    normalized.setdefault(section_name, []).extend(content)

        return normalized

    def _is_likely_header(self, text):
        """Kiểm tra xem text có phải tiêu đề section không."""
        # Tiêu đề thường ngắn (< 60 ký tự), không chứa dấu câu phức tạp
        if len(text) > 60:
            return False
        # Không phải header nếu chứa nhiều dấu phẩy/chấm (có vẻ là nội dung)
        if text.count(',') > 2 or text.count('.') > 1:
            return False
        return True

    def _match_section(self, text):
        """Xác định tên section chuẩn từ text."""
        text_lower = text.lower().strip().rstrip(':').strip()
        for section, keywords in self.section_keywords.items():
            for kw in keywords:
                if kw in text_lower:
                    return section
        return None

    def extract_personal_info(self, sections):
        """Trích xuất thông tin cá nhân từ các section."""
        personal_info = {}
        content_list = sections.get('personal_info', [])
        if not content_list:
            return personal_info

        text = '\n'.join(content_list) if isinstance(content_list, list) else str(content_list)

        # Tên thường là dòng đầu tiên
        if content_list:
            personal_info['name'] = content_list[0].strip()

        # Email
        email_match = re.search(r'[\w\.\-]+@[\w\.\-]+\.\w+', text)
        if email_match:
            personal_info['email'] = email_match.group(0)

        # Số điện thoại
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3}[-.\s]?\d{3,4}', text)
        if phone_match:
            personal_info['phone'] = phone_match.group(0)

        # GitHub
        github_match = re.search(r'github\.com/[\w\-\.]+', text, re.IGNORECASE)
        if github_match:
            personal_info['github'] = github_match.group(0)

        # LinkedIn
        linkedin_match = re.search(r'linkedin\.com/in/[\w\-\.]+', text, re.IGNORECASE)
        if linkedin_match:
            personal_info['linkedin'] = linkedin_match.group(0)

        return personal_info

    def extract_education(self, sections):
        """Trích xuất thông tin học vấn từ sections."""
        education_list = []
        content = sections.get('education', [])
        if not content:
            return education_list

        text = '\n'.join(content) if isinstance(content, list) else str(content)
        lines = text.split('\n')

        education = {
            'institution': '',
            'degree': '',
            'field': '',
            'start_date': '',
            'end_date': '',
            'gpa': ''
        }

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue

            # Dòng chứa tên trường (thường là dòng đầu hoặc chứa "University"/"Học viện")
            if any(kw in line_stripped.lower() for kw in ['university', 'học viện', 'trường', 'viện']):
                education['institution'] = line_stripped
            elif re.search(r'\d+\.\d+/\d+', line_stripped):
                # GPA pattern: 3.47/4.0
                gpa_match = re.search(r'(\d+\.\d+/\d+\.\d+)', line_stripped)
                if gpa_match:
                    education['gpa'] = gpa_match.group(1)
            elif re.search(r'\d{2}/\d{4}', line_stripped):
                # Date pattern: 09/2025 - Present
                date_match = re.findall(r'\d{2}/\d{4}|Present|Hiện tại', line_stripped, re.IGNORECASE)
                if len(date_match) >= 2:
                    education['start_date'] = date_match[0]
                    education['end_date'] = date_match[1]
                elif len(date_match) == 1:
                    education['end_date'] = date_match[0]
            elif any(kw in line_stripped.lower() for kw in ['major', 'chuyên ngành', 'ngành']):
                field_match = re.split(r'[:\-–]', line_stripped, maxsplit=1)
                if len(field_match) > 1:
                    education['field'] = field_match[1].strip()

        if education['institution']:
            education_list.append(education)

        return education_list
