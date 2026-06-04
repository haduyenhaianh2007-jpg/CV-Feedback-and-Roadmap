# DATA_SCHEMA.md - Module 1: CV Extraction Output

Tai lieu mo ta cau truc JSON output cua pipeline CV Extraction, danh cho Backend/Frontend tich hop.

---

## Cau truc tong quan

`json
{
  "pdf_type": "string",
  "structured_data": { ... },
  "career_profile": { ... }
}
`

| Field | Type | Mo ta |
|-------|------|-------|
| pdf_type | "digital" or "scanned" | Loai PDF (hien tai chi ho tro digital) |
| structured_data | object | Du lieu tho da trich xuat theo tung section |
| career_profile | object | Ho so nang luc da chuan hoa va phan loai |

---

## structured_data - Chi tiet tung field

### personal_info - string[]
Danh sach cac dong text tu phan thong tin ca nhan. Khong phai object co key-value, ma la mang string tho.

> Backend luu y: Email, phone, GitHub URL nam lan trong mang string. Dung RegexExtractor hoac parse rieng de lay gia tri cu the.

### summary - string[]
Mang cac dong text tu phan tom tat/muc tieu nghe nghiep. Co the rong [] neu CV khong co phan nay.

### education - string[]
Mang cac dong text tu phan hoc van. Bao gom ten truong, dia diem, chuyen nganh, GPA, thoi gian.

> Backend luu y: GPA/CPA nam trong string, can regex de extract. Thoi gian co format MM/YYYY - MM/YYYY hoac Present.

### experience - string[]
Mang cac dong text tu phan kinh nghiem lam viec.

### projects - string[][]
Mang cua mang string. Moi project la mot sub-array chua cac dong text lien quan.

> Backend luu y: Can logic de gom cac sub-array lien tiep thuoc cung mot project.

### skills - object[]
Mang cac skill objects, moi object co name va category.

| Category | Vi du skills |
|----------|-------------|
| Programming | Python, C/C++, JavaScript |
| Ai/Ml | PyTorch, NLP, LLMs, RAG, Computer Vision |
| Libraries & Frameworks | FastAPI, Pandas, OpenCV, Streamlit |
| Tools | Git, GitHub, Docker, LaTeX, Kaggle |

> Field nay da structured tot nhat. Backend co the dung truc tiep.

### certifications - string[]
Mang cac chung chi. Co the gop nhieu chung chi trong mot string (phan tach bang |).

### achievements - string[]
Mang cac thanh tich/giai thuong.

---

## career_profile - Ho so nang luc

| Field | Type | Mo ta |
|-------|------|-------|
| current_role | string | Vi tri hien tai (lay tu dong dau cua experience) |
| career_stage | string | Giai doan nghe nghiep: Student / Intern/Junior / Mid / Senior |
| experience_years | float | So nam kinh nghiem (extract tu text) |
| domains | string[] | Linh vuc chuyen mon (auto-detect tu skills) |
| skills | string[] | Danh sach ky nang phang (da deduplicate) |
| technology_stack | string[] | Tech stack (giong skills nhung thu tu khac) |
| summary | string | Tom tat ho so (auto-generated) |

### Logic xac dinh career_stage

| Dieu kien | Stage |
|-----------|-------|
| Education chua Present va experience_years = 0 | Student |
| experience_years > 0 va dang la Student | Intern/Junior |
| experience_years 1-3 | Junior |
| experience_years 3-5 | Mid |
| experience_years > 5 | Senior |

### Logic xac dinh domains

| Domain | Keywords trigger |
|--------|-----------------|
| AI/ML | ai, ml, machine learning, deep learning, nlp, llm, rag, transformer, pytorch, tensorflow |
| Backend Development | backend, api, fastapi, flask, django, spring, nodejs, express |
| Frontend Development | frontend, react, vue, angular, html, css, javascript, typescript |
| Data Science | data, analysis, pandas, numpy, sql, database, big data |
| DevOps/Cloud | devops, docker, kubernetes, ci/cd, aws, azure, gcp |
| Healthcare Tech | healthcare, medical, y te, suc khoe |

---

## Luu y tich hop

### 1. Data Quality Warnings
- personal_info, education, experience la raw text arrays, chua structured hoan toan.
- skills la field structured tot nhat - dung truc tiep duoc.
- projects co cau truc nested array - can logic group truoc khi hien thi.

### 2. Null Safety
- Moi field deu co the rong ([], "", 0.0). Frontend phai handle empty state.
- career_profile.experience_years mac dinh 0.0 neu khong parse duoc tu text.

### 3. Encoding
- Output JSON luon dung ensure_ascii=False -> giu nguyen ky tu tieng Viet.
- Backend/frontend phai dam bao UTF-8 encoding khi doc/luu.

### 4. Versioning
- Schema nay ap dung cho Module 1 output tinh den ngay 2026-06-04.
- Khi bo sung OCR (scanned PDF), field processing_metadata se duoc them vao.

---

## Vi du day du

Xem file mau: ../examples/sample_output.json
