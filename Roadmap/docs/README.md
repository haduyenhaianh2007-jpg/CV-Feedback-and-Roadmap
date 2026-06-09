# Roadmap Module – Career Compiler

Hệ thống sinh roadmap học tập cá nhân hóa dựa trên **knowledge graph** (DAG), không hardcode, tái sinh 100% từ graph + user state.

## 🧱 Kiến trúc 4 layer

| Layer | Tên | Vai trò | Output |
|-------|-----|---------|--------|
| 🔵 Layer 1 | Master Roadmap Graph | Knowledge graph gốc (DAG) | nodes + edges (quan hệ prerequisite) |
| 🟡 Layer 2 | Personalized Skill Overlay | Gán trạng thái user lên graph | completed / partial / missing / recommended_next |
| 🟣 Layer 3 | Phase Generator | Chuyển graph + user state → roadmap tuần tự | phases[].skills, duration, expected ATS |
| 🔴 Layer 4 | Node Detail Panel | Chi tiết skill khi click | market_demand, priority, effort, ats_gain, projects |

**Nguyên tắc cốt lõi:**
- Layer 1 là **source of truth** – mọi thứ derive từ graph, không hardcode
- Layer 2 chỉ **colorize**, không làm thay đổi graph gốc
- Layer 3 là **derived artifact** – regenerate 100% từ Layer 1 + Layer 2

## 📁 Cấu trúc thư mục

```
Roadmap/
├── roadmap/
│   ├── roadmap_generator_v2.py   # Orchestrator chính
│   ├── role_aware_pruner.py      # Layer 2: lọc graph theo role
│   ├── phase_builder_v2.py       # Layer 3: tạo phases từ graph
│   ├── graph_ats_scorer.py       # Layer 5: tính ATS dựa trên graph
│   ├── llm_narrative_layer.py    # Layer 4: sinh narrative giải thích
│   ├── project_templates.py      # Gợi ý project cho từng skill
│   └── stage_detector.py         # Phát hiện career stage
├── roadmap_output_v2.json        # Output mẫu
├── test_v2.py                    # Script chạy thử
└── README.md
```

## 🔧 Yêu cầu hệ thống

- **Python**: 3.10 trở lên (dùng các module chuẩn: `typing`, `dataclasses`, `pathlib`, `json`, `collections`)
- **Không cần thư viện bên ngoài** – toàn bộ code dùng thư viện chuẩn của Python.

## 📦 Cài đặt

1. Clone/di chuyển vào thư mục dự án:
   ```bash
   cd "C:\CV feedback and roadmap"
   ```

