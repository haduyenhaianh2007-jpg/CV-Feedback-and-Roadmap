# REPLACEMENT_GUIDE.md — Hướng dẫn chạy với CV khác

## 📋 Mục lục

1. [Cách 1: Edit file test_real_cv.py](#cách-1-edit-file-test_real_cvpy)
2. [Cách 2: Tạo script mới](#cách-2-tạo-script-mới)
3. [Cách 3: Dùng API trực tiếp](#cách-3-dùng-api-trực-tiếp)
4. [Customizing Feedback](#customizing-feedback)
5. [Adding Custom Skills](#adding-custom-skills)
6. [Changing Target Role](#changing-target-role)
7. [Ví dụ hoàn chỉnh](#ví-dụ-hoàn-chỉnh)

---

## Cách 1: Edit file test_real_cv.py

**Đơn giản nhất** - chỉ cần thay skills và role.

### Bước 1: Mở file

```bash
# Edit file
nano examples/test_real_cv.py
# hoặc
code examples/test_real_cv.py
```

### Bước 2: Thay thế skills và role

```python
# Dòng 15-20: Thay skills của bạn
RESUME_SKILLS = [
    "Python", "Machine Learning", "TensorFlow",
    "SQL", "Docker", "AWS"
]

# Dòng 25: Thay target role
TARGET_ROLE = "AI Engineer"
```

### Bước 3: Chạy

```bash
python examples/test_real_cv.py
```

---

## Cách 2: Tạo script mới

**Linh hoạt hơn** - có thể custom logic.

### Tạo file mới

```python
# File: my_cv_analysis.py

from skill_gap.skill_gap_engine import SkillGapEngine
from skill_gap.feedback_generator import FeedbackGenerator
from skill_gap.local_llm import LocalLLMClient

def analyze_my_cv():
    # 1. Define your CV
    resume_skills = [
        "Python", "JavaScript", "React", "Node.js",
        "MongoDB", "PostgreSQL", "Docker", "AWS"
    ]
    target_role = "Full-stack Developer"
    
    # 2. Analyze
    engine = SkillGapEngine()
    analysis = engine.analyze(
        resume_skills=resume_skills,
        target_role=target_role,
        max_improvement_actions=5
    )
    
    # 3. Print results
    print(f"Readiness: {analysis['readiness_score']}%")
    print(f"Strengths: {len(analysis['strengths'])}")
    print(f"Critical gaps: {len(analysis['critical_gaps'])}")
    
    # 4. Generate feedback
    generator = FeedbackGenerator()
    prompt = generator.generate_prompt(analysis)
    
    client = LocalLLMClient()
    feedback = client.generate(prompt)
    
    print("\n" + "="*70)
    print("FEEDBACK")
    print("="*70)
    print(feedback)

if __name__ == "__main__":
    analyze_my_cv()
```

### Chạy

```bash
python my_cv_analysis.py
```

---

## Cách 3: Dùng API trực tiếp

**Advanced** - tích hợp vào ứng dụng khác.

### Extract skills từ CV text

```python
from knowledge_base._08_knowledge_api import extract_skills

cv_text = """
Tôi là Full-stack Developer với 3 năm kinh nghiệm.
Kỹ năng: Python, Django, React, Node.js, PostgreSQL, MongoDB.
Kinh nghiệm với Docker, AWS, CI/CD.
"""

skills = extract_skills(cv_text)
print(f"Extracted skills: {skills}")
# Output: ['AWS', 'CI/CD', 'Django', 'Docker', 'MongoDB',
#          'Node.js', 'PostgreSQL', 'Python', 'React']
```

### Analyze skill gap

```python
from skill_gap.skill_gap_engine import SkillGapEngine

engine = SkillGapEngine()

analysis = engine.analyze(
    resume_skills=skills,
    target_role="Full-stack Developer"
)

# Access results
readiness = analysis['readiness_score']
strengths = analysis['strengths']
critical_gaps = analysis['critical_gaps']
medium_gaps = analysis['medium_gaps']

print(f"Readiness: {readiness}%")
for gap in critical_gaps:
    print(f"Critical: {gap['skill']} ({gap['frequency']}%)")
```

---

## Customizing Feedback

### Thay đổi prompt template

**File**: `skill_gap/prompts/skill_gap_feedback.txt`

```text
# Original
You are a career advisor. Generate feedback based on the analysis.

# Modified - stricter
You are a strict career advisor. 
ONLY use skills from the JSON below.
DO NOT hallucinate or add skills not in the JSON.
If a skill is not mentioned, say "not provided".

## Analysis
{{ANALYSIS_JSON}}

## Output Format
1. Overall Assessment (readiness score + summary)
2. Strengths (top 3-5 skills with frequency)
3. Critical Gaps (must fix, with actions + timeline)
4. Medium Gaps (should fix, with actions + timeline)
5. Recommended Learning Path (ordered steps)
```

### Dùng LLM khác

**File**: `skill_gap/local_llm.py`

```python
class LocalLLMClient:
    def __init__(
        self,
        model: str = "qwen2.5:7b",  # Change here
        base_url: str = "http://localhost:11434",
        temperature: float = 0.0,
        max_tokens: int = 2000
    ):
        self.model = model
        # ...

# Usage with different model
client = LocalLLMClient(model="qwen2.5:14b")  # Larger model
# or
client = LocalLLMClient(model="llama3:8b")    # Different model
```

### Thay đổi temperature

```python
# Temperature = 0.0 (deterministic, no creativity)
client = LocalLLMClient(temperature=0.0)

# Temperature = 0.7 (balanced)
client = LocalLLMClient(temperature=0.7)

# Temperature = 1.0 (creative, may hallucinate)
client = LocalLLMClient(temperature=1.0)
```

---

## Adding Custom Skills

### Thêm vào ontology

**File**: `knowledge_base/config.py`

```python
# Add to MANUAL_ALIASES dict
MANUAL_ALIASES = {
    # ... existing aliases ...
    
    # Your custom skill
    "custom_skill": "Custom Skill",
    "cs": "Custom Skill",
    "custom-skill": "Custom Skill",
}
```

### Hoặc edit trực tiếp ontology

**File**: `knowledge_base/outputs/skill_ontology.json`

```json
{
  "python": "Python",
  "py": "Python",
  "custom_skill": "Custom Skill",
  "cs": "Custom Skill"
}
```

### Thêm vào skill relationships

**File**: `skill_gap/skill_relationships.json`

```json
{
  "skills": {
    "Custom Skill": {
      "category": "Your Category",
      "prerequisites": ["Python", "Basic Skill"],
      "related": ["Related Skill 1", "Related Skill 2"],
      "leads_to": ["Advanced Custom Skill"]
    }
  }
}
```

---

## Changing Target Role

### Xem danh sách roles có sẵn

```python
import pandas as pd
from knowledge_base.config import ROLE_SKILL_MATRIX_PATH

df = pd.read_csv(ROLE_SKILL_MATRIX_PATH)
roles = df['role'].unique()

print("Available roles:")
for role in sorted(roles):
    print(f"  - {role}")

# Output:
# Available roles:
#   - AI Engineer
#   - Backend Developer
#   - Data Analyst
#   - Data Scientist
#   - DevOps Engineer
#   - Frontend Developer
#   - Full-stack Developer
#   - Mobile Developer
#   - Product Manager
#   - QA Engineer
```

### Thêm role mới

**File**: `knowledge_base/outputs/role_skill_matrix.csv`

```csv
role,skill,frequency_pct,count,total_jobs_in_role
Custom Role,Python,80.0,8,10
Custom Role,Docker,60.0,6,10
Custom Role,AWS,50.0,5,10
```

**Hoặc rebuild từ data**:

```bash
cd "C:/CV feedback and roadmap/knowledge_base"
python run_pipeline.py
```

---

## Ví dụ hoàn chỉnh

### Ví dụ 1: Frontend Developer

```python
# frontend_analysis.py

from skill_gap.skill_gap_engine import SkillGapEngine
from skill_gap.feedback_generator import FeedbackGenerator
from skill_gap.local_llm import LocalLLMClient

resume_skills = [
    "HTML", "CSS", "JavaScript", "TypeScript",
    "React", "Vue.js", "Tailwind CSS",
    "Git", "REST API"
]
target_role = "Frontend Developer"

engine = SkillGapEngine()
analysis = engine.analyze(
    resume_skills=resume_skills,
    target_role=target_role
)

generator = FeedbackGenerator()
prompt = generator.generate_prompt(analysis)

client = LocalLLMClient()
feedback = client.generate(prompt)

print(feedback)
```

### Ví dụ 2: Data Scientist

```python
# data_scientist_analysis.py

from knowledge_base._08_knowledge_api import extract_skills
from skill_gap.skill_gap_engine import SkillGapEngine
from skill_gap.feedback_generator import FeedbackGenerator
from skill_gap.local_llm import LocalLLMClient

# Extract from CV text
cv_text = """
Data Scientist with 2 years experience.
Skills: Python, R, SQL, Pandas, NumPy, Scikit-learn,
Machine Learning, Statistics, Tableau.
"""

skills = extract_skills(cv_text)

engine = SkillGapEngine()
analysis = engine.analyze(
    resume_skills=skills,
    target_role="Data Scientist"
)

generator = FeedbackGenerator()
prompt = generator.generate_prompt(analysis)

client = LocalLLMClient(temperature=0.0)
feedback = client.generate(prompt)

print(feedback)
```

### Ví dụ 3: DevOps Engineer

```python
# devops_analysis.py

from skill_gap.skill_gap_engine import SkillGapEngine
from skill_gap.feedback_generator import FeedbackGenerator
from skill_gap.local_llm import LocalLLMClient
from skill_gap.feedback_evaluator import FeedbackEvaluator
import json

resume_skills = [
    "Linux", "Docker", "Kubernetes",
    "AWS", "Terraform", "Jenkins",
    "Python", "Bash", "Git"
]
target_role = "DevOps Engineer"

engine = SkillGapEngine()
analysis = engine.analyze(
    resume_skills=resume_skills,
    target_role=target_role
)

generator = FeedbackGenerator()
prompt = generator.generate_prompt(analysis)

# Extract source JSON
json_start = prompt.find('{')
json_end = prompt.rfind('}') + 1
source_json = json.loads(prompt[json_start:json_end])

client = LocalLLMClient()
feedback = client.generate(prompt)

# Evaluate
evaluator = FeedbackEvaluator()
result = evaluator.evaluate(source_json, feedback)

print(f"Hallucination Rate: {result['hallucination_rate']:.2%}")
print(f"Overall Score: {result['overall_score']:.2f} / 1.00")
print("\n" + feedback)
```

---

## Debugging Tips

### Xem chi tiết analysis

```python
engine = SkillGapEngine()
analysis = engine.analyze(resume_skills, target_role)

# Print full analysis
import json
print(json.dumps(analysis, indent=2, ensure_ascii=False))
```

### Kiểm tra skill normalization

```python
from skill_gap.skill_normalization import SkillNormalizer
from knowledge_base.config import SKILL_ONTOLOGY_PATH

normalizer = SkillNormalizer(str(SKILL_ONTOLOGY_PATH))

matched, unknown = normalizer.get_canonical_names([
    "python", "py", "Python 3",
    "machine learning", "ml",
    "unknown_skill"
])

print(f"Matched: {matched}")
print(f"Unknown: {unknown}")
```

### Kiểm tra graph insights

```python
engine = SkillGapEngine()
analysis = engine.analyze(resume_skills, target_role)

print("Graph Insights:")
print(json.dumps(analysis['graph_insights'], indent=2))
```

---

## Resources

- **Main README**: [README.md](README.md)
- **Usage Guide**: [USAGE.md](USAGE.md)
- **Examples**: `examples/`

---

**Last updated**: June 8, 2026
