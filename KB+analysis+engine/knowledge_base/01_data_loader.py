"""
01_data_loader.py - Module tải và hợp nhất 4 nguồn dữ liệu thành schema thống nhất
cho pipeline Career Knowledge Base.

Các nguồn dữ liệu:
1. LinkedIn Clean (xlsx) - 1391 dòng
2. TopCV Clean (xlsx) - 1407 dòng
3. Kaggle Job Descriptions (csv) - 521 dòng
4. Kaggle Resumes (csv) - 2484 dòng

Output: Unified DataFrame lưu dưới dạng Parquet.
"""

import sys
from pathlib import Path

import pandas as pd

# Thêm thư mục knowledge_base vào path để import config
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    LINKEDIN_PATH,
    TOPCV_PATH,
    JD_CSV_PATH,
    RESUME_CSV_PATH,
    UNIFIED_DATA_PATH,
)


def _read_csv_safe(filepath: Path) -> pd.DataFrame:
    """
    Đọc file CSV với xử lý encoding linh hoạt.
    Thử lần lượt utf-8, latin-1, cp1252 cho đến khi đọc thành công.
    """
    encodings = ["utf-8", "latin-1", "cp1252"]
    for enc in encodings:
        try:
            df = pd.read_csv(filepath, encoding=enc)
            print(f"  [OK] Đọc '{filepath.name}' thành công với encoding='{enc}'")
            return df
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            print(f"  [LỖI] Không thể đọc '{filepath.name}': {e}")
            raise
    raise ValueError(f"Không thể đọc file '{filepath}' với bất kỳ encoding nào: {encodings}")


def _generate_record_ids(source_prefix: str, count: int) -> list[str]:
    """Tạo danh sách record_id duy nhất theo định dạng PREFIX_0001, PREFIX_0002, ..."""
    width = max(4, len(str(count)))
    return [f"{source_prefix}_{str(i + 1).zfill(width)}" for i in range(count)]


def load_linkedin() -> pd.DataFrame:
    """
    Tải dữ liệu LinkedIn đã làm sạch.
    skills_required hoàn toàn NULL nên gán skills_raw = None.
    """
    print("\n[1/4] Đang tải dữ liệu LinkedIn...")
    try:
        df = pd.read_excel(LINKEDIN_PATH, engine="openpyxl")
        print(f"  Số dòng gốc: {len(df)}")

        # Ánh xạ sang unified schema
        unified = pd.DataFrame({
            "record_id": _generate_record_ids("LINKEDIN", len(df)),
            "source": "LINKEDIN",
            "record_type": "job",
            "title": df["job_title"],
            "description": df["job_description"],
            # skills_required ALL NULL → gán None
            "skills_raw": None,
            "category": df.get("category"),
            "metadata": [
                {
                    "company": row.get("company"),
                    "location": row.get("location_normalized"),
                    "seniority": row.get("seniority"),
                }
                for _, row in df.iterrows()
            ],
        })
        print(f"  Số dòng sau ánh xạ: {len(unified)}")
        return unified

    except Exception as e:
        print(f"  [LỖI] Tải LinkedIn thất bại: {e}")
        raise


def load_topcv() -> pd.DataFrame:
    """
    Tải dữ liệu TopCV đã làm sạch.
    Phân tích cột skills_required (comma-separated) thành list.
    company hoàn toàn NULL nên không đưa vào metadata.
    """
    print("\n[2/4] Đang tải dữ liệu TopCV...")
    try:
        df = pd.read_excel(TOPCV_PATH, engine="openpyxl")
        print(f"  Số dòng gốc: {len(df)}")

        # Phân tích skills_required từ chuỗi comma-separated thành list
        def parse_skills(val):
            """Chuyển đổi chuỗi kỹ năng phân tách bởi dấu phẩy thành list, hoặc None nếu rỗng."""
            if pd.isna(val) or str(val).strip() == "":
                return None
            # Tách theo dấu phẩy, loại bỏ khoảng trắng thừa và phần tử rỗng
            skills = [s.strip() for s in str(val).split(",") if s.strip()]
            return skills if skills else None

        skills_parsed = df["skills_required"].apply(parse_skills)

        # Ánh xạ sang unified schema
        unified = pd.DataFrame({
            "record_id": _generate_record_ids("TOPCV", len(df)),
            "source": "TOPCV",
            "record_type": "job",
            "title": df["job_title"],
            "description": df["job_description"],
            "skills_raw": skills_parsed,
            "category": df.get("category"),
            "metadata": [
                {
                    "salary_vnd": row.get("salary_vnd"),
                    "location": row.get("location_normalized"),
                    "seniority": row.get("seniority"),
                }
                for _, row in df.iterrows()
            ],
        })
        print(f"  Số dòng sau ánh xạ: {len(unified)}")
        print(f"  Số dòng có skills_raw: {skills_parsed.notna().sum()}/{len(df)}")
        return unified

    except Exception as e:
        print(f"  [LỖI] Tải TopCV thất bại: {e}")
        raise


