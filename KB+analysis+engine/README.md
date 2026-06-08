# KB+analysis+engine — Career Knowledge Base & Skill Analysis Engine

> Hệ thống phân tích CV, đánh giá khoảng cách kỹ năng (skill gap) và gợi ý lộ trình phát triển nghề nghiệp.

## 📁 Cấu trúc thư mục

```
KB+analysis+engine/
├── README.md                    # Tài liệu này
├── USAGE.md                     # Hướng dẫn sử dụng chi tiết
├── REPLACEMENT_GUIDE.md         # Gợi ý code thay thế cho CV khác
├── requirements.txt             # Dependencies
│
├── knowledge_base/              # [1] Xây dựng & truy vấn Knowledge Base
│   ├── config.py                # Cấu hình đường dẫn, model, DB
│   ├── 01_data_loader.py        # Load & clean data từ LinkedIn/TopCV/JD
│   ├── 02_skill_extractor.py    # Extract skills từ text (NLP + regex)
│   ├── 03_ontology_builder.py   # Xây dựng skill ontology (canonical names)
│   ├── 04_role_skill_matrix.py  # Tính frequency skills theo role
│   ├── 05_career_transition.py  # Xây dựng đồ thị chuyển đổi nghề nghiệp
│   ├── 06_profile_normalizer.py # Normalize CV profiles
│   ├── 07_vector_indexer.py     # Index embeddings vào ChromaDB
│   ├── 08_knowledge_api.py      # API layer: extract_skills, match_jobs, analyze_skill_gap
│   ├── run_pipeline.py          # Chạy toàn bộ pipeline
│   └── outputs/                 # Data files (parquet, csv, json)
│       ├── skill_ontology.json  # 88 skill mappings
│       ├── role_skill_matrix.csv # Skills frequency by role
│       └── career_graph.json    # Career transition graph
│
├── skill_gap/                   # [2] Skill Gap Analysis Engine
│   ├── skill_gap_engine.py      # Orchestrator (8-step pipeline)
│   ├── skill_normalization.py   # Chuẩn hóa skill names
│   ├── strength_analyzer.py     # Phân tích điểm mạnh (CV ∩ role requirements)
│   ├��─ weakness_analyzer.py     # Phân tích điểm yếu (role requirements - CV)
│   ├── severity_analyzer.py     # Phân loại gaps (critical/medium/optional)
│   ├── readiness_calculator.py  # Tính readiness score (%)
│   ├── improvement_analyzer.py  # Gợi ý hành động cải thiện
│   ├── feedback_generator.py    # Generate LLM prompt từ analysis
│   ├── feedback_evaluator.py    # Đánh giá chất lượng feedback
│   ├── local_llm.py             # Client cho Ollama (Qwen2.5)
│   ├── text_cleaner.py          # Clean text trước khi extract skills
│   ├── demo_e2e.py              # Demo end-to-end
│   ├── skill_metadata.json      # Metadata cho skills
│   └── prompts/
│       └── skill_gap_feedback.txt # Prompt template cho LLM
│
├── skill_graph/                 # [3] Skill Relationship Graph
│   ├── skill_graph_engine.py    # Query skill relationships (prerequisites, leads_to)
│   └── skill_relationships.json # Graph data (skills, clusters, edges)
│
└── examples/                    # [4] Demo scripts
    ├── demo_e2e.py              # CV → Skill Gap → LLM → Feedback
    ├── demo_integration_v1.py   # Integration test
    └── test_real_cv.py          # Test với CV thực tế
```

## 🎯 Chức năng chính

### 1. Knowledge Base (`knowledge_base/`)

Xây dựng Career Knowledge Base từ dữ liệu thực tế:
- **Skill Ontology**: 88 canonical skill names + aliases
- **Role-Skill Matrix**: Frequency của skills theo job role
- **Career Graph**: Đồ thị chuyển đổi giữa các vai trò
- **Semantic Search**: Tìm kiếm CV/Jobs tương tự qua embeddings

### 2. Skill Gap Analysis (`skill_gap/`)

Phân tích khoảng cách kỹ năng với **8-step pipeline**:

```
1. Normalize skills      → Canonical names
2. Validate role         → Kiểm tra role có trong KB
3. Strength analysis     → Skills user có ∩ role requirements
4. Weakness analysis     → Skills user thiếu
5. Severity analysis     → Phân loại critical/medium/optional
6. Readiness score       → owned_weight / total_weight
7. Improvement actions   → Gợi ý hành động per gap
8. Assemble JSON         → Structured output
```

### 3. Skill Graph (`skill_graph/`)

Phân tích mối quan hệ giữa skills:
- **Prerequisites**: Skills cần học trước
- **Related skills**: Skills bổ trợ
- **Leads to**: Skills có thể học tiếp theo
- **Learning paths**: Lộ trình học tập

## 🚀 Quick Start

```bash
# 1. Cài đặt dependencies
cd "C:/CV feedback and roadmap/KB+analysis+engine"
pip install -r requirements.txt

# 2. Chạy demo end-to-end
python examples/demo_e2e.py

# 3. Hoặc phân tích CV của bạn
python examples/test_real_cv.py
```

## 📊 Output Example

```json
{
  "target_role": "AI Engineer",
  "readiness_score": 65.5,
  "strengths": [
    {"skill": "Python", "frequency": 85.0, "weight": 0.85},
    {"skill": "PyTorch", "frequency": 60.0, "weight": 0.60}
  ],
  "critical_gaps": [
    {"skill": "LLM", "frequency": 75.0, "weight": 0.75, "severity": "critical"}
  ],
  "medium_gaps": [
    {"skill": "MLOps", "frequency": 45.0, "weight": 0.45, "severity": "medium"}
  ],
  "improvement_actions": [
    {
      "skill": "LLM",
      "action": "Complete LLM course and build RAG project",
      "priority": "high",
      "estimated_time": "4-6 weeks"
    }
  ],
  "graph_insights": {
    "missing_skills": {
      "target_skills": ["LLM", "RAG"],
      "missing_prerequisites": {
        "LLM": ["Transformers", "Attention Mechanism"]
      }
    },
    "deepen_skills": {
      "current_strengths": ["Python", "PyTorch"],
      "recommended_next": [
        {"skill": "Distributed Training", "reason": "Natural progression from PyTorch"}
      ]
    }
  }
}
```

## 🛠️ Tech Stack

- **Python 3.12+**
- **pandas, numpy**: Data processing
- **scikit-learn**: Similarity calculations
- **ChromaDB**: Vector database for semantic search
- **sentence-transformers**: Embedding model (paraphrase-multilingual-MiniLM-L12-v2)
- **Ollama + Qwen2.5**: Local LLM for feedback generation

## 📚 Documentation

- **[USAGE.md](USAGE.md)**: Hướng dẫn cài đặt, sử dụng API, troubleshooting
- **[REPLACEMENT_GUIDE.md](REPLACEMENT_GUIDE.md)**: Cách chạy với CV khác, customizing feedback

## 🔗 Links

- Knowledge Base Pipeline: `knowledge_base/run_pipeline.py`
- Skill Gap API: `skill_gap/skill_gap_engine.py`
- Demo: `examples/demo_e2e.py`

---

**Last updated**: June 8, 2026
