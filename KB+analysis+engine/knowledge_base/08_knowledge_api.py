"""
08_knowledge_api.py - Knowledge API Layer
==========================================
Lớp giao diện chính để truy vấn Career Knowledge Base.

Module này cung cấp các hàm và class để:
1. Trích xuất kỹ năng từ văn bản (sử dụng ontology đã xây dựng)
2. Gợi ý công việc phù hợp dựa trên kỹ năng CV (Jaccard similarity)
3. Phân tích khoảng cách kỹ năng (skill gap) cho vai trò mục tiêu
4. Tạo lộ trình chuyển đổi nghề nghiệp (career roadmap) dựa trên đồ thị
5. Thống kê kỹ năng theo vai trò
6. Tìm kiếm ngữ nghĩa (semantic search) qua ChromaDB

Tất cả dữ liệu được tải một lần khi khởi tạo CareerKnowledgeBase class
để tối ưu hiệu suất truy vấn lặp lại.
"""

import json
import os
import re
import sys
import warnings
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

# Thêm thư mục knowledge_base vào path để import config và các module khác
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    CAREER_GRAPH_PATH,
    JOB_PROFILES_PATH,
    OUTPUT_DIR,
    RESUME_PROFILES_PATH,
    ROLE_SKILL_MATRIX_PATH,
    SKILL_ONTOLOGY_PATH,
    DEFAULT_SEED_SKILLS,
    MANUAL_ALIASES,
)


# ============================================================
# 1. CÁC HÀM TIỆN ÍCH (UTILITY FUNCTIONS)
# ============================================================

def _load_json_safe(path: Path, description: str = "JSON") -> Optional[dict]:
    """Tải file JSON an toàn, trả về None nếu file không tồn tại hoặc lỗi."""
    if not path.exists():
        warnings.warn(f"[WARN] File {description} không tồn tại: {path}")
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"[API] Đã tải {description}: {path.name}")
        return data
    except Exception as e:
        warnings.warn(f"[WARN] Không thể tải {description} từ {path}: {e}")
        return None


def _load_parquet_safe(path: Path, description: str = "Parquet") -> Optional[pd.DataFrame]:
    """Tải file Parquet an toàn, trả về None nếu file không tồn tại hoặc lỗi."""
    if not path.exists():
        warnings.warn(f"[WARN] File {description} không tồn tại: {path}")
        return None
    try:
        df = pd.read_parquet(path)
        print(f"[API] Đã tải {description}: {len(df)} records từ {path.name}")
        return df
    except Exception as e:
        warnings.warn(f"[WARN] Không thể tải {description} từ {path}: {e}")
        return None


def _load_csv_safe(path: Path, description: str = "CSV") -> Optional[pd.DataFrame]:
    """Tải file CSV an toàn, trả về None nếu file không tồn tại hoặc lỗi."""
    if not path.exists():
        warnings.warn(f"[WARN] File {description} không tồn tại: {path}")
        return None
    try:
        df = pd.read_csv(path)
        print(f"[API] Đã tải {description}: {len(df)} dòng từ {path.name}")
        return df
    except Exception as e:
        warnings.warn(f"[WARN] Không thể tải {description} từ {path}: {e}")
        return None


def _escape_regex_pattern(skill: str) -> str:
    """Escape các ký tự đặc biệt trong tên kỹ năng để dùng trong regex."""
    escaped = re.escape(skill)
    escaped = escaped.replace(r"\ ", r"[\s\-]")
    return escaped


def _build_regex_patterns(ontology: Dict[str, str]) -> List[Tuple[re.Pattern, str]]:
    """Xây dựng danh sách compiled regex patterns từ ontology."""
    all_terms: Set[str] = set()
    term_to_canonical: Dict[str, str] = {}

    for alias, canonical in ontology.items():
        alias_clean = alias.strip().lower()
        canonical_clean = canonical.strip()
        all_terms.add(alias_clean)
        term_to_canonical[alias_clean] = canonical_clean
        all_terms.add(canonical_clean.lower())
        term_to_canonical[canonical_clean.lower()] = canonical_clean

    sorted_terms = sorted(all_terms, key=len, reverse=True)

    patterns = []
    for term in sorted_terms:
        try:
            pattern_str = _escape_regex_pattern(term)
            full_pattern = rf"(?i)\b{pattern_str}\b"
            compiled = re.compile(full_pattern)
            canonical = term_to_canonical.get(term, term)
            patterns.append((compiled, canonical))
        except re.error:
            continue

    return patterns


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Tính Jaccard similarity giữa hai tập hợp."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _skill_coverage(cv_skills: set, required_skills: set) -> float:
    """
    Tính coverage: tỷ lệ skills JD được đáp ứng bởi CV.

    Coverage = |intersection| / |required_skills|

    Khác với Jaccard (|A ∩ B| / |A ∪ B|), coverage tập trung vào
    việc CV đáp ứng bao nhiêu % yêu cầu của JD, không bị penalty
    khi CV có nhiều skills hơn JD yêu cầu.
    """
    if not required_skills:
        return 0.0
    intersection = len(cv_skills & required_skills)
    return intersection / len(required_skills)


# ============================================================
# V2.4 DOMAIN-AWARE SCORING
# ============================================================
# Fix cho trường hợp semantic search không bắt được domain jobs:
# VD: Frontend CV trả về IT Support/Sales Admin thay vì React Developer.
# Nguyên nhân: embedding model đa ngôn ngữ không phân biệt rõ domain
# trong short text. Giải pháp 2 lớp:
#   1. Query enrichment - prepend domain hint để định hướng embedding
#   2. Keyword bonus - boost jobs có domain match trong title/role

