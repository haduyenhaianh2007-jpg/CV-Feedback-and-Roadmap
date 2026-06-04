import re
from typing import List, Dict, Optional

def group_project_blocks(blocks):
    """Gom các block thuộc cùng 1 dự án"""
    grouped = []
    current_project = None

    for block in blocks:
        # Phát hiện đầu dự án (có dấu • hoặc tên dự án in đậm)
        is_new_project = (
            block.text.startswith(('•', '-', '*')) or
            re.match(r'^[A-Z][\w\s]+(?:–|:)', block.text)
        )

        if is_new_project:
            if current_project:
                grouped.append(current_project)
            current_project = [block]
        elif current_project and block.text.strip():
            # Kiểm tra nếu block tiếp theo thuộc dự án hiện tại
            current_project.append(block)

    if current_project:
        grouped.append(current_project)

    return grouped

class ProjectExtractor:
    def extract(self, blocks):
        projects = []
        for project_blocks in group_project_blocks(blocks):
            # Tách tên dự án từ dòng đầu tiên
            name_line = project_blocks[0].text.strip('•- *')

            # Xác định role từ các dòng tiếp theo
            role = ""
            tech_stack = []
            description = []

            for i, block in enumerate(project_blocks[1:]):
                text = block.text.strip()
                if "role" in text.lower() or "position" in text.lower():
                    role = text
                elif any(kw in text.lower() for kw in ["python", "fastapi", "pytorch"]):
                    tech_stack = [tech.strip() for tech in text.split(',')]
                else:
                    description.append(text)

            projects.append({
                "name": name_line,
                "role": role,
                "description": " ".join(description),
                "technologies": tech_stack
            })
        return projects