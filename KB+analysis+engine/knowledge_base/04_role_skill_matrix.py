"""
04 - Role-Skill Matrix Builder
================================
Xây dựng ma trận Role-Skill từ dữ liệu job đã extract skills.

Quy trình:
1. Chuẩn hóa job title (loại bỏ seniority, tiếng Việt, map variant)
2. Đếm tần suất skill theo từng role
3. Lọc nhiễu (skill xuất hiện < 5% trong role bị loại)
4. Xuất CSV với các cột: role, skill, frequency_pct, count, total_jobs_in_role
"""

import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

# ============================================================
# Import cấu hình từ config
# ============================================================
sys.path.insert(0, str(Path(__file__).parent))
from config import ROLE_SKILL_MATRIX_PATH, DATA_WITH_SKILLS_PATH

# ============================================================
# MANUAL ROLE MAP - Ánh xạ thủ công các variant phổ biến
# ============================================================
# Key phải lowercase; value là tên canonical hiển thị
MANUAL_ROLE_MAP = {
    # Frontend
    "frontend developer": "Frontend Developer",
    "front-end developer": "Frontend Developer",
    "frontend engineer": "Frontend Developer",
    "front end developer": "Frontend Developer",
    "web developer": "Frontend Developer",
    "ui developer": "Frontend Developer",
    # Backend
    "backend developer": "Backend Developer",
    "back-end developer": "Backend Developer",
    "backend engineer": "Backend Developer",
    "back end developer": "Backend Developer",
    "server developer": "Backend Developer",
    "api developer": "Backend Developer",
    # Fullstack
    "fullstack developer": "Fullstack Developer",
    "full-stack developer": "Fullstack Developer",
    "full stack developer": "Fullstack Developer",
    "fullstack engineer": "Fullstack Developer",
    # AI / ML
    "ai engineer": "AI Engineer",
    "machine learning engineer": "ML Engineer",
    "ml engineer": "ML Engineer",
    "deep learning engineer": "ML Engineer",
    "data scientist": "Data Scientist",
    "nlp engineer": "NLP Engineer",
    "computer vision engineer": "Computer Vision Engineer",
    "cv engineer": "Computer Vision Engineer",
    # Data
    "data analyst": "Data Analyst",
    "business intelligence analyst": "Data Analyst",
    "bi analyst": "Data Analyst",
    "data engineer": "Data Engineer",
    "etl developer": "Data Engineer",
    "big data engineer": "Data Engineer",
    # DevOps / Cloud
    "devops engineer": "DevOps Engineer",
    "sre": "SRE",
    "site reliability engineer": "SRE",
    "cloud engineer": "Cloud Engineer",
    "infrastructure engineer": "Cloud Engineer",
    "platform engineer": "Platform Engineer",
    # QA
    "qa engineer": "QA Engineer",
    "test engineer": "QA Engineer",
    "automation tester": "QA Automation",
    "qa automation": "QA Automation",
    "manual tester": "QA Manual",
    "qa manual": "QA Manual",
    # Product / BA
    "product manager": "Product Manager",
    "pm": "Product Manager",
    "product owner": "Product Owner",
    "po": "Product Owner",
    "business analyst": "Business Analyst",
    "ba": "Business Analyst",
    "scrum master": "Scrum Master",
    # Design
    "ux designer": "UX/UI Designer",
    "ui designer": "UX/UI Designer",
    "ux/ui designer": "UX/UI Designer",
    "ui/ux designer": "UX/UI Designer",
    # Security
    "security engineer": "Security Engineer",
    "cyber security": "Security Engineer",
    "penetration tester": "Security Engineer",
    # Mobile
    "mobile developer": "Mobile Developer",
    "ios developer": "Mobile Developer",
    "android developer": "Mobile Developer",
    "flutter developer": "Mobile Developer",
    "react native developer": "Mobile Developer",
    # Enterprise
    "sap consultant": "SAP Consultant",
    "salesforce developer": "Salesforce Developer",
    "erp developer": "ERP Developer",
}

# ============================================================
# Các prefix/suffix cần loại bỏ khi chuẩn hóa role
# ============================================================
SENIORITY_PREFIXES_EN = [
    r"\bsenior\b", r"\bjunior\b", r"\bmid[- ]?level\b", r"\bmid\b",
    r"\blead\b", r"\bprincipal\b", r"\bentry[- ]?level\b", r"\bentry\b",
    r"\bintern\b", r"\bfresher\b", r"\bassociate\b", r"\bstaff\b",
    r"\bhead of\b", r"\bdirector\b", r"\bvp\b",
]

VIETNAMESE_PREFIXES_SUFFIXES = [
    r"\bkỹ sư\b", r"\bchuyên viên\b", r"\bnhân viên\b",
    r"\btrưởng nhóm\b", r"\bphó trưởng\b", r"\bgiám đốc\b",
    r"\bquản lý\b", r"\bthực tập\b", r"\bmới tốt nghiệp\b",
    r"\bcó kinh nghiệm\b", r"\blập trình viên\b",
]