2. (Tùy chọn) Tạo virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/Mac
   .\venv\Scripts\activate       # Windows
   ```

3. Cài đặt dependencies (nếu có – hiện tại không cần):
   ```bash
   pip install -r Roadmap/requirements.txt
   ```
   (File requirements.txt hiện tại để trống vì chỉ dùng thư viện chuẩn)

## 🚀 Chạy thử

```bash
python "C:\CV feedback and roadmap\test_v2.py"
```

Kết quả: file `Roadmap/roadmap_output_v2.json` được tạo, chứa đầy đủ:
- `pruned_graph`: Layer 1
- `user_overlay`: Layer 2
- `phases`: Layer 3
- `narrative`: Layer 4 (phase_narratives, personalized_story, ats_report)
- `ats_report`: Layer 5 (điểm ATS hiện tại và dự kiến)

## 📡 API Endpoints (gợi ý cho backend)

| Method | Endpoint | Input | Output |
|--------|----------|-------|--------|
| POST | `/api/roadmap/generate` | `{ cv_data, target_role }` | Full contract (4 layer) |
| GET | `/api/roadmap/graph` | `?role=AI Engineer` | Layer 1 – master graph |
| GET | `/api/roadmap/user-state` | `?user_id=xxx` | Layer 2 – completed/partial/missing |
| GET | `/api/roadmap/phases` | `?user_id=xxx&role=...` | Layer 3 – phases array |
| GET | `/api/roadmap/skill/{skill_name}` | – | Layer 4 – skill detail |

**Response mẫu** (file `roadmap_output_v2.json`):
```json
{
  "pruned_graph": { "nodes": [...], "edges": [...] },
  "phases": [
    { "phase_id": 1, "title": "Foundation", "skills": ["Python","SQL"], "skill_count": 2, "avg_depth": 0.5 }
  ],
  "ats_report": { "current_score": 43, "final_score": 68, "bottlenecks": ["Deep Learning","LLM"] },
  "user_overlay": { "completed": ["Python"], "partial": [], "missing": ["LLM","RAG"] },
  "narrative": {
    "phase_narratives": [...],
    "personalized_story": { "summary": "...", "focus": [...], "advice": [...] },
    "ats_report": { "report": "...", "weaknesses": [...], "next_actions": [...] }
  }
}
```

## 🎨 Hướng dẫn Frontend tích hợp

### Hiển thị roadmap dạng cây / graph (Layer 1 + 2)
- Dùng `pruned_graph` để vẽ DAG (thư viện: `react-flow`, `vis-network`, `d3`)
- Colorize node theo `user_overlay`: 🟢 completed, 🟡 partial, 🔴 missing
- Tooltip: hiển thị `reason` hoặc narrative ngắn

### Hiển thị phases (Layer 3)
- Render `phases` dưới dạng timeline hoặc accordion
- Mỗi phase hiển thị: `title`, danh sách `skills`, `skill_count`, `avg_depth`
- Hover/click phase → lấy narrative từ `narrative.phase_narratives`

### Panel chi tiết skill (Layer 4)
Khi click vào một skill node:
- Market demand (từ `ats_report.bottlenecks` hoặc `market_factors`)
- Priority (high nếu nằm trong bottlenecks)
- Estimated effort (map từ `avg_depth`: depth <1 → 2-4 weeks, 1-2 → 4-6 weeks, >2 → 6-8 weeks)
- ATS gain (từ `phase_contributions` của phase chứa skill)
- Prerequisites (từ `pruned_graph.edges`)
- Gợi ý project (từ `project_mapping` trong output)

### Hiển thị ATS report & personalized story
- Dùng `ats_report` + `narrative.ats_report` để vẽ gauge/thanh tiến trình
- Hiển thị `personalized_story.summary` và `advice` trong onboarding/welcome section

## ⚙️ Tùy chỉnh cấu hình

### Thay đổi market factors
Sửa `DEFAULT_MARKET_FACTORS` trong `graph_ats_scorer.py` hoặc truyền qua `__init__`:
```python
scorer = GraphATSScorer(graph, market_factors={"LLM": 1.5, "RAG": 1.4})
```

### Điều chỉnh độ khó phase
Sửa `max_skills_per_phase` khi khởi tạo `HardConstraintPhaseBuilder`:
```python
phase_builder = HardConstraintPhaseBuilder(skill_graph_engine, max_skills_per_phase=3)
```

### Thêm project template
Mở rộng `project_templates.py`:
```python
Project(
    name="Build RAG from scratch",
    primary_skills=["LLM", "RAG", "LangChain"],
    difficulty="advanced",
    estimated_hours=40
)
```

## 🧪 Kiểm tra hoạt động

```bash
python test_v2.py
cat roadmap_output_v2.json | grep narrative
```

Nếu thấy key `"narrative"` trong output, module đã hoạt động đúng.

## 📞 Hỗ trợ

- Xem file `roadmap_generator_v2.py` để hiểu pipeline tổng thể
- Xem file `llm_narrative_layer.py` để tùy chỉnh narrative
- Xem file `graph_ats_scorer.py` để điều chỉnh cách tính điểm ATS

---

© 2026 Claude Code by Anthropic
