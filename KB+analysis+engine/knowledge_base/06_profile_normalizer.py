"""
Module 06: Profile Normalizer
Chuẩn hóa dữ liệu resume và job thành các profile có cấu trúc cho Knowledge Base.

Đầu vào: outputs/data_with_skills.parquet
Đầu ra:
  - outputs/resume_profiles.parquet
  - outputs/job_profiles.parquet
"""

import os
import re
from collections import Counter

import pandas as pd

# Import đường dẫn từ config
from config import RESUME_PROFILES_PATH, JOB_PROFILES_PATH, DATA_WITH_SKILLS_PATH


# =============================================================================
# Bản đồ ánh xạ thủ công các biến thể chức danh -> tên chuẩn
# Bao gồm ~50 biến thể phổ biến trong dữ liệu việc làm IT
# =============================================================================
MANUAL_ROLE_MAP = {
    # Frontend
    "frontend developer": "Frontend Developer",
    "front-end developer": "Frontend Developer",
    "frontend engineer": "Frontend Developer",
    "front-end engineer": "Frontend Developer",
    "web developer": "Frontend Developer",
    "ui developer": "Frontend Developer",
    "react developer": "Frontend Developer",
    "angular developer": "Frontend Developer",
    "vue developer": "Frontend Developer",
    "javascript developer": "Frontend Developer",
    "typescript developer": "Frontend Developer",

    # Backend
    "backend developer": "Backend Developer",
    "back-end developer": "Backend Developer",
    "backend engineer": "Backend Developer",
    "back-end engineer": "Backend Developer",
    "server developer": "Backend Developer",
    "api developer": "Backend Developer",
    "java developer": "Backend Developer",
    "python developer": "Backend Developer",
    "golang developer": "Backend Developer",
    "go developer": "Backend Developer",
    "node.js developer": "Backend Developer",
    "nodejs developer": "Backend Developer",
    ".net developer": "Backend Developer",
    "dotnet developer": "Backend Developer",
    "php developer": "Backend Developer",
    "c# developer": "Backend Developer",
    "c++ developer": "Backend Developer",

    # Fullstack
    "fullstack developer": "Fullstack Developer",
    "full-stack developer": "Fullstack Developer",
    "full stack developer": "Fullstack Developer",
    "fullstack engineer": "Fullstack Developer",
    "full-stack engineer": "Fullstack Developer",

    # AI / ML
    "ai engineer": "AI Engineer",
    "ml engineer": "ML Engineer",
    "machine learning engineer": "ML Engineer",
    "deep learning engineer": "ML Engineer",
    "ai researcher": "AI Engineer",
    "nlp engineer": "AI Engineer",
    "computer vision engineer": "AI Engineer",
    "llm engineer": "AI Engineer",

    # Data
    "data scientist": "Data Scientist",
    "data analyst": "Data Analyst",
    "data engineer": "Data Engineer",
    "big data engineer": "Data Engineer",
    "analytics engineer": "Data Analyst",
    "bi analyst": "Data Analyst",
    "business intelligence analyst": "Data Analyst",

    # DevOps / Cloud / SRE
    "devops engineer": "DevOps Engineer",
    "devops": "DevOps Engineer",
    "sre": "Site Reliability Engineer",
    "site reliability engineer": "Site Reliability Engineer",
    "cloud engineer": "Cloud Engineer",
    "infrastructure engineer": "Cloud Engineer",
    "platform engineer": "Platform Engineer",

    # QA / Test
    "qa engineer": "QA Engineer",
    "test engineer": "QA Engineer",
    "software tester": "QA Engineer",
    "automation tester": "QA Engineer",
    "qc engineer": "QA Engineer",

    # Mobile
    "mobile developer": "Mobile Developer",
    "ios developer": "Mobile Developer",
    "android developer": "Mobile Developer",
    "flutter developer": "Mobile Developer",
    "react native developer": "Mobile Developer",

    # Security
    "security engineer": "Security Engineer",
    "cybersecurity engineer": "Security Engineer",
    "penetration tester": "Security Engineer",

    # Product / Project
    "product manager": "Product Manager",
    "project manager": "Project Manager",
    "scrum master": "Scrum Master",
    "business analyst": "Business Analyst",
    "ba": "Business Analyst",

    # Design
    "ux designer": "UX Designer",
    "ui designer": "UX Designer",
    "ux/ui designer": "UX Designer",
    "product designer": "UX Designer",

    # General Software
    "software engineer": "Software Engineer",
    "software developer": "Software Engineer",
    "developer": "Software Engineer",
    "engineer": "Software Engineer",
    "programmer": "Software Engineer",
}