# Domain keyword sets (lowercase)
_DOMAIN_KEYWORDS = {
    "frontend": {
        "keywords": [
            "frontend", "front-end", "front end",
            "react", "reactjs", "react.js",
            "vue", "vuejs", "vue.js",
            "angular", "angularjs", "angular.js",
            "next.js", "nextjs",
            "svelte", "tailwind", "webpack",
            "ui engineer", "web developer",
            "typescript", "javascript",
        ],
        "hint": "Frontend Web Developer role with React JavaScript CSS HTML",
    },
    "backend": {
        "keywords": [
            "backend", "back-end", "back end",
            "server", "api developer",
            "spring", "django", "fastapi", "flask",
            "laravel", "express", "nest",
            "microservices", "database",
        ],
        "hint": "Backend Developer role with API database server",
    },
    "ai_ml": {
        "keywords": [
            "ai", "ml", "machine learning", "deep learning",
            "data scientist", "data science",
            "nlp", "computer vision",
            "tensorflow", "pytorch", "scikit",
            "llm", "rag", "langchain",
            "neural", "model training",
        ],
        "hint": "AI Machine Learning Engineer role with Python model training",
    },
    "devops": {
        "keywords": [
            "devops", "sre", "site reliability",
            "kubernetes", "k8s", "docker",
            "terraform", "ansible",
            "ci/cd", "cicd", "jenkins",
            "aws", "azure", "gcp",
            "infrastructure", "cloud engineer",
        ],
        "hint": "DevOps Cloud Engineer role with Kubernetes Docker CI/CD",
    },
    "data": {
        "keywords": [
            "data engineer", "data analytics",
            "etl", "data pipeline",
            "spark", "kafka", "airflow",
            "bigquery", "snowflake",
            "sql", "data warehouse",
        ],
        "hint": "Data Engineer role with SQL ETL pipeline",
    },
    "mobile": {
        "keywords": [
            "mobile", "ios", "android",
            "flutter", "react native",
            "swift", "kotlin",
            "mobile developer",
        ],
        "hint": "Mobile Developer role",
    },
    "fullstack": {
        "keywords": [
            "fullstack", "full-stack", "full stack",
        ],
        "hint": "Full-stack Developer role",
    },
}


def _detect_domain(text: str) -> Optional[str]:
    """
    Detect domain từ text dựa trên keyword counting.

    Trả về domain có nhiều keyword match nhất, hoặc None nếu không rõ domain.
    Cần tối thiểu 2 keyword matches để xác định domain (tránh false positive
    khi text chỉ chứa 1 keyword chung chung như "aws" hay "sql").
    """
    if not text or not text.strip():
        return None

    text_lower = text.lower()
    domain_scores = {}

    for domain, config in _DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in config["keywords"] if kw in text_lower)
        if score >= 2:  # Cần ít nhất 2 keyword matches
            domain_scores[domain] = score

    if not domain_scores:
        return None

    # Trả về domain có score cao nhất
    return max(domain_scores.items(), key=lambda x: x[1])[0]


def _enrich_query(query: str, domain: Optional[str]) -> str:
    """
    Enrich query bằng cách prepend domain hint.

    Giúp embedding model định hướng tốt hơn khi query CV ngắn hoặc
    chứa nhiều thông tin không liên quan đến domain.

    VD: "Frontend Developer với 2 năm..." →
        "Frontend Web Developer role with React JavaScript CSS HTML.
         Frontend Developer với 2 năm..."
    """
    if not domain or domain not in _DOMAIN_KEYWORDS:
        return query

    hint = _DOMAIN_KEYWORDS[domain]["hint"]
    return f"{hint}. {query}"


def _compute_keyword_bonus(
    meta: dict, document: str, domain: Optional[str]
) -> float:
    """
    Tính keyword bonus dựa trên domain match trong title/role/document.

    Returns:
        Bonus score trong [0.0, 0.10] - tối đa 10% boost
        - 0.05 cho mỗi domain keyword match trong role/title (max 2 matches)
        - Bonus nhỏ nếu có keyword trong document text
    """
    if not domain or domain not in _DOMAIN_KEYWORDS:
        return 0.0

    keywords = _DOMAIN_KEYWORDS[domain]["keywords"]
    role = str(meta.get("role", "")).lower()
    title = str(meta.get("title", "")).lower()
    doc_lower = (document or "").lower()

    # Count matches trong role/title (quan trọng nhất)
    title_role_matches = sum(1 for kw in keywords if kw in role or kw in title)
    title_role_bonus = min(0.08, title_role_matches * 0.04)  # max 8%

    # Bonus nhỏ nếu có bất kỳ keyword nào trong document (max 2%)
    doc_bonus = 0.02 if any(kw in doc_lower for kw in keywords) else 0.0

    return title_role_bonus + doc_bonus


def _get_semantic_scores(
    cv_text: str,
    collection_name: str = "jobs",
    max_candidates: int = 100,
) -> Dict[str, float]:
    """
    Lấy semantic similarity scores từ ChromaDB.

    Query top `max_candidates` jobs tương tự nhất với CV text,
    trả về Dict[job_id → cosine_similarity (0-1)].

    ChromaDB với metric="cosine" trả về distance = 1 - similarity,
    nên ta dùng similarity = 1 - distance, clamp về [0, 1].
    """
    if not cv_text or not cv_text.strip():
        return {}

    try:
        import chromadb
    except ImportError:
        warnings.warn("[WARN] Thiếu chromadb, bỏ qua semantic scoring.")
        return {}

    chroma_dir = OUTPUT_DIR / "chroma_db"
    if not chroma_dir.exists():
        return {}

    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection(name=collection_name)

        results = collection.query(
            query_texts=[cv_text],
            n_results=max_candidates,
        )

        scores: Dict[str, float] = {}
        if results and results.get("ids") and results["ids"][0]:
            ids = results["ids"][0]
            distances = results.get("distances", [[]])[0]
            for job_id, distance in zip(ids, distances):
                # cosine similarity = 1 - cosine_distance
                similarity = max(0.0, min(1.0, 1.0 - distance))
                scores[str(job_id)] = similarity

        return scores
    except Exception as e:
        warnings.warn(f"[WARN] Lỗi khi tính semantic scores: {e}")
        return {}


