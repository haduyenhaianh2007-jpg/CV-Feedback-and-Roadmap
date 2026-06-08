"""
07_vector_indexer.py
====================
Tạo vector embeddings cho resume và job profiles để hỗ trợ tìm kiếm ngữ nghĩa (semantic search).

Module này:
- Đọc resume_profiles.parquet và job_profiles.parquet từ thư mục outputs/
- Xây dựng text representation cho mỗi record
- Tạo embeddings bằng sentence-transformers (all-MiniLM-L6-v2)
- Lưu trữ vào ChromaDB persistent collections ("resumes" và "jobs")
- Cung cấp hàm search_similar() để truy vấn semantic search
"""

import time
import sys
from pathlib import Path

# Thêm thư mục cha vào path để import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    RESUME_PROFILES_PATH,
    JOB_PROFILES_PATH,
    OUTPUT_DIR,
)

# Kiểm tra các thư viện bắt buộc
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("[ERROR] Thư viện 'sentence-transformers' chưa được cài đặt.")
    print("  Cài đặt bằng lệnh: pip install sentence-transformers")
    sys.exit(1)

try:
    import chromadb
except ImportError:
    print("[ERROR] Thư viện 'chromadb' chưa được cài đặt.")
    print("  Cài đặt bằng lệnh: pip install chromadb")
    sys.exit(1)

import pandas as pd


def build_embedding_texts(df: pd.DataFrame, record_type: str) -> list[str]:
    """
    Xây dựng chuỗi text đại diện cho mỗi record để tạo embedding.

    Args:
        df: DataFrame chứa dữ liệu profiles (resume hoặc job)
        record_type: "resume" hoặc "job" - xác định loại bản ghi

    Returns:
        List các chuỗi text tương ứng với mỗi hàng trong DataFrame
    """
    texts = []

    if record_type == "resume":
        # Với resume: kết hợp category, skills và mô tả ngắn
        for _, row in df.iterrows():
            category = str(row.get("category", "")) if pd.notna(row.get("category")) else ""
            skills = row.get("skills", [])
            # PyArrow may deserialize list columns as numpy ndarray
            if isinstance(skills, (list, tuple)) or (
                hasattr(skills, '__iter__') and hasattr(skills, '__len__')
                and not isinstance(skills, (str, bytes, dict))
            ):
                skills_str = ", ".join(str(s) for s in skills if s)
            else:
                skills_str = str(skills) if pd.notna(skills) else ""

            description_preview = str(row.get("description_preview", "")) if pd.notna(row.get("description_preview")) else ""
            # Cắt mô tả tối đa 300 ký tự để tránh vượt quá token limit
            description_preview = description_preview[:300]

            text = f"Category: {category}. Skills: {skills_str}. {description_preview}"
            texts.append(text.strip())

    elif record_type == "job":
        # V2.1: Enriched job text — dùng TẤT CẢ fields có sẵn
        # để tăng chất lượng embeddings (~50 words thay vì ~20 words).
        # Mục tiêu: cải thiện semantic similarity giữa CV và job.
        for _, row in df.iterrows():
            title_original = (
                str(row.get("title_original", ""))
                if pd.notna(row.get("title_original"))
                else ""
            )
            role = (
                str(row.get("role", ""))
                if pd.notna(row.get("role"))
                else ""
            )
            seniority = (
                str(row.get("seniority", ""))
                if pd.notna(row.get("seniority"))
                else ""
            )
            category = (
                str(row.get("category", ""))
                if pd.notna(row.get("category"))
                else ""
            )
            skills = row.get("skills", [])
            # PyArrow may deserialize list columns as numpy ndarray
            if isinstance(skills, (list, tuple)) or (
                hasattr(skills, '__iter__') and hasattr(skills, '__len__')
                and not isinstance(skills, (str, bytes, dict))
            ):
                skills_str = ", ".join(str(s) for s in skills if s)
            else:
                skills_str = str(skills) if pd.notna(skills) else ""

            company = (
                str(row.get("company", ""))
                if pd.notna(row.get("company"))
                else ""
            )
            location = (
                str(row.get("location", ""))
                if pd.notna(row.get("location"))
                else ""
            )

            # Build enriched text — chỉ thêm field có giá trị non-empty
            parts = []
            if title_original and title_original.strip():
                parts.append(f"Title: {title_original.strip()}")
            if (
                role
                and role.strip()
                and role.strip().lower() != title_original.strip().lower()
            ):
                parts.append(f"Role: {role.strip()}")
            if seniority and seniority.strip():
                parts.append(f"Seniority: {seniority.strip()}")
            if category and category.strip():
                parts.append(f"Category: {category.strip()}")
            if skills_str and skills_str.strip():
                parts.append(f"Required Skills: {skills_str.strip()}")
            if company and company.strip():
                parts.append(f"Company: {company.strip()}")
            if location and location.strip():
                parts.append(f"Location: {location.strip()}")

            text = ". ".join(parts)
            texts.append(text.strip())
    else:
        raise ValueError(f"record_type không hợp lệ: '{record_type}'. Phải là 'resume' hoặc 'job'.")

    return texts