# Các tiền tố cấp bậc tiếng Anh cần loại bỏ khi chuẩn hóa chức danh
SENIORITY_PREFIXES_EN = [
    r"\bsenior\b",
    r"\bjunior\b",
    r"\bmid[- ]?level\b",
    r"\bmid\b",
    r"\blead\b",
    r"\bprincipal\b",
    r"\bintern\b",
    r"\bentry[- ]?level\b",
    r"\bstaff\b",
]

# Các tiền tố/hậu tố tiếng Việt cần loại bỏ
VIETNAMESE_TERMS = [
    r"kỹ\s*sư",
    r"chuyên\s*viên",
    r"nhân\s*viên",
    r"trưởng\s*nhóm",
    r"giám\s*đốc",
]


def normalize_role(title: str) -> str:
    """
    Chuẩn hóa tên chức danh công việc về dạng thống nhất.

    Quy trình:
    1. Chuyển về chữ thường, xóa khoảng trắng thừa
    2. Tra cứu trong MANUAL_ROLE_MAP
    3. Nếu không tìm thấy, xóa tiền tố cấp bậc (EN/VN) rồi tra lại
    4. Fallback: trả về chuỗi đã làm sạch ở dạng Title Case

    Args:
        title: Chức danh gốc từ dữ liệu

    Returns:
        Tên chức danh đã chuẩn hóa
    """
    if not isinstance(title, str) or not title.strip():
        return "Unknown"

    # Bước 1: Chuyển về chữ thường và xóa khoảng trắng thừa
    cleaned = title.lower().strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Bước 2: Tra cứu trực tiếp trong bản đồ ánh xạ
    if cleaned in MANUAL_ROLE_MAP:
        return MANUAL_ROLE_MAP[cleaned]

    # Bước 3: Xóa các tiền tố cấp bậc tiếng Anh
    stripped = cleaned
    for pattern in SENIORITY_PREFIXES_EN:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)

    # Xóa các thuật ngữ tiếng Việt
    for pattern in VIETNAMESE_TERMS:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)

    # Xóa khoảng trắng thừa sau khi xóa tiền tố/hậu tố
    stripped = re.sub(r"\s+", " ", stripped).strip()
    # Xóa dấu gạch ngang hoặc dấu phẩy ở đầu/cuối
    stripped = stripped.strip("-, ")

    # Bước 4: Tra cứu lại sau khi đã xóa tiền tố
    if stripped in MANUAL_ROLE_MAP:
        return MANUAL_ROLE_MAP[stripped]

    # Bước 5: Fallback - trả về dạng Title Case của chuỗi đã làm sạch
    if stripped:
        return stripped.title()

    return cleaned.title()


def extract_candidate_id(record_id: str) -> int:
    """
    Trích xuất phần số từ record_id của resume.
    Ví dụ: "RESUME_0001" -> 1, "KAGGLE_RESUME_0042" -> 42

    Args:
        record_id: Mã định danh bản ghi resume

    Returns:
        Số nguyên đại diện cho candidate_id
    """
    if not isinstance(record_id, str):
        return 0
    # Tìm tất cả các nhóm chữ số, lấy nhóm cuối cùng
    numbers = re.findall(r"\d+", record_id)
    if numbers:
        return int(numbers[-1])
    return 0


