# Module 1: CV Processing Pipeline

Pipeline xử lý CV tự động: **PDF → Text → Structured JSON → Career Profile**.  
Đây là module đầu tiên trong hệ thống AI Career Roadmap, chịu trách nhiệm trích xuất và chuẩn hóa dữ liệu từ CV PDF.

---

## 📁 Cấu trúc thư mục

```
module 1/
├── main.py                  # Entry point (CLI + callable function)
├── requirements.txt         # Python dependencies
├── src/                     # Source code chính
│   ├── __init__.py          # Export tất cả classes
│   ├── pdf_processor.py     # PyMuPDF: extract text/images từ PDF
│   ├── ocr_engine.py        # PaddleOCR: xử lý scanned PDF
│   ├── section_detector.py  # Phát hiện sections (Education, Experience...)
│   ├── skill_extractor.py   # Trích xuất & chuẩn hóa skills
│   ├── career_profile_builder.py  # Xây dựng hồ sơ năng lực
│   ├── cv_schema.py         # Pydantic models cho CV data
│   ├── llm_extractor.py     # LLM-based extraction (OpenAI/Ollama)
│   ├── regex_extractor.py   # Regex-based fallback extraction
│   ├── text_cleaner.py      # Làm sạch text sau OCR/extract
│   ├── section_splitter.py  # Chia text thành sections
│   ├── json_repairer.py     # Sửa lỗi JSON từ LLM output
│   └── ...
├── examples/
│   ├── sample_cv.pdf        # CV mẫu để test
│   └── sample_output.json   # Output JSON tương ứng
└── docs/
    └── (API contract, schema docs - bổ sung sau)
```

---

## 🚀 Quick Start

### 1. Cài đặt dependencies

```bash
cd "module 1"
pip install -r requirements.txt
```

> ⚠️ **PaddleOCR** yêu cầu system libraries. Trên Linux: `apt-get install libgl1-mesa-glx libglib2.0-0`.  
> Trên Windows, PaddleOCR thường cài được trực tiếp qua pip. Nếu lỗi, dùng Docker (xem bên dưới).

### 2. Chạy với CV mẫu

```bash
python main.py --input examples/sample_cv.pdf --output result.json
```

### 3. Chạy với CV bất kỳ (Dynamic Input)

Pipeline **không phụ thuộc vào tên file cố định**. Bạn có thể truyền đường dẫn CV của bất kỳ user nào:

```bash
# CLI - xử lý CV bất kỳ từ local
python main.py --input "C:\Users\Admin\Downloads\cv_nguyen_van_a.pdf" --output "result_a.json"

# Short flag
python main.py -i "path/to/any_cv.pdf" -o "output.json"
```

> ⚠️ Nếu không chỉ định `--output`, kết quả sẽ in ra stdout (phù hợp khi Backend gọi qua subprocess).

#### Backend tích hợp upload động

Khi user upload CV lên web, Backend nhận file và truyền đường dẫn **động** vào pipeline:

**Cách 1: Subprocess (Recommended - cách ly môi trường)**
```python
import subprocess, json

def process_uploaded_cv(uploaded_file_path: str) -> dict:
    """Xử lý CV do user upload - đường dẫn thay đổi theo mỗi request"""
    result = subprocess.run(
        ["python", "main.py", "--input", uploaded_file_path],
        capture_output=True, text=True,
        cwd=r"C:\CV feedback and roadmap\module 1"
    )
    if result.returncode != 0:
        raise Exception(f"Pipeline error: {result.stderr}")
    return json.loads(result.stdout)
```

**Cách 2: Import trực tiếp (nếu cùng Python env)**
```python
import sys
sys.path.insert(0, r"C:\CV feedback and roadmap\module 1")
from main import process_cv

# Đường dẫn CV thay đổi theo mỗi user/request
profile = process_cv("/tmp/uploads/user_12345_cv.pdf")
```

#### Frontend lưu ý
- Upload component cần validate `.pdf` extension và file size ≤ 10MB **trước khi gửi**.
- Gửi file qua `multipart/form-data` đến endpoint Backend.
- Không hardcode tên file — luôn dùng dynamic path từ server response.

---

## 🔄 Luồng xử lý (Pipeline Flow)

> ⚠️ **Hiện tại:** Pipeline chỉ hỗ trợ **digital PDF** (PDF có text layer).  
> Scanned PDF (ảnh chụp/scan) sẽ được hỗ trợ ở phase sau khi tích hợp PaddleOCR thực tế.