def normalize_role(title: str) -> str:
    """
    Chuẩn hóa job title thành canonical role name.

    Bước xử lý:
    1. Lowercase và strip khoảng trắng thừa
    2. Kiểm tra MANUAL_ROLE_MAP trước (exact match sau khi clean)
    3. Loại bỏ seniority prefixes (EN + VN)
    4. Kiểm tra MANUAL_ROLE_MAP lần nữa (sau khi đã strip prefix)
    5. Nếu không match được, trả về title đã clean (title-case)
    """
    if not title or not isinstance(title, str):
        return "Unknown"

    # Bước 1: lowercase, strip, loại bỏ ký tự đặc biệt thừa
    cleaned = title.strip().lower()
    cleaned = re.sub(r"\s+", " ", cleaned)  # gộp nhiều space thành 1

    # Bước 2: kiểm tra exact match trong manual map
    if cleaned in MANUAL_ROLE_MAP:
        return MANUAL_ROLE_MAP[cleaned]

    # Bước 3: loại bỏ seniority prefixes (English)
    stripped = cleaned
    for pattern in SENIORITY_PREFIXES_EN:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)

    # Loại bỏ Vietnamese prefixes/suffixes
    for pattern in VIETNAMESE_PREFIXES_SUFFIXES:
        stripped = re.sub(pattern, "", stripped, flags=re.IGNORECASE)

    # Clean lại khoảng trắng sau khi strip
    stripped = re.sub(r"\s+", " ", stripped).strip()
    # Loại bỏ dấu gạch ngang/dấu phẩy ở đầu/cuối
    stripped = stripped.strip("-,/ ")

    # Bước 4: kiểm tra manual map lần nữa sau khi strip
    if stripped in MANUAL_ROLE_MAP:
        return MANUAL_ROLE_MAP[stripped]

    # Bước 5: fallback - trả về dạng title case của stripped
    if stripped:
        return stripped.title()

    return "Unknown"


def build_role_skill_matrix(df: pd.DataFrame, min_freq_pct: float = 5.0) -> pd.DataFrame:
    """
    Xây dựng ma trận Role-Skill từ DataFrame đã có cột skills_extracted.

    Args:
        df: DataFrame với cột record_type, title, skills_extracted
        min_freq_pct: Ngưỡng lọc nhiễu (%), chỉ giữ skill >= ngưỡng này

    Returns:
        DataFrame với columns: role, skill, frequency_pct, count, total_jobs_in_role
    """
    # Lọc chỉ lấy bản ghi job
    jobs_df = df[df["record_type"] == "job"].copy()
    print(f"[MATRIX] Số bản ghi job: {len(jobs_df)}")

    if len(jobs_df) == 0:
        print("[MATRIX] CẢNH BÁO: Không có bản ghi job nào!")
        return pd.DataFrame(columns=["role", "skill", "frequency_pct", "count", "total_jobs_in_role"])

    # Chuẩn hóa role cho tất cả job
    jobs_df["normalized_role"] = jobs_df["title"].apply(normalize_role)
    print(f"[MATRIX] Số role unique sau chuẩn hóa: {jobs_df['normalized_role'].nunique()}")

    # Explode skills: mỗi dòng trở thành (role, skill) pair
    # Lọc bỏ rows có skills_extracted rỗng hoặc None
    jobs_with_skills = jobs_df[jobs_df["skills_extracted"].notna()].copy()
    # PyArrow may deserialize list columns as numpy ndarray
    def _has_skills(x):
        if isinstance(x, (list, tuple)) or (
            hasattr(x, '__iter__') and hasattr(x, '__len__')
            and not isinstance(x, (str, bytes, dict))
        ):
            return len(x) > 0
        return False

    jobs_with_skills = jobs_with_skills[jobs_with_skills["skills_extracted"].apply(_has_skills)]

    exploded = jobs_with_skills.explode("skills_extracted")
    exploded = exploded.rename(columns={"skills_extracted": "skill"})
    exploded = exploded[exploded["skill"].notna()]
    exploded["skill"] = exploded["skill"].astype(str).str.strip()
    exploded = exploded[exploded["skill"] != ""]

    print(f"[MATRIX] Tổng số (role, skill) pairs trước aggregate: {len(exploded)}")

    # Đếm tổng số job theo mỗi role
    role_totals = jobs_df.groupby("normalized_role").size().reset_index(name="total_jobs_in_role")

    # Đếm số lần mỗi skill xuất hiện trong mỗi role
    role_skill_counts = (
        exploded.groupby(["normalized_role", "skill"])
        .size()
        .reset_index(name="count")
    )

    # Merge để có total_jobs_in_role
    matrix = role_skill_counts.merge(role_totals, on="normalized_role", how="left")

    # Tính phần trăm tần suất
    matrix["frequency_pct"] = (matrix["count"] / matrix["total_jobs_in_role"] * 100).round(2)

    # Lọc nhiễu: chỉ giữ skill xuất hiện >= min_freq_pct% trong role
    matrix_filtered = matrix[matrix["frequency_pct"] >= min_freq_pct].copy()

    # Đổi tên cột và sắp xếp
    matrix_filtered = matrix_filtered.rename(columns={"normalized_role": "role"})
    matrix_filtered = matrix_filtered.sort_values(
        ["role", "frequency_pct"], ascending=[True, False]
    ).reset_index(drop=True)

    # Chỉ giữ các cột cần thiết
    result = matrix_filtered[["role", "skill", "frequency_pct", "count", "total_jobs_in_role"]]

    return result