def build_resume_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Xây dựng bảng resume profiles từ dữ liệu đã gán skills.

    Chỉ xử lý các bản ghi có record_type == "resume".

    Args:
        df: DataFrame đầu vào với đầy đủ cột

    Returns:
        DataFrame chứa resume profiles theo schema yêu cầu
    """
    # Lọc chỉ lấy bản ghi resume
    resumes = df[df["record_type"] == "resume"].copy()

    if resumes.empty:
        print("⚠️ Không tìm thấy bản ghi resume nào trong dữ liệu.")
        return pd.DataFrame(columns=[
            "candidate_id", "source", "category", "skills",
            "skill_count", "description_preview"
        ])

    # Xây dựng các cột theo schema
    profiles = pd.DataFrame()
    profiles["candidate_id"] = resumes["record_id"].apply(extract_candidate_id)
    profiles["source"] = resumes["source"]
    profiles["category"] = resumes["category"]
    # PyArrow may deserialize list columns as numpy ndarray
    def _to_list(x):
        if isinstance(x, (list, tuple)) or (
            hasattr(x, '__iter__') and hasattr(x, '__len__')
            and not isinstance(x, (str, bytes, dict))
        ):
            return list(x)
        return []

    profiles["skills"] = resumes["skills_extracted"].apply(_to_list)
    profiles["skill_count"] = profiles["skills"].apply(len)
    profiles["description_preview"] = resumes["description"].apply(
        lambda x: str(x)[:500] if isinstance(x, str) else ""
    )

    return profiles


def build_job_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    Xây dựng bảng job profiles từ dữ liệu đã gán skills.

    Chỉ xử lý các bản ghi có record_type == "job".
    Trích xuất thông tin company, location, salary, seniority từ cột metadata.

    Args:
        df: DataFrame đầu vào với đầy đủ cột

    Returns:
        DataFrame chứa job profiles theo schema yêu cầu
    """
    # Lọc chỉ lấy bản ghi job
    jobs = df[df["record_type"] == "job"].copy()

    if jobs.empty:
        print("⚠️ Không tìm thấy bản ghi job nào trong dữ liệu.")
        return pd.DataFrame(columns=[
            "job_id", "source", "role", "title_original", "company",
            "location", "salary_vnd", "seniority", "skills",
            "skill_count", "category"
        ])

    # Hàm trích xuất an toàn từ metadata dict
    def safe_meta_get(metadata, key, default=None):
        """Lấy giá trị từ metadata dict một cách an toàn."""
        if isinstance(metadata, dict):
            return metadata.get(key, default)
        return default

    # Xây dựng các cột theo schema
    profiles = pd.DataFrame()
    profiles["job_id"] = jobs["record_id"]
    profiles["source"] = jobs["source"]
    profiles["role"] = jobs["title"].apply(normalize_role)
    profiles["title_original"] = jobs["title"]
    profiles["company"] = jobs["metadata"].apply(lambda m: safe_meta_get(m, "company"))
    profiles["location"] = jobs["metadata"].apply(lambda m: safe_meta_get(m, "location"))
    profiles["salary_vnd"] = jobs["metadata"].apply(lambda m: safe_meta_get(m, "salary_vnd"))
    profiles["seniority"] = jobs["metadata"].apply(lambda m: safe_meta_get(m, "seniority"))
    # PyArrow may deserialize list columns as numpy ndarray
    def _to_list(x):
        if isinstance(x, (list, tuple)) or (
            hasattr(x, '__iter__') and hasattr(x, '__len__')
            and not isinstance(x, (str, bytes, dict))
        ):
            return list(x)
        return []

    profiles["skills"] = jobs["skills_extracted"].apply(_to_list)
    profiles["skill_count"] = profiles["skills"].apply(len)
    profiles["category"] = jobs["category"]

    return profiles


