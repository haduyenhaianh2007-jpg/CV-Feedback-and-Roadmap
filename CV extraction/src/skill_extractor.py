import re
class SkillExtractor:
    def __init__(self):
        self.categories = {
            'programming': ['python', 'c/c++', 'java', 'javascript', 'typescript', 'cpp'],
            'ai_ml': ['pytorch', 'transformers', 'nlp', 'llm', 'rag', 'computer vision', 'hugging face', 'phobert', 'gpt', 'gemini'],
            'frameworks': ['fastapi', 'react', 'streamlit', 'pandas', 'numpy', 'scikit-learn', 'opencv', 'matplot', 'kare'],
            'tools': ['git', 'github', 'docker', 'kaggle', 'jupyter', 'colab', 'latex', 'overleaf', 'vllm', 'chromadb']
        }

    def extract(self, text):
        skills = []
        for line in text.split('\n'):
            if not line.strip():
                continue
            if ':' in line:
                category, items = line.split(':', 1)
                for skill in self._parse_skills(items):
                    skills.append({
                        'name': skill,
                        'category': category.strip().title()
                    })
            else:
                for skill in self._parse_skills(line):
                    category = self._categorize_skill(skill)
                    skills.append({
                        'name': skill,
                        'category': category
                    })
        return skills

    def normalize_skills(self, skills_data):
        if isinstance(skills_data, list):
            text = '\n'.join(skills_data)
        else:
            text = skills_data
        return self.extract(text)

    def process_project_technologies(self, project_data):
        """Xử lý và trích xuất công nghệ từ dự án"""
        if isinstance(project_data, dict):
            return project_data.get('technologies', [])
        elif isinstance(project_data, str):
            return [s.strip() for s in re.split(r'[;,]', project_data) if s.strip()]
        else:
            return []

    def _parse_skills(self, text):
        return [s.strip() for s in re.split(r'[;,]', text) if s.strip()]

    def _categorize_skill(self, skill_name):
        skill_lower = skill_name.lower().replace('•', '').strip()
        for category, keywords in self.categories.items():
            if any(kw in skill_lower for kw in keywords):
                return category.replace('_', ' ').title()
        if any(x in skill_lower for x in ['python', 'java', 'c++', 'javascript']):
            return "Programming Language"
        if any(x in skill_lower for x in ['pytorch', 'transformers', 'nlp']):
            return "AI/ML"
        return "General"