def print_statistics(matrix: pd.DataFrame, df: pd.DataFrame) -> None:
    """In thống kê tổng quan về ma trận Role-Skill."""
    print("\n" + "=" * 70)
    print("THỐNG KÊ ROLE-SKILL MATRIX")
    print("=" * 70)

    if matrix.empty:
        print("[STATS] Ma trận rỗng, không có thống kê.")
        return

    # Số role unique
    unique_roles = matrix["role"].nunique()
    print(f"\nSố role unique: {unique_roles}")

    # Tổng số cặp role-skill
    total_pairs = len(matrix)
    print(f"Tổng số cặp (role, skill): {total_pairs}")

    # Top 20 roles theo số lượng job
    role_job_counts = (
        matrix.groupby("role")["total_jobs_in_role"]
        .first()
        .sort_values(ascending=False)
    )
    print(f"\n--- Top 20 Roles theo số lượng Job ---")
    for i, (role, count) in enumerate(role_job_counts.head(20).items(), 1):
        print(f"  {i:2d}. {role:<35s} | {count:>5d} jobs")

    # Top 10 roles: in top 5 skills mỗi role
    top_10_roles = role_job_counts.head(10).index.tolist()
    print(f"\n--- Top 5 Skills cho mỗi Role (trong Top 10 Roles) ---")
    for role in top_10_roles:
        role_data = matrix[matrix["role"] == role].sort_values(
            "frequency_pct", ascending=False
        ).head(5)
        print(f"\n  [{role}] ({role_data['total_jobs_in_role'].iloc[0]} jobs)")
        for _, row in role_data.iterrows():
            print(f"    - {row['skill']:<30s} | {row['frequency_pct']:5.1f}% ({row['count']} lần)")

    print("\n" + "=" * 70)


def main():
    """Hàm chính: load data → xây matrix → lưu kết quả."""
    print("=" * 70)
    print("04 - XÂY DỰNG ROLE-SKILL MATRIX")
    print("=" * 70)

    try:
        # ----------------------------------------------------------
        # 1. Load dữ liệu đã extract skills
        # ----------------------------------------------------------
        print(f"\n[LOAD] Đọc dữ liệu từ: {DATA_WITH_SKILLS_PATH}")
        if not DATA_WITH_SKILLS_PATH.exists():
            raise FileNotFoundError(
                f"Không tìm thấy file: {DATA_WITH_SKILLS_PATH}\n"
                "Hãy chạy 02_skill_extractor.py trước."
            )

        df = pd.read_parquet(DATA_WITH_SKILLS_PATH)
        print(f"[LOAD] Đã đọc {len(df)} bản ghi, columns: {list(df.columns)}")

        # Kiểm tra cột bắt buộc
        required_cols = {"record_type", "title", "skills_extracted"}
        missing = required_cols - set(df.columns)
        if missing:
            raise ValueError(f"Thiếu cột bắt buộc: {missing}")

        # ----------------------------------------------------------
        # 2. Xây dựng ma trận Role-Skill
        # ----------------------------------------------------------
        print("\n[BUILD] Đang xây dựng ma trận Role-Skill...")
        matrix = build_role_skill_matrix(df, min_freq_pct=5.0)

        # ----------------------------------------------------------
        # 3. In thống kê
        # ----------------------------------------------------------
        print_statistics(matrix, df)

        # ----------------------------------------------------------
        # 4. Lưu kết quả
        # ----------------------------------------------------------
        if not matrix.empty:
            matrix.to_csv(ROLE_SKILL_MATRIX_PATH, index=False, encoding="utf-8-sig")
            print(f"\n[SAVE] Đã lưu ma trận vào: {ROLE_SKILL_MATRIX_PATH}")
            print(f"[SAVE] Kích thước: {matrix.shape[0]} dòng x {matrix.shape[1]} cột")
        else:
            print("\n[SAVE] Ma trận rỗng, không lưu file.")

        print("\n[DONE] Hoàn thành xây dựng Role-Skill Matrix!")

    except FileNotFoundError as e:
        print(f"\n[LỖI FILE] {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\n[LỖI DỮ LIỆU] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[LỖI KHÔNG XÁC ĐỊNH] {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
