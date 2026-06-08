# USAGE.md — Hướng dẫn sử dụng KB+analysis+engine

## 📋 Mục lục

1. [Cài đặt môi trường](#1-cài-đặt-môi-trường)
2. [Xây dựng Knowledge Base](#2-xây-dựng-knowledge-base)
3. [Phân tích CV với Skill Gap Engine](#3-phân-tích-cv-với-skill-gap-engine)
4. [API Usage](#4-api-usage)
5. [Troubleshooting](#5-troubleshooting)

---

## 1. Cài đặt môi trường

### 1.1. Python & Dependencies

```bash
# Python 3.12+ (đã có trong .venv)
python --version

# Cài đặt dependencies
cd "C:/CV feedback and roadmap/KB+analysis+engine"
pip install -r requirements.txt
```

**requirements.txt**:
```
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
chromadb>=0.4.0
sentence-transformers>=2.2.0
requests>=2.31.0
openpyxl>=3.1.0
```

### 1.2. Ollama (Local LLM)

**Cài đặt Ollama**:
- Download: https://ollama.com/download
- Hoặc dùng curl: `curl -fsSL https://ollama.com/install.sh | sh`

**Kéo model Qwen2.5**:
```bash
ollama pull qwen2.5:7b
```

**Kiểm tra**:
```bash
ollama list
ollama run qwen2.5:7b "Hello"
```

---

## 2. Xây dựng Knowledge Base

### 2.1. Chuẩn bị data

Đặt data files vào thư mục `Data/`:
```
Data/
├── JD.csv                    # Job descriptions
├── Resume.csv                # CV samples
└── Data_clean/
    ├── linkedin_clean.xlsx   # LinkedIn profiles
    └── topcv_clean.xlsx      # TopCV profiles
```

### 2.2. Chạy pipeline

```bash
cd "C:/CV feedback and roadmap/knowledge_base"
python run_pipeline.py
```

**Pipeline 7 bước**:

| Step | File | Chức năng |
|------|------|-----------|
| 1 | `01_data_loader.py` | Load & clean data từ CSV/Excel |
| 2 | `02_skill_extractor.py` | Extract skills từ text |
| 3 | `03_ontology_builder.py` | Xây skill ontology (canonical names) |
| 4 | `04_role_skill_matrix.py` | Tính frequency skills theo role |
| 5 | `05_career_transition.py` | Xây đồ thị chuyển đổi nghề nghiệp |
| 6 | `06_profile_normalizer.py` | Normalize CV profiles |
| 7 | `07_vector_indexer.py` | Index embeddings vào ChromaDB |

**Output**:
```
knowledge_base/outputs/
├── skill_ontology.json      # 88 skill mappings
├── role_skill_matrix.csv    # Skills frequency by role
├── career_graph.json        # Career transition graph
├── chroma_db/               # Vector database
├── unified_data.parquet     # All data merged
└── data_with_skills.parquet # Data + extracted skills
```

---

## 3. Phân tích CV với Skill Gap Engine

### 3.1. Chạy demo end-to-end

```bash
cd "C:/CV feedback and roadmap/KB+analysis+engine"
python examples/demo_e2e.py
```

**Output**:
```
======================================================================
SKILL GAP ANALYSIS - END-TO-END DEMO
======================================================================

[STEP 1] Checking local LLM...
[OK] Local LLM is ready (Qwen2.5)

[STEP 2] Analyzing CV with Skill Gap Engine...
[OK] Readiness: 65.5%
[OK] Strengths: 5
[OK] Gaps: 3 medium, 2 critical

[STEP 3] Building LLM prompt...
[OK] Prompt length: 2456 characters

[STEP 4] Calling Qwen2.5 to generate feedback...
----------------------------------------------------------------------

# Feedback Report for AI Engineer

## Overall Assessment
Your readiness score is **65.5%**, indicating a moderate fit...

## Strengths
1. **Python** (85% frequency) - Excellent foundation...
2. **PyTorch** (60% frequency) - Good experience...

## Areas for Improvement
### Critical Gaps
1. **LLM** (75% frequency, CRITICAL)
   - Action: Complete LLM course and build RAG project
   - Timeline: 4-6 weeks

### Medium Gaps
1. **MLOps** (45% frequency, MEDIUM)
   - Action: Learn Docker, Kubernetes, CI/CD
   - Timeline: 2-3 weeks

## Recommended Learning Path
1. **Prerequisites**: Transformers, Attention Mechanism
2. **Core**: LLM, RAG
3. **Advanced**: Distributed Training

----------------------------------------------------------------------

[STEP 5] Running automatic evaluation...

📊 EVALUATION RESULTS:
  • Hallucination Rate: 0.00%
    ✅ No hallucinated skills detected

  • Severity Drift: 0
    ✅ All gaps correctly classified

  • Number Drift: 0 issues
    ✅ All numbers match source JSON

  • Overall Score: 0.95 / 1.00
----------------------------------------------------------------------

[DONE] Feedback generated (3421 characters)
```

### 3.2. Chạy với CV của bạn

**Edit file**: `examples/test_real_cv.py`

```python
# Thay thế skills và target role
RESUME_SKILLS = [
    "Python", "Machine Learning", "TensorFlow",
    "SQL", "Docker", "AWS"
]
TARGET_ROLE = "AI Engineer"

# Chạy
python examples/test_real_cv.py
```

---

## 4. API Usage

### 4.1. Extract Skills từ text

```python
from knowledge_base.config import SKILL_ONTOLOGY_PATH
from knowledge_base._08_knowledge_api import extract_skills

text = """
I have 3 years of experience in Python, Machine Learning, Deep Learning.
Proficient in PyTorch, TensorFlow, and Scikit-learn.
Experience with Docker and AWS.
"""

skills = extract_skills(text)
print(skills)
# Output: ['AWS', 'Deep Learning', 'Docker', 'Machine Learning',
#          'Python', 'PyTorch', 'Scikit-learn', 'TensorFlow']
```

### 4.2. Match Jobs với CV

```python
from knowledge_base._08_knowledge_api import match_jobs

cv_skills = ["Python", "PyTorch", "Computer Vision", "SQL"]
cv_text = "AI Engineer with 2 years experience in deep learning..."

jobs = match_jobs(cv_skills, cv_text, top_n=5)

for job in jobs:
    print(f"{job['role']} - Score: {job['final_score']:.1f}")
```

### 4.3. Analyze Skill Gap

```python
from skill_gap.skill_gap_engine import SkillGapEngine

engine = SkillGapEngine()

analysis = engine.analyze(
    resume_skills=["Python", "PyTorch", "Computer Vision"],
    target_role="AI Engineer",
    max_improvement_actions=5
)

print(f"Readiness: {analysis['readiness_score']}%")
print(f"Strengths: {len(analysis['strengths'])}")
print(f"Critical gaps: {len(analysis['critical_gaps'])}")

# Access detailed results
for gap in analysis['critical_gaps']:
    print(f"  - {gap['skill']}: {gap['frequency']}% (weight: {gap['weight']})")
```

### 4.4. Generate Career Roadmap

```python
from knowledge_base._08_knowledge_api import generate_career_roadmap

current_skills = ["Python", "Machine Learning", "SQL"]
target_role = "AI Engineer"

roadmap = generate_career_roadmap(current_skills, target_role)

print(f"Path: {' → '.join(roadmap['path'])}")
for step in roadmap['steps']:
    print(f"  {step['role']}: {step['skills_to_learn']}")
```

### 4.5. Generate LLM Feedback

```python
from skill_gap.feedback_generator import FeedbackGenerator
from skill_gap.local_llm import LocalLLMClient

# Generate prompt
generator = FeedbackGenerator()
prompt = generator.generate_prompt(analysis)

# Call LLM
client = LocalLLMClient()
feedback = client.generate(prompt)

print(feedback)
```

---

## 5. Troubleshooting

### 5.1. Lỗi: "Role 'X' not found in knowledge base"

**Nguyên nhân**: Target role không có trong `role_skill_matrix.csv`

**Giải pháp**:
```python
# Xem danh sách roles có sẵn
import pandas as pd
from knowledge_base.config import ROLE_SKILL_MATRIX_PATH

df = pd.read_csv(ROLE_SKILL_MATRIX_PATH)
roles = df['role'].unique()
print(sorted(roles))

# Output: ['AI Engineer', 'Backend Developer', 'Data Analyst', ...]
```

### 5.2. Lỗi: "Local LLM not ready"

**Nguyên nhân**: Ollama chưa chạy hoặc chưa kéo model

**Giải pháp**:
```bash
# Kiểm tra Ollama
ollama list

# Kéo model nếu chưa có
ollama pull qwen2.5:7b

# Chạy thử
ollama run qwen2.5:7b "Hello"
```

### 5.3. Lỗi: "ChromaDB collection not found"

**Nguyên nhân**: Chưa chạy pipeline hoặc ChromaDB chưa được index

**Giải pháp**:
```bash
cd "C:/CV feedback and roadmap/knowledge_base"
python run_pipeline.py
```

### 5.4. Lỗi: "ModuleNotFoundError: No module named 'skill_gap'"

**Nguyên nhân**: Chưa cài đặt package hoặc chạy từ sai thư mục

**Giải pháp**:
```bash
# Đảm bảo đang ở đúng thư mục
cd "C:/CV feedback and roadmap/KB+analysis+engine"

# Hoặc thêm vào Python path
export PYTHONPATH="${PYTHONPATH}:C:/CV feedback and roadmap/KB+analysis+engine"
```

### 5.5. Lỗi: "Hallucination detected" trong evaluation

**Nguyên nhân**: LLM sinh ra skills không có trong source JSON

**Giải pháp**:
```python
# Kiểm tra hallucinated skills
evaluator = FeedbackEvaluator()
result = evaluator.evaluate(source_json, feedback)

print(f"Hallucination rate: {result['hallucination_rate']:.2%}")
print(f"Hallucinated skills: {result['hallucinated_skills']}")

# Nếu rate cao, thử:
# 1. Dùng prompt mạnh hơn (thêm "ONLY use skills from JSON")
# 2. Dùng model khác (Qwen2.5:14b thay vì 7b)
# 3. Tăng temperature=0.0 để giảm sáng tạo
```

### 5.6. Lỗi: "Skill normalization failed"

**Nguyên nhân**: Skill name không có trong ontology

**Giải pháp**:
```python
# Thêm skill vào ontology
from knowledge_base.config import MANUAL_ALIASES

# Thêm alias
MANUAL_ALIASES["new_skill"] = "New Skill"
MANUAL_ALIASES["ns"] = "New Skill"

# Hoặc edit trực tiếp file
# knowledge_base/outputs/skill_ontology.json
```

---

## 📚 Resources

- **Knowledge Base**: `knowledge_base/`
- **Skill Gap Engine**: `skill_gap/skill_gap_engine.py`
- **API Layer**: `knowledge_base/08_knowledge_api.py`
- **Examples**: `examples/`

---

**Last updated**: June 8, 2026