def create_vector_index():
    """
    Hàm chính: tải profiles, tạo embeddings và lưu vào ChromaDB.

    Quy trình:
    1. Đọc resume_profiles.parquet và job_profiles.parquet
    2. Xây dựng text cho mỗi record
    3. Batch encode bằng SentenceTransformer
    4. Tạo/cập nhật ChromaDB persistent collections
    """
    start_time = time.time()
    chroma_dir = Path(OUTPUT_DIR) / "chroma_db"

    # --- Kiểm tra file đầu vào ---
    resume_path = Path(RESUME_PROFILES_PATH)
    job_path = Path(JOB_PROFILES_PATH)

    if not resume_path.exists():
        print(f"[WARNING] File không tồn tại: {resume_path}")
        print("  Vui lòng chạy các bước trước để tạo resume_profiles.parquet")
        return

    if not job_path.exists():
        print(f"[WARNING] File không tồn tại: {job_path}")
        print("  Vui lòng chạy các bước trước để tạo job_profiles.parquet")
        return

    # --- Tải dữ liệu ---
    print("=" * 60)
    print("BẮT ĐẦU TẠO VECTOR INDEX (V2.1 - Enriched + Dedup)")
    print("=" * 60)

    print(f"\n[1/6] Đang tải dữ liệu profiles...")
    resume_df = pd.read_parquet(resume_path)
    job_df = pd.read_parquet(job_path)
    print(f"  - Resume profiles: {len(resume_df)} bản ghi (trước dedup)")
    print(f"  - Job profiles: {len(job_df)} bản ghi (trước dedup)")

    # --- V2.2: Content-based dedup ---
    # Job IDs đã unique, nhưng nhiều jobs là "repost" — cùng title, company, skills
    # (cùng 1 JD đăng ở nhiều nguồn LinkedIn/TopCV hoặc đăng lại nhiều lần).
    # Thay vì dedup theo ID, dedup theo content hash = title + company + sorted(skills).
    # Mục tiêu: loại 10-20% trùng lặp nội dung, giúp top N kết quả đa dạng hơn.
    print(f"\n[2/6] Đang loại bỏ duplicates theo nội dung...")
    original_resume_count = len(resume_df)
    original_job_count = len(job_df)

    def _row_content_hash(row: pd.Series) -> str:
        """Tạo hash từ nội dung chính của record (title/company/skills)."""
        import hashlib

        title = str(row.get("title_original", "") or row.get("role", "") or "")
        company = str(row.get("company", "") or "")
        # Normalize title + company
        key_parts = [title.strip().lower(), company.strip().lower()]

        # Normalize skills: sort để order không ảnh hưởng đến hash
        skills = row.get("skills", [])
        if isinstance(skills, (list, tuple)) or (
            hasattr(skills, "__iter__")
            and hasattr(skills, "__len__")
            and not isinstance(skills, (str, bytes, dict))
        ):
            skill_list = sorted(str(s).strip().lower() for s in skills if s)
        else:
            skill_list = []
        key_parts.append("|".join(skill_list))

        raw_key = "::".join(key_parts)
        return hashlib.md5(raw_key.encode("utf-8")).hexdigest()

    # Áp dụng cho resumes
    resume_df = resume_df.copy()
    resume_df["_content_hash"] = resume_df.apply(_row_content_hash, axis=1)
    resume_df = resume_df.drop_duplicates(subset=["_content_hash"], keep="first")
    resume_df = resume_df.drop(columns=["_content_hash"])

    # Áp dụng cho jobs
    job_df = job_df.copy()
    job_df["_content_hash"] = job_df.apply(_row_content_hash, axis=1)
    job_df = job_df.drop_duplicates(subset=["_content_hash"], keep="first")
    job_df = job_df.drop(columns=["_content_hash"])

    resume_dedup_count = original_resume_count - len(resume_df)
    job_dedup_count = original_job_count - len(job_df)
    print(f"  - Resume: loại bỏ {resume_dedup_count} duplicates nội dung, còn {len(resume_df)} records")
    print(f"  - Job: loại bỏ {job_dedup_count} duplicates nội dung, còn {len(job_df)} records")

    # --- Xây dựng text cho embedding ---
    print(f"\n[3/6] Đang xây dựng text cho embedding (enriched template)...")
    resume_texts = build_embedding_texts(resume_df, "resume")
    job_texts = build_embedding_texts(job_df, "job")
    print(f"  - Resume texts: {len(resume_texts)} chuỗi")
    print(f"  - Job texts: {len(job_texts)} chuỗi")

    # In sample enriched job text để kiểm tra template
    if job_texts:
        print(f"\n  📝 Sample enriched job text (first 200 chars):")
        sample_text = job_texts[0]
        print(f"     {sample_text[:200]}...")

    # --- Tải model và tạo embeddings ---
    print(f"\n[4/6] Đang tải model embedding: {EMBEDDING_MODEL}...")
    model = SentenceTransformer(EMBEDDING_MODEL)
    print(f"  Model đã sẵn sàng (dimension={EMBEDDING_DIMENSION})")

    print(f"\n[5/6] Đang tạo embeddings (batch_size=64)...")

    # Batch encode cho resumes
    t0 = time.time()
    resume_embeddings = model.encode(
        resume_texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    t_resume = time.time() - t0
    print(f"  - Resume embeddings: {resume_embeddings.shape} ({t_resume:.1f}s)")

    # Batch encode cho jobs
    t0 = time.time()
    job_embeddings = model.encode(
        job_texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
    )
    t_jobs = time.time() - t0
    print(f"  - Job embeddings: {job_embeddings.shape} ({t_jobs:.1f}s)")

    # --- Lưu vào ChromaDB ---
    print(f"\n[6/6] Đang lưu embeddings vào ChromaDB tại: {chroma_dir}")
    client = chromadb.PersistentClient(path=str(chroma_dir))

    # Xóa collections cũ nếu tồn tại (fresh index mỗi lần chạy)
    for collection_name in ["resumes", "jobs"]:
        try:
            existing = client.get_collection(name=collection_name)
            if existing is not None:
                client.delete_collection(name=collection_name)
                print(f"  - Đã xóa collection cũ: '{collection_name}'")
        except Exception:
            # Collection chưa tồn tại, bỏ qua
            pass

    # Tạo collection mới cho resumes
    # V2.2 FIX: ChromaDB mặc định dùng L2 distance → similarity có thể < 0 hoặc > 1
    # Cần set metadata={"hnsw:space": "cosine"} để dùng cosine distance (range: [0, 2])
    # Khi đó similarity = 1 - distance sẽ nằm trong [-1, 1], chuẩn cho so sánh ngữ nghĩa.
    resumes_collection = client.create_collection(
        name="resumes",
        metadata={
            "description": "Resume/CV profiles embeddings",
            "hnsw:space": "cosine",  # FIX: dùng cosine thay vì L2 (mặc định)
        },
    )

    # Chuẩn bị metadata cho resumes
    resume_ids = [str(cid) for cid in resume_df["candidate_id"].tolist()]
    resume_metadatas = []
    for _, row in resume_df.iterrows():
        meta = {
            "candidate_id": str(row.get("candidate_id", "")),
            "source": str(row.get("source", "")),
            "category": str(row.get("category", "")),
            "skill_count": int(row.get("skill_count", 0)),
        }
        # Lưu skills dưới dạng string vì ChromaDB metadata chỉ hỗ trợ primitive types
        skills = row.get("skills", [])
        # PyArrow may deserialize list columns as numpy ndarray
        if isinstance(skills, (list, tuple)) or (
            hasattr(skills, '__iter__') and hasattr(skills, '__len__')
            and not isinstance(skills, (str, bytes, dict))
        ):
            meta["skills"] = ", ".join(str(s) for s in skills if s)
        else:
            meta["skills"] = str(skills) if pd.notna(skills) else ""
        resume_metadatas.append(meta)

    # Thêm resumes vào collection (chia nhỏ nếu quá nhiều để tránh lỗi bộ nhớ)
    CHUNK_SIZE = 500
    for i in range(0, len(resume_ids), CHUNK_SIZE):
        end = min(i + CHUNK_SIZE, len(resume_ids))
        resumes_collection.add(
            ids=resume_ids[i:end],
            embeddings=resume_embeddings[i:end].tolist(),
            documents=resume_texts[i:end],
            metadatas=resume_metadatas[i:end],
        )
    print(f"  - Đã thêm {len(resume_ids)} resume embeddings vào collection 'resumes'")

    # Tạo collection mới cho jobs
    # V2.2 FIX: Dùng cosine distance thay vì L2 (mặc định)
    jobs_collection = client.create_collection(
        name="jobs",
        metadata={
            "description": "Job posting profiles embeddings",
            "hnsw:space": "cosine",  # FIX: dùng cosine thay vì L2 (mặc định)
        },
    )

    # Chuẩn bị metadata cho jobs
    job_ids = [str(jid) for jid in job_df["job_id"].tolist()]
    job_metadatas = []
    for _, row in job_df.iterrows():
        meta = {
            "job_id": str(row.get("job_id", "")),
            "source": str(row.get("source", "")),
            "role": str(row.get("role", "")),
            "company": str(row.get("company", "")),
            "location": str(row.get("location", "")),
            "seniority": str(row.get("seniority", "")),
            "category": str(row.get("category", "")),
            "skill_count": int(row.get("skill_count", 0)),
        }
        skills = row.get("skills", [])
        # PyArrow may deserialize list columns as numpy ndarray
        if isinstance(skills, (list, tuple)) or (
            hasattr(skills, '__iter__') and hasattr(skills, '__len__')
            and not isinstance(skills, (str, bytes, dict))
        ):
            meta["skills"] = ", ".join(str(s) for s in skills if s)
        else:
            meta["skills"] = str(skills) if pd.notna(skills) else ""
        job_metadatas.append(meta)

    # Thêm jobs vào collection
    for i in range(0, len(job_ids), CHUNK_SIZE):
        end = min(i + CHUNK_SIZE, len(job_ids))
        jobs_collection.add(
            ids=job_ids[i:end],
            embeddings=job_embeddings[i:end].tolist(),
            documents=job_texts[i:end],
            metadatas=job_metadatas[i:end],
        )
    print(f"  - Đã thêm {len(job_ids)} job embeddings vào collection 'jobs'")

    # --- Tổng kết ---
    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    print("HOÀN THÀNH TẠO VECTOR INDEX")
    print("=" * 60)
    print(f"  Tổng số embeddings: {len(resume_ids) + len(job_ids)}")
    print(f"    - Resumes: {len(resume_ids)}")
    print(f"    - Jobs: {len(job_ids)}")
    print(f"  Embedding dimension: {EMBEDDING_DIMENSION}")
    print(f"  ChromaDB path: {chroma_dir}")
    print(f"  Thời gian tổng: {total_time:.1f}s")
    print("=" * 60)


def search_similar(query_text: str, collection_name: str, n_results: int = 5) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa (semantic search) trong ChromaDB.

    Args:
        query_text: Chuỗi truy vấn (ví dụ: "Python developer with ML experience")
        collection_name: Tên collection để tìm kiếm ("resumes" hoặc "jobs")
        n_results: Số lượng kết quả trả về (mặc định 5)

    Returns:
        List các dict chứa thông tin kết quả:
        [{
            "id": str,
            "document": str,
            "metadata": dict,
            "distance": float,
        }, ...]
    """
    chroma_dir = Path(OUTPUT_DIR) / "chroma_db"

    if not chroma_dir.exists():
        print(f"[WARNING] ChromaDB chưa được khởi tạo tại: {chroma_dir}")
        print("  Vui lòng chạy create_vector_index() trước.")
        return []

    # Kết nối đến ChromaDB
    client = chromadb.PersistentClient(path=str(chroma_dir))

    try:
        collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"[ERROR] Không thể truy cập collection '{collection_name}': {e}")
        return []

    # Tải model embedding để encode query
    model = SentenceTransformer(EMBEDDING_MODEL)
    query_embedding = model.encode([query_text], convert_to_numpy=True)[0].tolist()

    # Thực hiện tìm kiếm
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"],
    )

    # Định dạng kết quả trả về
    formatted_results = []
    if results and results["ids"] and results["ids"][0]:
        for i in range(len(results["ids"][0])):
            result = {
                "id": results["ids"][0][i],
                "document": results["documents"][0][i] if results["documents"] else "",
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else None,
            }
            formatted_results.append(result)

    return formatted_results


def main():
    """Entry point cho pipeline orchestrator."""
    try:
        create_vector_index()
    except Exception as e:
        print(f"\n[FATAL ERROR] Lỗi khi tạo vector index: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