```
Input PDF (Digital)
    │
    ▼
[Step 1] PyMuPDF Extract Text ──→ Raw text từ tất cả trang
    │
    ▼
[Step 2] Section Detection ──→ {personal_info, education, experience, skills, projects, ...}
    │
    ▼
[Step 3] Skill Normalization ──→ Chuẩn hóa tên skills, loại trùng lặp
    │
    ▼
[Step 4] Career Profile Building ──→ {current_role, career_stage, experience_years, domains, tech_stack}
    │
    ▼
Output JSON
```

---

## 📦 Output JSON Schema

```json
{
  "pdf_type": "digital | scanned",
  "structured_data": {
    "personal_info": ["Ha Duyen Hai Anh", "haduyenhaianh2007@gmail.com", ...],
    "education": ["Hanoi University of Science and Technology", ...],
    "experience": ["AI Engineer Intern at ...", ...],
    "skills": ["Python", "FastAPI", "PyTorch", "RAG", ...],
    "projects": [{"name": "...", "technologies": [...]}],
    "certifications": [],
    "languages": []
  },
  "career_profile": {
    "current_role": "AI Engineer Intern",
    "career_stage": "Intern/Junior",
    "experience_years": 1.5,
    "domains": ["AI/ML", "Backend Development"],
    "skills": ["Python", "FastAPI", "PyTorch", "RAG", "ChromaDB"],
    "technology_stack": ["Python", "FastAPI", "PyTorch", "RAG", "ChromaDB"],
    "summary": "Ha Duyen Hai Anh - Ứng viên tiềm năng | Lĩnh vực: AI/ML, Backend Development"
  }
}
```

> 📌 Xem file mẫu đầy đủ: [examples/sample_output.json](examples/sample_output.json)

---

## 💻 Hướng dẫn tích hợp cho Backend

### Cách 1: Gọi qua subprocess (Recommended)

```python
import subprocess
import json

result = subprocess.run(
    ["python", "main.py", "--input", uploaded_cv_path],
    capture_output=True, text=True, cwd="path/to/module 1"
)
profile = json.loads(result.stdout)
```

### Cách 2: Import trực tiếp (nếu cùng Python environment)

```python
import sys
sys.path.insert(0, "path/to/module 1")
from main import process_cv

profile = process_cv("uploaded_cv.pdf")
```

### Endpoint gợi ý

| Method | Path | Mô tả |
|--------|------|-------|
| POST | `/api/v1/cv/upload` | Nhận file PDF (multipart/form-data), trả về JSON profile |
| GET | `/api/v1/profile/{id}` | Lấy lại profile đã lưu |

### Lưu ý quan trọng

- **Thời gian xử lý:** Digital PDF ~0.5-1s, Scanned PDF ~3-8s (do OCR). Nên dùng async/job queue.
- **Memory:** PaddleOCR tốn ~2-4GB RAM. Giới hạn concurrent requests.
- **Error handling:** Pipeline trả về error message rõ ràng. Backend nên wrap thêm error code (`INVALID_PDF`, `OCR_FAILED`, etc.).
- **File size:** Nên giới hạn upload ≤ 10MB phía Backend.

---

## 🎨 Hướng dẫn tích hợp cho Frontend

- **Upload component:** Drag-drop, validate `.pdf` extension và file size trước khi gửi.
- **Loading state:** Hiển thị spinner/progress bar. Scanned PDF có thể mất 5-8s.
- **Editable form:** Render `structured_data` dạng form để user confirm/chỉnh sửa trước khi lưu.
- **Dashboard:** Hiển thị `career_profile` (role, stage, skills, domains) dạng card/tag cloud.

---

## ⚙️ Environment Variables (nếu dùng LLM extraction)

Tạo file `.env` trong thư mục `module 1/`:

```env
OPENAI_API_KEY=sk-...
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=gpt-4o-mini
```

> Hiện tại pipeline hoạt động được mà **không cần LLM** (dùng regex + rule-based).  
> LLM extraction là optional, dùng để nâng cao độ chính xác.

---

## 🐛 Troubleshooting

| Vấn đề | Giải pháp |
|--------|-----------|
| `ModuleNotFoundError: No module named 'fitz'` | `pip install PyMuPDF` |
| PaddleOCR import error | Cài system libs hoặc dùng Docker |
| Output JSON thiếu fields | Kiểm tra CV có đủ sections không; xem log console |
| OCR ra text sai/rác | CV scan chất lượng thấp → tăng DPI trong `pdf_processor.py` |
