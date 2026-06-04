import re
from typing import Dict, List, Any


class CareerProfileBuilder:
    """Xây dựng hồ sơ nghề nghiệp từ dữ liệu CV đã trích xuất."""

    def build(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Xây dựng career profile từ structured data.

        Args:
            structured_data: Dict với key là tên section, value là list các dòng string
                             (output từ SectionDetector.detect_sections)

        Returns:
            Dict chứa career profile
        """
        if not isinstance(structured_data, dict):
            structured_data = {}

        profile = {
            "current_role": "Unknown",
            "career_stage": "Entry",
            "experience_years": 0.0,
            "domains": [],
            "skills": [],
            "technology_stack": [],
            "summary": ""
        }

        # --- Xử lý personal_info ---
        personal_info_lines = structured_data.get('personal_info', [])
        if isinstance(personal_info_lines, list) and personal_info_lines:
            # Dòng đầu tiên thường là tên
            name = personal_info_lines[0].strip() if personal_info_lines else ""
            if name:
                profile['summary'] = f"{name} - Ứng viên tiềm năng"

        # Nếu personal_info là dict (từ nguồn khác)
        elif isinstance(personal_info_lines, dict):
            name = personal_info_lines.get('name', '')
            if name:
                profile['summary'] = f"{name} - Ứng viên tiềm năng"

        # --- Xử lý education ---
        education_lines = structured_data.get('education', [])
        if isinstance(education_lines, list) and education_lines:
            edu_text = ' '.join(education_lines).lower()
            if 'present' in edu_text or 'hiện tại' in edu_text or 'nay' in edu_text:
                profile['career_stage'] = "Student"
            elif any(kw in edu_text for kw in ['university', 'học viện', 'trường', 'viện']):
                profile['career_stage'] = "Student"

        # --- Xử lý experience ---
        experience_lines = structured_data.get('experience', [])
        if isinstance(experience_lines, list) and experience_lines:
            exp_text = ' '.join(experience_lines)
            # Đếm số năm kinh nghiệm từ text
            years_match = re.search(r'(\d+\.?\d*)\s*(?:năm|year)', exp_text.lower())
            if years_match:
                profile['experience_years'] = float(years_match.group(1))

            # Xác định role từ dòng đầu tiên của experience
            if experience_lines:
                first_line = experience_lines[0].strip()
                # Thường dòng đầu chứa vị trí hoặc công ty
                if first_line:
                    profile['current_role'] = first_line[:100]  # Giới hạn độ dài

            # Nếu đang đi làm thì không còn là Student
            if profile['experience_years'] > 0:
                if profile['career_stage'] == "Student":
                    profile['career_stage'] = "Intern/Junior"

        # --- Xử lý skills ---
        skills_lines = structured_data.get('skills', [])
        all_skills = []

        if isinstance(skills_lines, list):
            for line in skills_lines:
                if isinstance(line, str):
                    # Parse skills từ dòng text (có thể có format "Category: skill1, skill2")
                    if ':' in line:
                        _, items = line.split(':', 1)
                        skills = [s.strip() for s in re.split(r'[;,]', items) if s.strip()]
                        all_skills.extend(skills)
                    else:
                        # Split bởi dấu phẩy hoặc chấm phẩy
                        skills = [s.strip() for s in re.split(r'[;,]', line) if s.strip()]
                        all_skills.extend(skills)
                elif isinstance(line, dict):
                    # Nếu skill đã được parse thành dict
                    if 'name' in line:
                        all_skills.append(line['name'])
                    elif 'skills' in line and isinstance(line['skills'], list):
                        all_skills.extend(line['skills'])

        # Loại bỏ trùng lặp và rỗng
        all_skills = list(dict.fromkeys([s for s in all_skills if s]))
        profile['skills'] = all_skills
        profile['technology_stack'] = list(set(all_skills))

        # --- Phân loại lĩnh vực ---
        skills_lower = [s.lower() for s in all_skills]
        domains = []

        if any(any(kw in s for kw in ['ai', 'ml', 'machine learning', 'deep learning', 'nlp', 'llm', 'rag', 'transformer', 'pytorch', 'tensorflow']) for s in skills_lower):
            domains.append("AI/ML")
        if any(any(kw in s for kw in ['backend', 'api', 'fastapi', 'flask', 'django', 'spring', 'nodejs', 'express']) for s in skills_lower):
            domains.append("Backend Development")
        if any(any(kw in s for kw in ['frontend', 'react', 'vue', 'angular', 'html', 'css', 'javascript', 'typescript']) for s in skills_lower):
            domains.append("Frontend Development")
        if any(any(kw in s for kw in ['data', 'analysis', 'pandas', 'numpy', 'sql', 'database', 'big data']) for s in skills_lower):
            domains.append("Data Science")
        if any(any(kw in s for kw in ['devops', 'docker', 'kubernetes', 'ci/cd', 'aws', 'azure', 'gcp']) for s in skills_lower):
            domains.append("DevOps/Cloud")
        if any(any(kw in s for kw in ['healthcare', 'medical', 'y tế', 'sức khỏe']) for s in skills_lower):
            domains.append("Healthcare Tech")

        profile['domains'] = domains

        # --- Cập nhật summary nếu có thông tin tốt hơn ---
        if profile['domains']:
            domain_str = ', '.join(profile['domains'])
            if profile['summary']:
                profile['summary'] += f" | Lĩnh vực: {domain_str}"
            else:
                profile['summary'] = f"Lĩnh vực chuyên môn: {domain_str}"

        return profile
