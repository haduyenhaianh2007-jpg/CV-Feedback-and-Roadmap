"""
02_skill_extractor.py - Trích xuất kỹ năng từ văn bản sử dụng Dictionary + Regex + Fuzzy Matching

Module này xử lý việc trích xuất các kỹ năng (skills) từ mô tả công việc và CV,
sử dụng kết hợp ba phương pháp:
1. Dictionary matching: So khớp chính xác theo từ điển kỹ năng
2. Regex matching: Tìm kiếm theo mẫu regex với word boundary
3. Fuzzy matching: So khớp gần đúng cho các biến thể viết tắt/lỗi chính tả

Đầu vào: outputs/unified_data.parquet (từ 01_data_loader.py)
Đầu ra: outputs/data_with_skills.parquet với cột skills_extracted bổ sung
"""

import re
import os
import sys
from collections import Counter
from typing import List, Dict, Optional, Set, Tuple

import pandas as pd

# Thêm thư mục cha vào path để import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEFAULT_SEED_SKILLS,
    MANUAL_ALIASES,
    FUZZY_MATCH_THRESHOLD,
    UNIFIED_DATA_PATH,
    DATA_WITH_SKILLS_PATH,
    SKILL_ONTOLOGY_PATH,
)


def load_ontology() -> Dict[str, str]:
    """
    Tải ontology kỹ năng từ file hoặc xây dựng từ cấu hình mặc định.

    Ontology là một dictionary ánh xạ từ alias (tên gọi khác) sang canonical name (tên chuẩn).
    Ví dụ: {"ml": "Machine Learning", "machine learning": "Machine Learning"}

    Ưu tiên tải từ SKILL_ONTOLOGY_PATH nếu tồn tại,
    ngược lại xây dựng từ DEFAULT_SEED_SKILLS và MANUAL_ALIASES.

    Returns:
        Dict[str, str]: Ontology {alias_lower: canonical_name}
    """
    ontology: Dict[str, str] = {}

    # Thử tải ontology từ file JSON/YAML nếu tồn tại
    if os.path.exists(SKILL_ONTOLOGY_PATH):
        try:
            import json
            with open(SKILL_ONTOLOGY_PATH, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # Chuẩn hóa tất cả key về lowercase
            for alias, canonical in loaded.items():
                ontology[alias.lower().strip()] = canonical.strip()
            print(f"[INFO] Đã tải ontology từ {SKILL_ONTOLOGY_PATH}: {len(ontology)} mappings")
        except Exception as e:
            print(f"[WARN] Không thể tải ontology từ {SKILL_ONTOLOGY_PATH}: {e}")
            print("[INFO] Sẽ xây dựng ontology từ cấu hình mặc định")
            ontology = {}

    # Nếu chưa có ontology hoặc cần merge thêm, xây dựng từ seed skills và manual aliases
    if not ontology:
        # Mỗi seed skill tự map đến chính nó như canonical name
        for skill in DEFAULT_SEED_SKILLS:
            canonical = skill.strip()
            ontology[canonical.lower()] = canonical

        print(f"[INFO] Đã xây dựng ontology từ {len(DEFAULT_SEED_SKILLS)} seed skills")

    # Merge manual aliases lên trên (ghi đè nếu trùng key)
    for alias, canonical in MANUAL_ALIASES.items():
        ontology[alias.lower().strip()] = canonical.strip()

    print(f"[INFO] Tổng số mappings trong ontology sau khi merge: {len(ontology)}")
    return ontology


def _escape_regex_pattern(skill: str) -> str:
    """
    Escape các ký tự đặc biệt trong tên kỹ năng để dùng trong regex.

    Các ký tự như ., +, -, (, ), [, ], {, }, *, ?, ^, $, |, \\
    cần được escape để tránh hiểu nhầm thành regex metacharacters.

    Đồng thời xử lý khoảng trắng và dấu gạch ngang trong tên kỹ năng đa từ:
    - Khoảng trắng có thể thay bằng dấu gạch ngang hoặc ngược lại
    - Ví dụ: "Machine Learning" cũng khớp với "machine-learning"

    Args:
        skill: Tên kỹ năng gốc

    Returns:
        str: Pattern regex đã được escape
    """
    # Escape các ký tự regex đặc biệt trước
    escaped = re.escape(skill)

    # Cho phép khoảng trắng hoặc dấu gạch ngang thay thế lẫn nhau
    # \  (escaped space) -> [\s\-]
    escaped = escaped.replace(r"\ ", r"[\s\-]")

    return escaped


def _build_regex_patterns(ontology: Dict[str, str]) -> List[Tuple[re.Pattern, str]]:
    """
    Xây dựng danh sách các compiled regex patterns từ ontology.

    Sắp xếp theo độ dài giảm dần để ưu tiên khớp các cụm từ dài hơn trước,
    tránh trường hợp "Deep Learning" bị khớp thành "Deep" riêng lẻ.

    Args:
        ontology: Dict {alias_lower: canonical_name}

    Returns:
        List[Tuple[compiled_pattern, canonical_name]]: Danh sách pattern kèm canonical name
    """
    patterns = []

    # Lấy tất cả unique aliases và canonical names để tạo pattern
    all_terms: Set[str] = set()
    term_to_canonical: Dict[str, str] = {}

    for alias, canonical in ontology.items():
        alias_clean = alias.strip().lower()
        canonical_clean = canonical.strip()
        all_terms.add(alias_clean)
        term_to_canonical[alias_clean] = canonical_clean
        # Cũng thêm canonical name để đảm bảo tìm thấy
        all_terms.add(canonical_clean.lower())
        term_to_canonical[canonical_clean.lower()] = canonical_clean

    # Sắp xếp theo độ dài giảm dần để ưu tiên match cụm dài hơn
    sorted_terms = sorted(all_terms, key=len, reverse=True)

    for term in sorted_terms:
        try:
            pattern_str = _escape_regex_pattern(term)
            # Sử dụng word boundary (\b) để tránh khớp một phần từ
            # Ví dụ: "Java" không khớp trong "JavaScript"
            full_pattern = rf"(?i)\b{pattern_str}\b"
            compiled = re.compile(full_pattern)
            canonical = term_to_canonical.get(term, term)
            patterns.append((compiled, canonical))
        except re.error as e:
            print(f"[WARN] Không thể compile regex cho '{term}': {e}")
            continue

    print(f"[INFO] Đã xây dựng {len(patterns)} regex patterns")
    return patterns


def extract_skills(text: Optional[str], ontology: Dict[str, str]) -> List[str]:
    """
    Trích xuất danh sách kỹ năng từ văn bản đầu vào.

    Sử dụng regex matching với word boundary để tìm các kỹ năng trong text,
    sau đó ánh xạ về tên chuẩn (canonical) thông qua ontology.

    Args:
        text: Văn bản cần trích xuất kỹ năng (mô tả công việc, CV, v.v.)
        ontology: Dict {alias_lower: canonical_name} để ánh xạ tên

    Returns:
        List[str]: Danh sách các kỹ năng canonical duy nhất, đã sắp xếp
    """
    # Kiểm tra đầu vào rỗng
    if not text or not isinstance(text, str) or len(text.strip()) == 0:
        return []

    # Xây dựng patterns (cache sẽ được xử lý ở mức pipeline)
    patterns = _build_regex_patterns(ontology)

    found_canonical: Set[str] = set()

    # Duyệt qua tất cả patterns và tìm match trong text
    for pattern, canonical in patterns:
        if pattern.search(text):
            found_canonical.add(canonical)

    # Trả về danh sách đã sắp xếp và deduplicated
    return sorted(found_canonical)


def _normalize_raw_skills(skills_raw: str, ontology: Dict[str, str]) -> List[str]:
    """
    Chuẩn hóa danh sách kỹ năng thô (từ TopCV skills_raw column) thông qua ontology.

    TopCV cung cấp sẵn danh sách kỹ năng nhưng có thể chứa alias hoặc biến thể.
    Hàm này ánh xạ chúng về canonical names.

    Args:
        skills_raw: Chuỗi kỹ năng thô, phân tách bởi dấu phẩy hoặc xuống dòng
        ontology: Dict {alias_lower: canonical_name}

    Returns:
        List[str]: Danh sách kỹ năng canonical đã chuẩn hóa
    """
    if not skills_raw or not isinstance(skills_raw, str):
        return []

    # Tách các kỹ năng theo dấu phẩy, dấu chấm phẩy, hoặc xuống dòng
    raw_list = re.split(r"[,;\n]+", skills_raw)

    canonical_set: Set[str] = set()

    for raw_skill in raw_list:
        skill_clean = raw_skill.strip().lower()
        if not skill_clean:
            continue

        # Tra cứu trực tiếp trong ontology
        if skill_clean in ontology:
            canonical_set.add(ontology[skill_clean])
        else:
            # Thử fuzzy matching nếu không tìm thấy exact match
            best_match = _fuzzy_match_skill(skill_clean, ontology)
            if best_match:
                canonical_set.add(best_match)
            else:
                # Giữ nguyên tên gốc nếu không tìm thấy match nào
                # Viết hoa chữ cái đầu cho đẹp
                canonical_set.add(raw_skill.strip())

    return sorted(canonical_set)


def _fuzzy_match_skill(
    skill: str, ontology: Dict[str, str], threshold: int = None
) -> Optional[str]:
    """
    Tìm kiếm gần đúng (fuzzy matching) một kỹ năng trong ontology.

    Sử dụng thuật toán so khớp chuỗi gần đúng để tìm alias tương tự nhất.
    Chỉ trả về kết quả nếu độ tương đồng vượt ngưỡng FUZZY_MATCH_THRESHOLD.

    Args:
        skill: Tên kỹ năng cần tìm (đã lowercase)
        ontology: Dict {alias_lower: canonical_name}
        threshold: Ngưỡng tương đồng tối thiểu (mặc định lấy từ config)

    Returns:
        Optional[str]: Canonical name nếu tìm thấy match đủ tốt, None nếu không
    """
    if threshold is None:
        threshold = FUZZY_MATCH_THRESHOLD

    # Sử dụng difflib cho fuzzy matching (không cần thư viện ngoài)
    from difflib import SequenceMatcher

    best_score = 0.0
    best_canonical: Optional[str] = None

    for alias, canonical in ontology.items():
        # Tính tỷ lệ tương đồng
        score = SequenceMatcher(None, skill, alias).ratio() * 100
        if score > best_score and score >= threshold:
            best_score = score
            best_canonical = canonical

    return best_canonical


def process_unified_data(ontology: Dict[str, str]) -> pd.DataFrame:
    """
    Xử lý toàn bộ unified_data.parquet và trích xuất kỹ năng cho mỗi record.

    Logic xử lý:
    - Records có skills_raw (TopCV): Chuẩn hóa qua ontology + extract thêm từ description
    - Records không có skills_raw: Extract hoàn toàn từ description text
    - Kết hợp cả hai nguồn và deduplicate

    Args:
        ontology: Dict {alias_lower: canonical_name}

    Returns:
        pd.DataFrame: DataFrame với cột skills_extracted bổ sung
    """
    # Tải dữ liệu unified
    if not os.path.exists(UNIFIED_DATA_PATH):
        raise FileNotFoundError(
            f"Không tìm thấy file {UNIFIED_DATA_PATH}. "
            "Hãy chạy 01_data_loader.py trước."
        )

    print(f"[INFO] Đang tải dữ liệu từ {UNIFIED_DATA_PATH}...")
    df = pd.read_parquet(UNIFIED_DATA_PATH)
    print(f"[INFO] Đã tải {len(df)} records")

    # Pre-build regex patterns một lần để tái sử dụng (tránh build lại cho mỗi record)
    print("[INFO] Đang xây dựng regex patterns...")
    patterns = _build_regex_patterns(ontology)

    def _extract_with_cached_patterns(text: Optional[str]) -> List[str]:
        """Trích xuất skills sử dụng patterns đã được cache."""
        if not text or not isinstance(text, str) or len(text.strip()) == 0:
            return []

        found_canonical: Set[str] = set()
        for pattern, canonical in patterns:
            if pattern.search(text):
                found_canonical.add(canonical)
        return sorted(found_canonical)

    # Xử lý từng record
    print("[INFO] Đang trích xuất kỹ năng...")
    skills_extracted_list: List[List[str]] = []

    for idx, row in df.iterrows():
        if idx % 500 == 0 and idx > 0:
            print(f"  ... đã xử lý {idx}/{len(df)} records")

        skills_from_raw: List[str] = []
        skills_from_text: List[str] = []

        # Nếu có skills_raw (thường từ TopCV), chuẩn hóa chúng
        skills_raw_val = row.get("skills_raw", None)
        if isinstance(skills_raw_val, str) and skills_raw_val.strip():
            skills_from_raw = _normalize_raw_skills(skills_raw_val, ontology)

        # Trích xuất thêm từ description text
        desc_val = row.get("description", None)
        if isinstance(desc_val, str) and desc_val.strip():
            skills_from_text = _extract_with_cached_patterns(desc_val)

        # Cũng kiểm tra title vì đôi khi kỹ năng xuất hiện ở tiêu đề
        title_val = row.get("title", None)
        if isinstance(title_val, str) and title_val.strip():
            skills_from_title = _extract_with_cached_patterns(title_val)
            skills_from_text = list(set(skills_from_text + skills_from_title))

        # Hợp nhất và deduplicate
        combined = sorted(set(skills_from_raw + skills_from_text))
        skills_extracted_list.append(combined)

    df["skills_extracted"] = skills_extracted_list
    print(f"[INFO] Hoàn thành trích xuất kỹ năng cho {len(df)} records")

    return df


def print_extraction_stats(df: pd.DataFrame) -> None:
    """
    In thống kê về kết quả trích xuất kỹ năng.

    Bao gồm:
    - Số kỹ năng trung bình mỗi record
    - Top 30 kỹ năng được trích xuất nhiều nhất
    - Tỷ lệ coverage (% records có ít nhất 1 kỹ năng)

    Args:
        df: DataFrame với cột skills_extracted
    """
    print("\n" + "=" * 70)
    print("THỐNG KÊ TRÍCH XUẤT KỸ NĂNG")
    print("=" * 70)

    # Tính số kỹ năng mỗi record
    skill_counts = df["skills_extracted"].apply(len)

    # Trung bình số kỹ năng
    avg_skills = skill_counts.mean()
    median_skills = skill_counts.median()
    max_skills = skill_counts.max()
    min_skills = skill_counts.min()

    print(f"\n📊 Số kỹ năng mỗi record:")
    print(f"   Trung bình: {avg_skills:.2f}")
    print(f"   Trung vị:   {median_skills:.1f}")
    print(f"   Tối đa:     {max_skills}")
    print(f"   Tối thiểu:  {min_skills}")

    # Coverage: % records có ít nhất 1 kỹ năng
    records_with_skills = (skill_counts > 0).sum()
    total_records = len(df)
    coverage_pct = (records_with_skills / total_records) * 100 if total_records > 0 else 0

    print(f"\n📈 Coverage:")
    print(f"   Records có kỹ năng: {records_with_skills}/{total_records} ({coverage_pct:.1f}%)")
    print(f"   Records không có kỹ năng: {total_records - records_with_skills} ({100 - coverage_pct:.1f}%)")

    # Coverage theo source
    if "source" in df.columns:
        print(f"\n📋 Coverage theo nguồn dữ liệu:")
        for source in df["source"].unique():
            source_df = df[df["source"] == source]
            source_with_skills = (source_df["skills_extracted"].apply(len) > 0).sum()
            source_total = len(source_df)
            source_pct = (source_with_skills / source_total) * 100 if source_total > 0 else 0
            avg_source = source_df["skills_extracted"].apply(len).mean()
            print(f"   {source}: {source_with_skills}/{source_total} ({source_pct:.1f}%), TB: {avg_source:.1f} skills")

    # Top 30 kỹ năng phổ biến nhất
    all_skills: List[str] = []
    for skills_list in df["skills_extracted"]:
        # PyArrow may deserialize list columns as numpy ndarray
        if isinstance(skills_list, (list, tuple)) or (
            hasattr(skills_list, '__iter__') and hasattr(skills_list, '__len__')
            and not isinstance(skills_list, (str, bytes, dict))
        ):
            all_skills.extend(skills_list)

    skill_counter = Counter(all_skills)
    top_30 = skill_counter.most_common(30)

    print(f"\n🏆 Top 30 kỹ năng được trích xuất nhiều nhất:")
    print(f"   {'Hạng':<6} {'Kỹ năng':<35} {'Số lần':<10} {'% records':<10}")
    print(f"   {'-'*6} {'-'*35} {'-'*10} {'-'*10}")
    for rank, (skill, count) in enumerate(top_30, 1):
        pct = (count / total_records) * 100 if total_records > 0 else 0
        print(f"   {rank:<6} {skill:<35} {count:<10} {pct:.1f}%")

    # Tổng số unique skills
    unique_skills = len(skill_counter)
    print(f"\n📚 Tổng số kỹ năng unique: {unique_skills}")

    print("=" * 70)


def save_results(df: pd.DataFrame) -> None:
    """
    Lưu kết quả trích xuất ra file parquet.

    Tạo thư mục output nếu chưa tồn tại.

    Args:
        df: DataFrame với cột skills_extracted
    """
    # Đảm bảo thư mục output tồn tại
    output_dir = os.path.dirname(DATA_WITH_SKILLS_PATH)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"[INFO] Đã tạo thư mục {output_dir}")

    # Convert cột skills_extracted thành pure Python list để tránh
    # PyArrow deserializing thành numpy ndarray khi đọc lại (gây lỗi
    # isinstance(x, list) ở các module downstream).
    df["skills_extracted"] = df["skills_extracted"].apply(
        lambda x: list(x) if not isinstance(x, list) else x
    )

    # Lưu ra parquet
    df.to_parquet(DATA_WITH_SKILLS_PATH, index=False)
    file_size_mb = os.path.getsize(DATA_WITH_SKILLS_PATH) / (1024 * 1024)
    print(f"[INFO] Đã lưu kết quả ra {DATA_WITH_SKILLS_PATH} ({file_size_mb:.2f} MB)")
    print(f"[INFO] Tổng cộng {len(df)} records với cột skills_extracted")


def main():
    """
    Hàm chính điều phối toàn bộ pipeline trích xuất kỹ năng.

    Quy trình:
    1. Tải/xây dựng ontology kỹ năng
    2. Tải unified data
    3. Trích xuất kỹ năng cho mỗi record
    4. In thống kê
    5. Lưu kết quả
    """
    print("=" * 70)
    print("BƯỚC 2: TRÍCH XUẤT KỸ NĂNG (SKILL EXTRACTION)")
    print("=" * 70)
    print()

    try:
        # Bước 1: Tải hoặc xây dựng ontology
        print("--- 1. Tải Ontology ---")
        ontology = load_ontology()
        print()

        # Bước 2: Xử lý dữ liệu và trích xuất kỹ năng
        print("--- 2. Trích xuất Kỹ năng ---")
        df = process_unified_data(ontology)
        print()

        # Bước 3: In thống kê
        print("--- 3. Thống kê ---")
        print_extraction_stats(df)
        print()

        # Bước 4: Lưu kết quả
        print("--- 4. Lưu Kết quả ---")
        save_results(df)
        print()

        print("[DONE] Hoàn thành trích xuất kỹ năng!")

    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] Lỗi không mong muốn: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