def print_statistics(resume_profiles: pd.DataFrame, job_profiles: pd.DataFrame) -> None:
    """
    In thống kê tóm tắt cho cả hai bảng profiles.

    Bao gồm: số dòng, trung bình skills, top 10 skills phổ biến,
    phân bố category (resume), top 10 roles (job).
    """
    print("\n" + "=" * 70)
    print("THỐNG KÊ RESUME PROFILES")
    print("=" * 70)

    if not resume_profiles.empty:
        print(f"  Số lượng hồ sơ: {len(resume_profiles)}")
        avg_skills = resume_profiles["skill_count"].mean()
        print(f"  Trung bình skills/hồ sơ: {avg_skills:.2f}")

        # Top 10 skills phổ biến nhất
        all_resume_skills = []
        for skills_list in resume_profiles["skills"]:
            # PyArrow may deserialize list columns as numpy ndarray
            if isinstance(skills_list, (list, tuple)) or (
                hasattr(skills_list, '__iter__') and hasattr(skills_list, '__len__')
                and not isinstance(skills_list, (str, bytes, dict))
            ):
                all_resume_skills.extend(skills_list)
        skill_counter = Counter(all_resume_skills)
        print("\n  Top 10 skills phổ biến (Resume):")
        for skill, count in skill_counter.most_common(10):
            print(f"    - {skill}: {count}")

        # Phân bố category
        print("\n  Phân bố Category:")
        cat_dist = resume_profiles["category"].value_counts()
        for cat, cnt in cat_dist.items():
            pct = cnt / len(resume_profiles) * 100
            print(f"    - {cat}: {cnt} ({pct:.1f}%)")
    else:
        print("  Không có dữ liệu resume.")

    print("\n" + "=" * 70)
    print("THỐNG KÊ JOB PROFILES")
    print("=" * 70)

    if not job_profiles.empty:
        print(f"  Số lượng tin tuyển dụng: {len(job_profiles)}")
        avg_skills = job_profiles["skill_count"].mean()
        print(f"  Trung bình skills/tin: {avg_skills:.2f}")

        # Top 10 skills phổ biến nhất
        all_job_skills = []
        for skills_list in job_profiles["skills"]:
            # PyArrow may deserialize list columns as numpy ndarray
            if isinstance(skills_list, (list, tuple)) or (
                hasattr(skills_list, '__iter__') and hasattr(skills_list, '__len__')
                and not isinstance(skills_list, (str, bytes, dict))
            ):
                all_job_skills.extend(skills_list)
        skill_counter = Counter(all_job_skills)
        print("\n  Top 10 skills phổ biến (Job):")
        for skill, count in skill_counter.most_common(10):
            print(f"    - {skill}: {count}")

        # Top 10 roles theo số lượng
        print("\n  Top 10 Roles (sau chuẩn hóa):")
        role_counts = job_profiles["role"].value_counts().head(10)
        for role, cnt in role_counts.items():
            pct = cnt / len(job_profiles) * 100
            print(f"    - {role}: {cnt} ({pct:.1f}%)")
    else:
        print("  Không có dữ liệu job.")

    print("=" * 70)


def main():
    """
    Hàm chính: đọc dữ liệu, xây dựng profiles, lưu parquet và in thống kê.
    """
    try:
        # Đọc dữ liệu đầu vào
        print(f"📂 Đang đọc dữ liệu từ: {DATA_WITH_SKILLS_PATH}")
        if not os.path.exists(DATA_WITH_SKILLS_PATH):
            raise FileNotFoundError(
                f"Không tìm thấy file đầu vào: {DATA_WITH_SKILLS_PATH}\n"
                "Hãy chạy module 05 trước để tạo data_with_skills.parquet"
            )

        df = pd.read_parquet(DATA_WITH_SKILLS_PATH)
        print(f"   Đã đọc {len(df)} bản ghi, columns: {list(df.columns)}")

        # Kiểm tra các cột bắt buộc
        required_cols = ["record_id", "source", "record_type", "title",
                         "description", "skills_extracted", "category"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            raise ValueError(f"Thiếu các cột bắt buộc trong dữ liệu đầu vào: {missing}")

        # Tạo thư mục output nếu chưa tồn tại
        for path in [RESUME_PROFILES_PATH, JOB_PROFILES_PATH]:
            out_dir = os.path.dirname(path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
                print(f"   Đã tạo thư mục: {out_dir}")

        # Xây dựng Resume Profiles
        print("\n🔧 Đang xây dựng Resume Profiles...")
        resume_profiles = build_resume_profiles(df)
        resume_profiles.to_parquet(RESUME_PROFILES_PATH, index=False)
        print(f"   ✅ Đã lưu {len(resume_profiles)} resume profiles -> {RESUME_PROFILES_PATH}")

        # Xây dựng Job Profiles
        print("\n🔧 Đang xây dựng Job Profiles...")
        job_profiles = build_job_profiles(df)
        job_profiles.to_parquet(JOB_PROFILES_PATH, index=False)
        print(f"   ✅ Đã lưu {len(job_profiles)} job profiles -> {JOB_PROFILES_PATH}")

        # In thống kê
        print_statistics(resume_profiles, job_profiles)

        print("\n✅ Hoàn thành chuẩn hóa profiles!")

    except FileNotFoundError as e:
        print(f"❌ Lỗi file: {e}")
    except ValueError as e:
        print(f"❌ Lỗi dữ liệu: {e}")
    except Exception as e:
        print(f"❌ Lỗi không xác định: {type(e).__name__}: {e}")
        raise


if __name__ == "__main__":
    main()