def load_kaggle_jd() -> pd.DataFrame:
    """
    Tải dữ liệu Kaggle Job Descriptions (tiếng Anh).
    Chỉ có 2 cột: Job Title, Description.
    """
    print("\n[3/4] Đang tải dữ liệu Kaggle Job Descriptions...")
    try:
        df = _read_csv_safe(JD_CSV_PATH)
        print(f"  Số dòng gốc: {len(df)}")

        # Ánh xạ sang unified schema
        unified = pd.DataFrame({
            "record_id": _generate_record_ids("JD", len(df)),
            "source": "KAGGLE_JD",
            "record_type": "job",
            "title": df["Job Title"],
            "description": df["Description"],
            "skills_raw": None,
            "category": None,
            "metadata": [{} for _ in range(len(df))],
        })
        print(f"  Số dòng sau ánh xạ: {len(unified)}")
        return unified

    except Exception as e:
        print(f"  [LỖI] Tải Kaggle JD thất bại: {e}")
        raise


def load_kaggle_resume() -> pd.DataFrame:
    """
    Tải dữ liệu Kaggle Resumes.
    Sử dụng Resume_str cho text processing, Category làm title/category.
    """
    print("\n[4/4] Đang tải dữ liệu Kaggle Resumes...")
    try:
        df = _read_csv_safe(RESUME_CSV_PATH)
        print(f"  Số dòng gốc: {len(df)}")

        # Ánh xạ sang unified schema
        unified = pd.DataFrame({
            "record_id": _generate_record_ids("RESUME", len(df)),
            "source": "KAGGLE_RESUME",
            "record_type": "resume",
            "title": df["Category"],
            "description": df["Resume_str"],
            "skills_raw": None,
            "category": df["Category"],
            "metadata": [
                {"original_id": row.get("ID")}
                for _, row in df.iterrows()
            ],
        })
        print(f"  Số dòng sau ánh xạ: {len(unified)}")
        return unified

    except Exception as e:
        print(f"  [LỖI] Tải Kaggle Resume thất bại: {e}")
        raise


def print_statistics(df: pd.DataFrame) -> None:
    """In thống kê tổng quan về DataFrame đã hợp nhất."""
    print("\n" + "=" * 60)
    print("THỐNG KÊ DỮ LIỆU HỢP NHẤT")
    print("=" * 60)

    # Số lượng bản ghi theo nguồn
    print("\n--- Số lượng bản ghi theo nguồn ---")
    source_counts = df["source"].value_counts().sort_index()
    for src, cnt in source_counts.items():
        print(f"  {src}: {cnt:,} dòng")
    print(f"  TỔNG: {len(df):,} dòng")

    # Số lượng theo loại bản ghi
    print("\n--- Số lượng theo loại bản ghi ---")
    type_counts = df["record_type"].value_counts()
    for rt, cnt in type_counts.items():
        print(f"  {rt}: {cnt:,} dòng")

    # Tóm tắt giá trị thiếu
    print("\n--- Giá trị thiếu (missing values) ---")
    missing = df[["title", "description", "skills_raw", "category"]].isnull().sum()
    for col, miss_count in missing.items():
        pct = miss_count / len(df) * 100
        print(f"  {col}: {miss_count:,} ({pct:.1f}%)")

    # Thống kê skills_raw
    has_skills = df["skills_raw"].notna().sum()
    print(f"\n  Bản ghi có skills_raw: {has_skills:,} ({has_skills / len(df) * 100:.1f}%)")

    print("=" * 60)


def save_unified(df: pd.DataFrame, output_path: Path) -> None:
    """Lưu DataFrame hợp nhất ra file Parquet, tạo thư mục nếu chưa tồn tại."""
    try:
        # Tạo thư mục output nếu chưa tồn tại
        output_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"\nĐang lưu dữ liệu hợp nhất vào: {output_path}")
        df.to_parquet(output_path, index=False, engine="pyarrow")
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"  Lưu thành công! Kích thước file: {file_size_mb:.2f} MB")
    except Exception as e:
        print(f"  [LỖI] Lưu file thất bại: {e}")
        raise


def load_all() -> pd.DataFrame:
    """
    Hàm chính: tải và hợp nhất tất cả 4 nguồn dữ liệu.
    Trả về DataFrame thống nhất theo unified schema.
    """
    print("=" * 60)
    print("BẮT ĐẦU TẢI VÀ HỢP NHẤT DỮ LIỆU")
    print("=" * 60)

    # Tải từng nguồn dữ liệu
    linkedin_df = load_linkedin()
    topcv_df = load_topcv()
    jd_df = load_kaggle_jd()
    resume_df = load_kaggle_resume()

    # Hợp nhất tất cả vào một DataFrame duy nhất
    print("\nĐang hợp nhất 4 nguồn dữ liệu...")
    unified = pd.concat(
        [linkedin_df, topcv_df, jd_df, resume_df],
        ignore_index=True,
    )

    # Đảm bảo kiểu dữ liệu đúng
    unified["record_id"] = unified["record_id"].astype(str)
    unified["source"] = unified["source"].astype(str)
    unified["record_type"] = unified["record_type"].astype(str)

    print(f"Tổng số dòng sau hợp nhất: {len(unified):,}")

    return unified


def main():
    """Hàm chính để chạy toàn bộ pipeline tải và hợp nhất dữ liệu."""
    # Chạy pipeline tải và hợp nhất dữ liệu
    unified_df = load_all()

    # In thống kê chi tiết
    print_statistics(unified_df)

    # Lưu kết quả ra Parquet
    save_unified(unified_df, UNIFIED_DATA_PATH)

    print("\n[HOÀN THÀNH] Dữ liệu đã sẵn sàng cho bước tiếp theo.")


if __name__ == "__main__":
    main()