# V2.2 CACHE: Cache ontology ở module level để tránh load lại nhiều lần.
# Trước đây, mỗi lần gọi extract_skills() → _load_or_build_ontology() → in log
# "[API] Đã tải ontology" → gây spam 200+ dòng log khi semantic_search() fallback.
_CACHED_ONTOLOGY: Optional[Dict[str, str]] = None


def _load_or_build_ontology() -> Dict[str, str]:
    """Tải ontology từ file hoặc xây dựng từ cấu hình mặc định (cached)."""
    global _CACHED_ONTOLOGY
    if _CACHED_ONTOLOGY is not None:
        return _CACHED_ONTOLOGY

    ontology: Dict[str, str] = {}

    if SKILL_ONTOLOGY_PATH.exists():
        try:
            with open(SKILL_ONTOLOGY_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for alias, canonical in loaded.items():
                ontology[alias.lower().strip()] = canonical.strip()
            print(f"[API] Đã tải ontology: {len(ontology)} mappings")
        except Exception as e:
            warnings.warn(f"[WARN] Không thể tải ontology: {e}")
            ontology = {}

    if not ontology:
        for skill in DEFAULT_SEED_SKILLS:
            canonical = skill.strip()
            ontology[canonical.lower()] = canonical

    for alias, canonical in MANUAL_ALIASES.items():
        ontology[alias.lower().strip()] = canonical.strip()

    _CACHED_ONTOLOGY = ontology
    return ontology


def _find_closest_role(
    current_skills: List[str],
    adjacency: Dict[str, List[dict]],
    role_skill_matrix_df: Optional[pd.DataFrame] = None,
) -> Optional[str]:
    """Tìm vai trò gần nhất với tập kỹ năng hiện có của ứng viên."""
    if not current_skills:
        return None

    current_set = set(s.strip() for s in current_skills if s and s.strip())
    available_roles = list(adjacency.keys())

    if not available_roles:
        return None

    if role_skill_matrix_df is not None and not role_skill_matrix_df.empty:
        best_role = None
        best_score = -1.0

        for role in available_roles:
            role_data = role_skill_matrix_df[
                role_skill_matrix_df["role"].str.lower() == role.lower()
            ]
            if role_data.empty:
                continue
            role_skills = set(role_data[role_data["frequency_pct"] >= 30]["skill"].tolist())
            score = _jaccard_similarity(current_set, role_skills)
            if score > best_score:
                best_score = score
                best_role = role

        if best_role and best_score > 0:
            return best_role

    best_role = None
    best_score = -1.0
    for role in available_roles:
        role_words = set(role.lower().split())
        current_lower = set(s.lower() for s in current_set)
        overlap = len(role_words & current_lower)
        if overlap > best_score:
            best_score = overlap
            best_role = role

    return best_role if best_score > 0 else available_roles[0] if available_roles else None


def _bfs_shortest_path(
    adjacency: Dict[str, List[dict]],
    start: str,
    target: str,
) -> Optional[List[str]]:
    """Tìm đường đi ngắn nhất bằng BFS trên đồ thị chuyển đổi."""
    start_lower = start.lower()
    target_lower = target.lower()

    node_map: Dict[str, str] = {}
    for node in adjacency:
        node_map[node.lower()] = node

    if start_lower not in node_map:
        return None
    if target_lower not in node_map:
        return None

    start_actual = node_map[start_lower]
    target_actual = node_map[target_lower]

    if start_actual == target_actual:
        return [start_actual]

    visited: Set[str] = {start_actual}
    queue: deque = deque([(start_actual, [start_actual])])

    while queue:
        current, path = queue.popleft()

        for edge in adjacency.get(current, []):
            neighbor = edge["to"]
            if neighbor in visited:
                continue

            new_path = path + [neighbor]

            if neighbor.lower() == target_lower:
                return new_path

            visited.add(neighbor)
            queue.append((neighbor, new_path))

    return None


# ============================================================
# 2. CÁC HÀM API ĐỘC LẬP (STANDALONE FUNCTIONS)
# ============================================================

def extract_skills(text: str, ontology: Optional[Dict[str, str]] = None) -> List[str]:
    """
    Trích xuất danh sách kỹ năng từ văn bản đầu vào.

    Sử dụng regex matching với word boundary để tìm các kỹ năng trong text,
    sau đó ánh xạ về tên chuẩn (canonical) thông qua ontology.

    Args:
        text: Văn bản cần trích xuất kỹ năng
        ontology: Dict {alias_lower: canonical_name} (optional, tự tải nếu None)

    Returns:
        List[str]: Danh sách các kỹ năng canonical duy nhất, đã sắp xếp
    """
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return []

    if ontology is None:
        ontology = _load_or_build_ontology()

    if not ontology:
        warnings.warn("[WARN] Ontology rỗng, không thể trích xuất kỹ năng.")
        return []

    patterns = _build_regex_patterns(ontology)

    found_canonical: Set[str] = set()
    for pattern, canonical in patterns:
        if pattern.search(text):
            found_canonical.add(canonical)

    return sorted(found_canonical)


def match_jobs(
    cv_skills: List[str],
    cv_text: str = "",
    top_n: int = 10,
    job_profiles_df: Optional[pd.DataFrame] = None,
    semantic_weight: float = 0.7,
    coverage_weight: float = 0.3,
) -> List[dict]:
    """
    Matching Engine V2 - Hybrid Scoring: Semantic + Skill Coverage.

    Công thức:
        final_score = (semantic_weight * semantic_similarity
                     + coverage_weight * skill_coverage) * 100

    Trong đó:
        - semantic_similarity: cosine similarity từ ChromaDB embeddings (0-1)
        - skill_coverage: |cv_skills ∩ job_skills| / |job_skills| (0-1)

    Ưu điểm so với V1 (Jaccard thuần):
        - Coverage không bị penalty khi CV có nhiều skills hơn JD
        - Semantic bắt được các trường hợp ontology chưa hoàn hảo
          (ví dụ: "Machine Learning" trong CV ↔ "ML" trong JD)
        - Trọng số 0.7/0.3 phù hợp với free-text dài + skill extraction tốt

    Args:
        cv_skills: Danh sách kỹ năng của ứng viên (đã extract)
        cv_text: Văn bản CV gốc để query semantic (optional nhưng recommended)
        top_n: Số lượng kết quả trả về (mặc định 10)
        job_profiles_df: DataFrame job profiles (optional, tự tải nếu None)
        semantic_weight: Trọng số cho semantic similarity (mặc định 0.7)
        coverage_weight: Trọng số cho skill coverage (mặc định 0.3)

    Returns:
        List[dict]: Mỗi dict chứa:
            - job_id, role, company, location, salary_vnd
            - match_score: final_score (0-100)
            - semantic_score: thành phần semantic (0-1)
            - coverage_score: thành phần coverage (0-1)
            - matched_skills: skills CV đáp ứng
            - missing_skills: skills JD yêu cầu mà CV thiếu
    """
    if not cv_skills and not cv_text:
        return []

    if job_profiles_df is None:
        job_profiles_df = _load_parquet_safe(JOB_PROFILES_PATH, "Job Profiles")

    if job_profiles_df is None or job_profiles_df.empty:
        warnings.warn("[WARN] Không có dữ liệu job profiles để gợi ý.")
        return []

    cv_skill_set = set(s.strip() for s in cv_skills if s and s.strip())

    # Lấy semantic scores từ ChromaDB (top 100 candidates)
    semantic_scores: Dict[str, float] = {}
    if cv_text and cv_text.strip():
        semantic_scores = _get_semantic_scores(cv_text, collection_name="jobs", max_candidates=200)

    results = []

    for _, row in job_profiles_df.iterrows():
        job_id = str(row.get("job_id", ""))

        # Parse job skills
        job_skills_raw = row.get("skills", [])
        # PyArrow may deserialize list columns as numpy ndarray
        if isinstance(job_skills_raw, (list, tuple)) or (
            hasattr(job_skills_raw, '__iter__') and hasattr(job_skills_raw, '__len__')
            and not isinstance(job_skills_raw, (str, bytes, dict))
        ):
            job_skill_set = set(str(s).strip() for s in job_skills_raw if s)
        elif isinstance(job_skills_raw, str) and job_skills_raw.strip():
            job_skill_set = set(s.strip() for s in job_skills_raw.split(",") if s.strip())
        else:
            job_skill_set = set()

        # V1 fallback: Jaccard nếu không có cv_text
        if not cv_text and not job_skill_set:
            continue

        # Tính coverage (ưu tiên chính)
        coverage = _skill_coverage(cv_skill_set, job_skill_set) if job_skill_set else 0.0

        # Lấy semantic score từ dict đã query
        semantic = semantic_scores.get(job_id, 0.0)

        # Nếu không có cv_text, fallback về Jaccard để tương thích V1
        if not cv_text:
            if not job_skill_set:
                continue
            semantic = _jaccard_similarity(cv_skill_set, job_skill_set)
            # Dùng Jaccard thay cho cả 2 thành phần
            final_score = semantic * 100
        else:
            # Hybrid scoring: 0.7 semantic + 0.3 coverage
            final_score = (
                semantic_weight * semantic + coverage_weight * coverage
            ) * 100

        if final_score <= 0:
            continue

        matched = sorted(cv_skill_set & job_skill_set)
        missing = sorted(job_skill_set - cv_skill_set)

        salary_vnd = None
        if "salary_vnd" in row.index and pd.notna(row.get("salary_vnd")):
            salary_vnd = row["salary_vnd"]

        results.append({
            "job_id": job_id,
            "role": str(row.get("role", "")),
            "company": str(row.get("company", "")),
            "location": str(row.get("location", "")),
            "salary_vnd": salary_vnd,
            "match_score": round(final_score, 2),
            "semantic_score": round(semantic, 4),
            "coverage_score": round(coverage, 4),
            "matched_skills": matched,
            "missing_skills": missing,
        })

    results.sort(key=lambda x: x["match_score"], reverse=True)

    return results[:top_n]


def find_skill_gap(
    current_skills: List[str],
    target_role: str,
    role_skill_matrix_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Phân tích khoảng cách kỹ năng giữa kỹ năng hiện có và vai trò mục tiêu.

    Args:
        current_skills: Danh sách kỹ năng hiện có của ứng viên
        target_role: Vai trò mục tiêu (ví dụ: "AI Engineer")
        role_skill_matrix_df: DataFrame role-skill matrix (optional)

    Returns:
        dict: Kết quả phân tích skill gap
    """
    empty_result = {
        "target_role": target_role,
        "current_skills": sorted(current_skills),
        "have": [],
        "need": [],
        "match_percentage": 0.0,
    }

    if not target_role:
        return empty_result

    if role_skill_matrix_df is None:
        role_skill_matrix_df = _load_csv_safe(ROLE_SKILL_MATRIX_PATH, "Role-Skill Matrix")

    if role_skill_matrix_df is None or role_skill_matrix_df.empty:
        warnings.warn("[WARN] Không có dữ liệu role-skill matrix.")
        return empty_result

    # Lọc theo target_role (case-insensitive exact match trước)
    role_data = role_skill_matrix_df[
        role_skill_matrix_df["role"].str.lower() == target_role.strip().lower()
    ]

    if role_data.empty:
        # Thử partial match nếu exact match không tìm thấy
        role_data = role_skill_matrix_df[
            role_skill_matrix_df["role"].str.contains(
                re.escape(target_role.strip()), case=False, na=False
            )
        ]

    if role_data.empty:
        warnings.warn(f"[WARN] Không tìm thấy vai trò '{target_role}' trong ma trận.")
        return empty_result

    # Lấy các kỹ năng bắt buộc (frequency_pct >= 50%)
    required_skills_df = role_data[role_data["frequency_pct"] >= 50.0]
    required_skills = set(required_skills_df["skill"].tolist())

    if not required_skills:
        # Nếu không có skill nào >= 50%, lấy tất cả skills của role
        required_skills = set(role_data["skill"].tolist())

    current_set = set(s.strip() for s in current_skills if s and s.strip())

    have = sorted(current_set & required_skills)
    need = sorted(required_skills - current_set)

    match_pct = (len(have) / len(required_skills) * 100) if required_skills else 0.0

    return {
        "target_role": target_role,
        "current_skills": sorted(current_skills),
        "have": have,
        "need": need,
        "match_percentage": round(match_pct, 2),
    }


def generate_roadmap(
    current_skills: List[str],
    target_role: str,
    career_graph: Optional[dict] = None,
    role_skill_matrix_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Tạo lộ trình chuyển đổi nghề nghiệp từ vai trò hiện tại đến vai trò mục tiêu.

    Sử dụng BFS trên đồ thị chuyển đổi nghề nghiệp để tìm đường đi ngắn nhất.

    Args:
        current_skills: Danh sách kỹ năng hiện có
        target_role: Vai trò mục tiêu
        career_graph: Dict chứa transitions (optional, tự tải nếu None)
        role_skill_matrix_df: DataFrame role-skill matrix (optional)

    Returns:
        dict: Lộ trình chuyển đổi nghề nghiệp
    """
    empty_result = {
        "start_role": None,
        "target_role": target_role,
        "path": [],
        "steps": [],
        "total_new_skills": [],
    }

    if not target_role:
        return empty_result

    if career_graph is None:
        career_graph = _load_json_safe(CAREER_GRAPH_PATH, "Career Graph")

    if career_graph is None:
        warnings.warn("[WARN] Không có dữ liệu career graph.")
        return empty_result

    transitions = career_graph.get("transitions", [])
    if not transitions:
        warnings.warn("[WARN] Career graph không có transitions.")
        return empty_result

    # Xây dựng adjacency list cho BFS (đồ thị vô hướng để tìm đường linh hoạt)
    adjacency: Dict[str, List[dict]] = {}
    for t in transitions:
        from_role = t["from"]
        to_role = t["to"]

        if from_role not in adjacency:
            adjacency[from_role] = []
        if to_role not in adjacency:
            adjacency[to_role] = []

        adjacency[from_role].append(t)
        # Thêm cạnh ngược để BFS có thể tìm đường theo cả hai hướng
        reverse_t = {
            "from": to_role,
            "to": from_role,
            "weight": t["weight"],
            "shared_skills": t["shared_skills"],
            "new_skills_needed": t.get("shared_skills", []),
        }
        adjacency[to_role].append(reverse_t)

    # Xác định start_role: vai trò gần nhất với current_skills
    start_role = _find_closest_role(current_skills, adjacency, role_skill_matrix_df)

    if start_role is None:
        all_roles = career_graph.get("roles", [])
        if all_roles:
            start_role = all_roles[0]
        else:
            return empty_result

    target_normalized = target_role.strip()

    # Kiểm tra xem start và target có giống nhau không
    if start_role.lower() == target_normalized.lower():
        return {
            "start_role": start_role,
            "target_role": target_role,
            "path": [start_role],
            "steps": [],
            "total_new_skills": [],
        }

    # BFS tìm đường đi ngắn nhất
    path = _bfs_shortest_path(adjacency, start_role, target_normalized)

    if path is None:
        warnings.warn(
            f"[WARN] Không tìm thấy đường đi từ '{start_role}' đến '{target_role}'."
        )
        return {
            "start_role": start_role,
            "target_role": target_role,
            "path": [],
            "steps": [],
            "total_new_skills": [],
        }

    # Xây dựng chi tiết từng bước
    steps = []
    all_new_skills: Set[str] = set()

    for i in range(len(path) - 1):
        from_r = path[i]
        to_r = path[i + 1]

        step_info = None
        for t in adjacency.get(from_r, []):
            if t["to"].lower() == to_r.lower():
                step_info = t
                break

        if step_info is None:
            step_info = {"shared_skills": [], "new_skills_needed": []}

        new_skills = step_info.get("new_skills_needed", [])
        all_new_skills.update(new_skills)

        steps.append({
            "from": from_r,
            "to": to_r,
            "shared_skills": step_info.get("shared_skills", []),
            "skills_to_learn": new_skills,
        })

    return {
        "start_role": start_role,
        "target_role": target_role,
        "path": path,
        "steps": steps,
        "total_new_skills": sorted(all_new_skills),
    }


def get_role_stats(
    role: str,
    role_skill_matrix_df: Optional[pd.DataFrame] = None,
) -> dict:
    """
    Lấy thống kê kỹ năng cho một vai trò cụ thể.

    Args:
        role: Tên vai trò (ví dụ: "AI Engineer")
        role_skill_matrix_df: DataFrame role-skill matrix (optional)

    Returns:
        dict: Thống kê gồm role, total_jobs, top_skills
    """
    empty_result = {"role": role, "total_jobs": 0, "top_skills": []}

    if not role:
        return empty_result

    if role_skill_matrix_df is None:
        role_skill_matrix_df = _load_csv_safe(ROLE_SKILL_MATRIX_PATH, "Role-Skill Matrix")

    if role_skill_matrix_df is None or role_skill_matrix_df.empty:
        return empty_result

    role_data = role_skill_matrix_df[
        role_skill_matrix_df["role"].str.lower() == role.strip().lower()
    ]

    if role_data.empty:
        role_data = role_skill_matrix_df[
            role_skill_matrix_df["role"].str.contains(
                re.escape(role.strip()), case=False, na=False
            )
        ]

    if role_data.empty:
        return empty_result

    role_data = role_data.sort_values("frequency_pct", ascending=False)

    total_jobs = int(role_data["total_jobs_in_role"].iloc[0]) \
        if "total_jobs_in_role" in role_data.columns else 0

    top_skills = []
    for _, row in role_data.iterrows():
        top_skills.append({
            "skill": row["skill"],
            "frequency_pct": float(row["frequency_pct"]),
            "count": int(row["count"]),
        })

    return {
        "role": role,
        "total_jobs": total_jobs,
        "top_skills": top_skills,
    }


def semantic_search(
    query: str,
    collection_name: str = "jobs",
    n_results: int = 5,
    hybrid: bool = True,
    semantic_weight: float = 0.6,
    coverage_weight: float = 0.4,
) -> List[dict]:
    """
    Tìm kiếm ngữ nghĩa (semantic search) trong ChromaDB.

    V2.2 Hybrid Mode (mặc định): Kết hợp semantic similarity + skill coverage
    để re-rank kết quả, tránh trường hợp match bừa "Sales Admin" cho CV Frontend.

    Cơ chế hybrid:
        1. Query top 100 candidates từ ChromaDB (semantic similarity)
        2. Extract skills từ query text bằng ontology
        3. Tính skill coverage cho mỗi candidate:
           coverage = |query_skills ∩ candidate_skills| / |candidate_skills|
        4. Re-rank theo:
           final_score = semantic_weight*semantic + coverage_weight*coverage
        5. Trả về top n_results theo final_score

    Ưu điểm:
        - Semantic bắt được ngữ cảnh ("AI engineer" ≈ "ML researcher")
        - Coverage đảm bảo candidate có đủ skills yêu cầu (React, Python, ...)
        - Loại bỏ false positives (Sales Admin match CV Frontend)

    Args:
        query: Chuỗi truy vấn (CV text hoặc mô tả công việc)
        collection_name: Tên collection ("resumes" hoặc "jobs")
        n_results: Số lượng kết quả trả về
        hybrid: Bật hybrid scoring (mặc định True). Set False để dùng pure semantic.
        semantic_weight: Trọng số cho semantic similarity (mặc định 0.6)
        coverage_weight: Trọng số cho skill coverage (mặc định 0.4)

    Returns:
        List[dict]: Mỗi dict chứa:
            - id: ID của document trong ChromaDB
            - document: Text đầy đủ của document
            - distance: Cosine distance từ ChromaDB (1 - similarity)
            - metadata: Metadata (role, company, skills, ...)
            - semantic_score: 1 - distance, trong [0, 1]
            - coverage_score: Skill coverage trong [0, 1]
            - final_score: Trọng số kết hợp (khi hybrid=True)
    """
    try:
        import chromadb
    except ImportError:
        warnings.warn("[WARN] Thiếu thư viện chromadb cho semantic search.")
        return []

    chroma_dir = Path(OUTPUT_DIR) / "chroma_db"

    if not chroma_dir.exists():
        warnings.warn(f"[WARN] ChromaDB chưa được khởi tạo tại: {chroma_dir}")
        return []

    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        collection = client.get_collection(name=collection_name)

        # V2.4 DOMAIN-AWARE: Detect domain và enrich query để embedding model
        # định hướng tốt hơn. VD: Frontend CV → prepend "Frontend Web Developer..."
        query_domain = _detect_domain(query)
        enriched_query = _enrich_query(query, query_domain)

        if query_domain and query_domain != _detect_domain(enriched_query):
            # Tránh detect lại domain sau khi enrich
            pass

        # Query nhiều hơn n_results để có buffer cho re-ranking
        query_count = max(n_results, 100) if hybrid else n_results

        results = collection.query(
            query_texts=[enriched_query],
            n_results=query_count,
        )

        output = []
        if results and results.get("ids"):
            ids = results["ids"][0]
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            # Extract query skills cho hybrid ranking (dùng original query)
            query_skills: Set[str] = set()
            if hybrid and query and query.strip():
                extracted = extract_skills(query)
                query_skills = set(s.strip().lower() for s in extracted if s and s.strip())

            for idx in range(len(ids)):
                # Semantic score = 1 - cosine_distance, clamp về [0, 1]
                raw_distance = distances[idx] if idx < len(distances) else 0
                semantic_score = max(0.0, min(1.0, 1.0 - raw_distance))

                # Parse candidate skills từ metadata
                meta = metadatas[idx] if idx < len(metadatas) else {}
                candidate_skills: Set[str] = set()
                if hybrid and meta.get("skills"):
                    raw_skills = meta["skills"]
                    if isinstance(raw_skills, str) and raw_skills.strip():
                        candidate_skills = set(
                            s.strip().lower() for s in raw_skills.split(",") if s.strip()
                        )
                    elif isinstance(raw_skills, (list, tuple)):
                        candidate_skills = set(
                            str(s).strip().lower() for s in raw_skills if s
                        )

                # V2.2 FALLBACK: Nếu metadata.skills trống (thường gặp ở TopCV data),
                # extract skills từ document text bằng ontology.
                # Tránh false negative coverage=0 khi job thực sự có skills nhưng
                # metadata không được làm đầy đủ ở bước 07_vector_indexer.
                if hybrid and not candidate_skills:
                    doc_text = documents[idx] if idx < len(documents) else ""
                    if doc_text and doc_text.strip():
                        try:
                            doc_skills = extract_skills(doc_text, ontology=None)
                            candidate_skills = set(
                                s.strip().lower() for s in doc_skills if s and s.strip()
                            )
                        except Exception:
                            # Silent fail - không để lỗi extract skills làm hỏng query
                            candidate_skills = set()

                # V2.3 COVERAGE: Count-based + richness penalty
                # Thay vì dùng ratio (intersection / query_skills) - phạt quá nặng
                # khi query CV dài (15 skills), giờ dùng count-based:
                #   match 5+ skills → coverage = 1.0
                #   match 1 skill → coverage = 0.2
                # Kèm richness penalty: jobs có <3 skills (thường là Sales Admin,
                # data TopCV chất lượng thấp) bị phạt coverage.
                # Công thức: coverage = min(1, intersection_count/5) * min(1, candidate_count/3)
                coverage = 0.0
                if hybrid and candidate_skills and query_skills:
                    intersection_count = len(query_skills & candidate_skills)
                    # Count-based coverage: 5+ matched skills = 1.0
                    base_coverage = min(1.0, intersection_count / 5.0)
                    # Richness penalty: jobs ít skills (data chất lượng thấp) bị phạt
                    richness = min(1.0, len(candidate_skills) / 3.0)
                    coverage = base_coverage * richness

                # V2.4 KEYWORD BONUS: Boost jobs có domain match trong title/role
                # Giải quyết vấn đề semantic search không phân biệt được domain
                # (VD: Frontend CV match Sales Admin do semantic score ngang nhau)
                doc_text = documents[idx] if idx < len(documents) else ""
                keyword_bonus = _compute_keyword_bonus(meta, doc_text, query_domain)

                # Final score (hybrid hoặc pure semantic)
                if hybrid and query_skills:
                    final_score = (
                        semantic_weight * semantic_score
                        + coverage_weight * coverage
                        + keyword_bonus
                    )
                else:
                    final_score = semantic_score + keyword_bonus

                output.append({
                    "id": ids[idx],
                    "document": documents[idx] if idx < len(documents) else "",
                    "distance": raw_distance,
                    "metadata": meta,
                    "semantic_score": round(semantic_score, 4),
                    "coverage_score": round(coverage, 4),
                    "keyword_bonus": round(keyword_bonus, 4),
                    "final_score": round(final_score, 4),
                })

            # Re-rank by final_score (hybrid) hoặc semantic (pure)
            if hybrid:
                output.sort(key=lambda x: x["final_score"], reverse=True)
                output = output[:n_results]

        return output

    except Exception as e:
        warnings.warn(f"[WARN] Lỗi khi tìm kiếm ngữ nghĩa: {e}")
        return []


# ============================================================
# 3. CLASS CareerKnowledgeBase - GIAO DIỆN CHÍNH
# ============================================================

class CareerKnowledgeBase:
    """
    Lớp giao diện chính để truy vấn Career Knowledge Base.

    Tải tất cả dữ liệu một lần khi khởi tạo để tối ưu hiệu suất
    truy vấn lặp lại. Cung cấp các phương thức:
    - extract_skills: Trích xuất kỹ năng từ văn bản
    - match_jobs: Gợi ý công việc phù hợp
    - find_skill_gap: Phân tích khoảng cách kỹ năng
    - generate_roadmap: Tạo lộ trình chuyển đổi nghề nghiệp
    - get_role_stats: Thống kê kỹ năng theo vai trò
    - semantic_search: Tìm kiếm ngữ nghĩa qua ChromaDB

    Usage:
        kb = CareerKnowledgeBase()
        skills = kb.extract_skills("Tôi biết Python, Machine Learning và TensorFlow")
        jobs = kb.match_jobs(skills, top_n=5)
        gap = kb.find_skill_gap(skills, "AI Engineer")
        roadmap = kb.generate_roadmap(skills, "ML Engineer")
        stats = kb.get_role_stats("Data Scientist")
        results = kb.semantic_search("kinh nghiệm xử lý ảnh y tế")
    """

    def __init__(self):
        """Khởi tạo và tải tất cả dữ liệu cần thiết."""
        print("=" * 60)
        print("KHỞI TẠO CAREER KNOWLEDGE BASE")
        print("=" * 60)

        # Tải ontology
        self.ontology = _load_or_build_ontology()
        print(f"[KB] Ontology: {len(self.ontology)} mappings")

        # Tải Job Profiles
        self.job_profiles_df = _load_parquet_safe(JOB_PROFILES_PATH, "Job Profiles")

        # Tải Resume Profiles
        self.resume_profiles_df = _load_parquet_safe(RESUME_PROFILES_PATH, "Resume Profiles")

        # Tải Role-Skill Matrix
        self.role_skill_matrix_df = _load_csv_safe(ROLE_SKILL_MATRIX_PATH, "Role-Skill Matrix")

        # Tải Career Graph
        self.career_graph = _load_json_safe(CAREER_GRAPH_PATH, "Career Graph")

        print("\n[KB] Khởi tạo hoàn tất!")
        print("=" * 60)

    def extract_skills(self, text: str) -> List[str]:
        """Trích xuất kỹ năng từ văn bản."""
        return extract_skills(text, ontology=self.ontology)

    def match_jobs(
        self,
        cv_skills: List[str],
        cv_text: str = "",
        top_n: int = 10,
        semantic_weight: float = 0.7,
        coverage_weight: float = 0.3,
    ) -> List[dict]:
        """
        Gợi ý công việc phù hợp - Hybrid Scoring V2.

        Args:
            cv_skills: Danh sách kỹ năng đã extract
            cv_text: Văn bản CV gốc (recommended để có semantic score)
            top_n: Số lượng kết quả
            semantic_weight: Trọng số semantic (mặc định 0.7)
            coverage_weight: Trọng số coverage (mặc định 0.3)
        """
        return match_jobs(
            cv_skills,
            cv_text=cv_text,
            top_n=top_n,
            job_profiles_df=self.job_profiles_df,
            semantic_weight=semantic_weight,
            coverage_weight=coverage_weight,
        )

    def find_skill_gap(self, current_skills: List[str], target_role: str) -> dict:
        """Phân tích khoảng cách kỹ năng cho vai trò mục tiêu."""
        return find_skill_gap(
            current_skills, target_role, role_skill_matrix_df=self.role_skill_matrix_df
        )

    def generate_roadmap(self, current_skills: List[str], target_role: str) -> dict:
        """Tạo lộ trình chuyển đổi nghề nghiệp."""
        return generate_roadmap(
            current_skills,
            target_role,
            career_graph=self.career_graph,
            role_skill_matrix_df=self.role_skill_matrix_df,
        )

    def get_role_stats(self, role: str) -> dict:
        """Lấy thống kê kỹ năng cho một vai trò."""
        return get_role_stats(role, role_skill_matrix_df=self.role_skill_matrix_df)

    def semantic_search(
        self, query: str, collection_name: str = "jobs", n_results: int = 5
    ) -> List[dict]:
        """Tìm kiếm ngữ nghĩa trong ChromaDB."""
        return semantic_search(query, collection_name=collection_name, n_results=n_results)

    def summary(self) -> dict:
        """Trả về tóm tắt trạng thái của Knowledge Base."""
        return {
            "ontology_size": len(self.ontology),
            "job_profiles_count": len(self.job_profiles_df) if self.job_profiles_df is not None else 0,
            "resume_profiles_count": len(self.resume_profiles_df) if self.resume_profiles_df is not None else 0,
            "role_skill_matrix_rows": len(self.role_skill_matrix_df) if self.role_skill_matrix_df is not None else 0,
            "career_graph_loaded": self.career_graph is not None,
            "unique_roles": (
                self.role_skill_matrix_df["role"].nunique()
                if self.role_skill_matrix_df is not None and not self.role_skill_matrix_df.empty
                else 0
            ),
        }


# ============================================================
# 4. DEMO / TEST KHI CHẠY TRỰC TIẾP
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("DEMO: CAREER KNOWLEDGE BASE API")
    print("=" * 70)

    # Khởi tạo Knowledge Base
    kb = CareerKnowledgeBase()

    # In tóm tắt
    print("\n--- Tóm tắt Knowledge Base ---")
    summary = kb.summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # Demo 1: Extract skills
    print("\n--- Demo 1: Extract Skills ---")
    sample_text = (
        "Tôi có kinh nghiệm 3 năm với Python, Machine Learning, TensorFlow, "
        "PyTorch, SQL, Docker và AWS. Đã xây dựng hệ thống RAG sử dụng LangChain "
        "và ChromaDB cho dự án Healthcare AI."
    )
    extracted = kb.extract_skills(sample_text)
    print(f"  Input: {sample_text[:80]}...")
    print(f"  Extracted skills ({len(extracted)}): {extracted}")

    # Demo 2: Match jobs - V2 Hybrid Scoring
    print("\n--- Demo 2: Match Jobs (V2 - Hybrid Scoring) ---")
    if extracted:
        # Pass cv_text để enable semantic scoring
        matched = kb.match_jobs(extracted, cv_text=sample_text, top_n=3)
        print(f"  Top {len(matched)} job matches:")
        for i, job in enumerate(matched, 1):
            print(f"    {i}. {job['role']} @ {job['company']}")
            print(f"       Final Score: {job['match_score']:.1f}/100")
            print(f"       Semantic: {job.get('semantic_score', 0):.3f} | "
                  f"Coverage: {job.get('coverage_score', 0):.3f}")
            print(f"       Matched: {job['matched_skills'][:5]}")
            print(f"       Missing: {job['missing_skills'][:3]}")
    else:
        print("  Không có skills để match.")

    # Demo 3: Skill gap
    print("\n--- Demo 3: Skill Gap Analysis ---")
    if extracted:
        gap = kb.find_skill_gap(extracted, "AI Engineer")
        print(f"  Target: {gap['target_role']}")
        print(f"  Match: {gap['match_percentage']:.1f}%")
        print(f"  Have: {gap['have'][:5]}")
        print(f"  Need: {gap['need'][:5]}")

    # Demo 4: Roadmap
    print("\n--- Demo 4: Career Roadmap ---")
    if extracted:
        roadmap = kb.generate_roadmap(extracted, "ML Engineer")
        print(f"  From: {roadmap['start_role']}")
        print(f"  To: {roadmap['target_role']}")
        print(f"  Path: {' -> '.join(roadmap['path'])}")
        print(f"  New skills needed: {roadmap['total_new_skills'][:5]}")

    # Demo 5: Role stats
    print("\n--- Demo 5: Role Stats ---")
    stats = kb.get_role_stats("AI Engineer")
    print(f"  Role: {stats['role']}")
    print(f"  Total jobs: {stats['total_jobs']}")
    if stats['top_skills']:
        print(f"  Top 5 skills:")
        for s in stats['top_skills'][:5]:
            print(f"    - {s['skill']}: {s['frequency_pct']:.1f}% ({s['count']} lần)")

    print("\n" + "=" * 70)
    print("DEMO HOÀN TẤT")
    print("=" * 70)