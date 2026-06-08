"""
Career Knowledge Base - Skill Ontology Builder
===============================================
Module tự động xây dựng Skill Ontology từ dữ liệu skills đã extract.

Quy trình:
1. Load data_with_skills.parquet (output của 02_skill_extractor.py)
2. Đếm tần suất tất cả skill variants
3. Group các variant giống nhau bằng fuzzy matching (difflib.SequenceMatcher)
4. Chọn variant phổ biến nhất làm canonical name
5. Áp dụng MANUAL_ALIASES overrides (manual luôn ưu tiên)
6. Xuất ra skill_ontology.json và skills_master.csv
"""

import json
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

# ============================================================
# Import cấu hình từ config.py
# ============================================================
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    DATA_WITH_SKILLS_PATH,
    DEFAULT_SEED_SKILLS,
    FUZZY_MATCH_THRESHOLD,
    MANUAL_ALIASES,
    SEED_ONTOLOGY_TOP_N,
    SKILL_ONTOLOGY_PATH,
    SKILLS_MASTER_PATH,
)


def load_skills_data() -> list[str]:
    """
    Load và flatten tất cả skills_extracted từ parquet file.
    Trả về danh sách phẳng chứa tất cả skill strings (có trùng lặp).
    """
    print(f"[ONT] Đang load dữ liệu từ: {DATA_WITH_SKILLS_PATH}")

    if not DATA_WITH_SKILLS_PATH.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file: {DATA_WITH_SKILLS_PATH}\n"
            "Hãy chạy 02_skill_extractor.py trước."
        )

    df = pd.read_parquet(DATA_WITH_SKILLS_PATH)

    # Kiểm tra cột skills_extracted có tồn tại không
    if "skills_extracted" not in df.columns:
        raise ValueError(
            f"Cột 'skills_extracted' không tồn tại trong {DATA_WITH_SKILLS_PATH}. "
            f"Các cột hiện có: {list(df.columns)}"
        )

    # Flatten danh sách skills từ tất cả records
    all_skills = []
    for skills_list in df["skills_extracted"]:
        # PyArrow may deserialize list columns as numpy ndarray
        if isinstance(skills_list, (list, tuple)) or (
            hasattr(skills_list, '__iter__') and hasattr(skills_list, '__len__')
            and not isinstance(skills_list, (str, bytes, dict))
        ):
            all_skills.extend(skills_list)
        elif isinstance(skills_list, str):
            # Phòng trường hợp skills được lưu dưới dạng string thay vì list
            all_skills.append(skills_list)

    print(f"[ONT] Tổng số skill instances (đã flatten): {len(all_skills):,}")
    return all_skills


def get_top_skills(all_skills: list[str], top_n: int) -> list[tuple[str, int]]:
    """
    Đếm tần suất và trả về top N skills phổ biến nhất.
    """
    counter = Counter(all_skills)
    top_skills = counter.most_common(top_n)
    unique_count = len(counter)

    print(f"[ONT] Tổng số unique skills: {unique_count:,}")
    print(f"[ONT] Lấy top {top_n} skills để xây ontology")

    return top_skills


def fuzzy_group_skills(
    skills_with_freq: list[tuple[str, int]],
    threshold: float,
) -> dict[str, list[tuple[str, int]]]:
    """
    Nhóm các skill variants giống nhau bằng fuzzy matching.

    Thuật toán:
    - Duyệt qua từng cặp skill
    - Nếu similarity >= threshold, gộp vào cùng một group
    - Dùng Union-Find để quản lý groups hiệu quả
    - Variant có frequency cao nhất được chọn làm canonical

    Args:
        skills_with_freq: Danh sách (skill_name, frequency)
        threshold: Ngưỡng tương đồng (0-100)

    Returns:
        Dict mapping canonical_skill -> list of (variant, frequency)
    """
    n = len(skills_with_freq)
    print(f"[ONT] Bắt đầu fuzzy grouping cho {n} skills (threshold={threshold})...")

    # Union-Find data structure để quản lý groups
    parent = list(range(n))

    def find(x: int) -> int:
        """Tìm root của element với path compression."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # Path compression
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        """Hợp nhất hai groups."""
        rx, ry = find(x), find(y)
        if rx != ry:
            # Luôn giữ index nhỏ hơn làm root (để deterministic)
            if rx < ry:
                parent[ry] = rx
            else:
                parent[rx] = ry

    # Chuẩn hóa tên skills để so sánh (lowercase, strip)
    normalized = [s.lower().strip() for s, _ in skills_with_freq]

    # So sánh từng cặp - O(n^2) nhưng n <= SEED_ONTOLOGY_TOP_N (200) nên chấp nhận được
    comparisons = 0
    merges = 0
    for i in range(n):
        for j in range(i + 1, n):
            comparisons += 1
            # Tính similarity ratio (0.0 - 1.0)
            ratio = SequenceMatcher(None, normalized[i], normalized[j]).ratio()
            if ratio * 100 >= threshold:
                union(i, j)
                merges += 1

    print(f"[ONT] Đã so sánh {comparisons:,} cặp, gộp được {merges} cặp")

    # Gom nhóm theo root
    groups = defaultdict(list)
    for i in range(n):
        root = find(i)
        groups[root].append(skills_with_freq[i])

    # Với mỗi group, chọn variant có frequency cao nhất làm canonical
    result = {}
    for root, members in groups.items():
        # Sắp xếp theo frequency giảm dần, nếu bằng thì lấy tên ngắn hơn
        members_sorted = sorted(members, key=lambda x: (-x[1], len(x[0])))
        canonical = members_sorted[0][0]  # Variant phổ biến nhất
        result[canonical] = members_sorted

    num_groups = len(result)
    num_merged = sum(1 for v in result.values() if len(v) > 1)
    print(f"[ONT] Kết quả: {num_groups} groups, trong đó {num_merged} groups có nhiều variants")

    return result


def build_ontology(
    grouped_skills: dict[str, list[tuple[str, int]]],
    manual_aliases: dict[str, str],
    seed_skills: list[str],
) -> tuple[dict[str, str], pd.DataFrame]:
    """
    Xây dựng ontology hoàn chỉnh từ fuzzy groups + manual aliases + seed skills.

    Returns:
        Tuple của (ontology_dict, master_dataframe)
    """
    # ============================================================
    # Bước 1: Tạo mapping từ fuzzy grouping
    # alias (lowercase) -> canonical skill name
    # ============================================================
    ontology = {}

    # Mapping ngược: lowercase(canonical) -> canonical (để xử lý manual overrides)
    canonical_lookup = {}

    for canonical, variants in grouped_skills.items():
        canonical_lower = canonical.lower().strip()
        canonical_lookup[canonical_lower] = canonical

        # Map tất cả variants về canonical
        for variant, freq in variants:
            variant_lower = variant.lower().strip()
            ontology[variant_lower] = canonical

    # ============================================================
    # Bước 2: Áp dụng MANUAL_ALIASES (manual LUÔN ưu tiên)
    # ============================================================
    manual_override_count = 0
    for alias, canonical in manual_aliases.items():
        alias_lower = alias.lower().strip()
        old_canonical = ontology.get(alias_lower)

        # Manual override: ghi đè lên auto-discovered mapping
        if old_canonical != canonical:
            ontology[alias_lower] = canonical
            manual_override_count += 1

        # Đảm bảo canonical cũng map đến chính nó
        canonical_lower = canonical.lower().strip()
        if canonical_lower not in ontology:
            ontology[canonical_lower] = canonical

    print(f"[ONT] Manual aliases áp dụng: {len(manual_aliases)}, overrides: {manual_override_count}")

    # ============================================================
    # Bước 3: Thêm seed skills (mỗi seed skill map đến chính nó)
    # ============================================================
    seed_added = 0
    for skill in seed_skills:
        skill_lower = skill.lower().strip()
        if skill_lower not in ontology:
            ontology[skill_lower] = skill
            seed_added += 1
        else:
            # Seed skill đã tồn tại - kiểm tra xem có cần cập nhật canonical không
            # Nếu seed skill là canonical form chuẩn, đảm bảo mapping đúng
            existing_canonical = ontology[skill_lower]
            if existing_canonical.lower() == skill_lower and existing_canonical != skill:
                # Cập nhật để dùng đúng casing từ seed list
                ontology[skill_lower] = skill

    print(f"[ONT] Seed skills thêm mới: {seed_added}/{len(seed_skills)}")

    # ============================================================
    # Bước 4: Xây DataFrame master skills
    # ============================================================
    # Tính tổng frequency cho mỗi canonical skill
    canonical_freq = Counter()
    canonical_aliases = defaultdict(set)

    for alias_lower, canonical in ontology.items():
        canonical_freq[canonical] += 0  # Đảm bảo canonical xuất hiện
        canonical_aliases[canonical].add(alias_lower)

    # Cộng frequency từ grouped data
    for canonical, variants in grouped_skills.items():
        # Tìm canonical cuối cùng sau khi áp dụng manual aliases
        final_canonical = ontology.get(canonical.lower().strip(), canonical)
        for variant, freq in variants:
            canonical_freq[final_canonical] += freq
            canonical_aliases[final_canonical].add(variant.lower().strip())

    # Tạo DataFrame
    master_records = []
    for canonical, freq in canonical_freq.items():
        aliases = sorted(canonical_aliases.get(canonical, set()))
        # Loại bỏ canonical itself khỏi danh sách aliases nếu trùng
        aliases_clean = [a for a in aliases if a != canonical.lower().strip()]
        master_records.append({
            "skill": canonical,
            "frequency": freq,
            "aliases": ", ".join(aliases_clean) if aliases_clean else "",
        })

    master_df = pd.DataFrame(master_records)
    master_df = master_df.sort_values("frequency", ascending=False).reset_index(drop=True)

    return ontology, master_df


def save_outputs(
    ontology: dict[str, str],
    master_df: pd.DataFrame,
) -> None:
    """Lưu ontology và master skills ra files."""
    # Lưu skill_ontology.json
    with open(SKILL_ONTOLOGY_PATH, "w", encoding="utf-8") as f:
        json.dump(ontology, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"[ONT] Đã lưu ontology: {SKILL_ONTOLOGY_PATH} ({len(ontology)} mappings)")

    # Lưu skills_master.csv
    master_df.to_csv(SKILLS_MASTER_PATH, index=False, encoding="utf-8-sig")
    print(f"[ONT] Đã lưu master skills: {SKILLS_MASTER_PATH} ({len(master_df)} skills)")


def print_stats(
    ontology: dict[str, str],
    master_df: pd.DataFrame,
    grouped_skills: dict[str, list[tuple[str, int]]],
) -> None:
    """In thống kê tổng quan về ontology đã xây dựng."""
    print("\n" + "=" * 60)
    print("THỐNG KÊ ONTOLOGY")
    print("=" * 60)

    # Số lượng unique canonical skills
    unique_canonical = set(ontology.values())
    print(f"Tổng số alias mappings: {len(ontology):,}")
    print(f"Tổng số canonical skills: {len(unique_canonical):,}")
    print(f"Số groups từ fuzzy matching: {len(grouped_skills):,}")

    # Top 20 canonical skills phổ biến nhất
    print(f"\nTop 20 Canonical Skills (theo frequency):")
    print("-" * 50)
    top_20 = master_df.head(20)
    for idx, row in top_20.iterrows():
        alias_count = len(row["aliases"].split(", ")) if row["aliases"] else 0
        print(f"  {idx+1:>2}. {row['skill']:<30} freq={row['frequency']:>5}  aliases={alias_count}")

    # Số skills chỉ có 1 alias (không merge được)
    single_alias = master_df[master_df["aliases"] == ""].shape[0]
    multi_alias = master_df[master_df["aliases"] != ""].shape[0]
    print(f"\nSkills đơn lẻ (no aliases): {single_alias}")
    print(f"Skills có aliases (merged):   {multi_alias}")
    print("=" * 60)


def main():
    """Hàm chính điều phối toàn bộ quy trình xây ontology."""
    print("\n" + "=" * 60)
    print("SKILL ONTOLOGY BUILDER")
    print("=" * 60)

    try:
        # Bước 1: Load và flatten skills data
        all_skills = load_skills_data()

        if not all_skills:
            print("[ONT] WARNING: Không có skills nào được tìm thấy. Sử dụng seed skills.")
            # Fallback: tạo ontology chỉ từ seed skills + manual aliases
            top_skills = [(s, 0) for s in DEFAULT_SEED_SKILLS]
        else:
            # Bước 2: Lấy top N skills phổ biến nhất
            top_skills = get_top_skills(all_skills, SEED_ONTOLOGY_TOP_N)

        # Bước 3: Fuzzy grouping các skill variants
        grouped_skills = fuzzy_group_skills(top_skills, FUZZY_MATCH_THRESHOLD)

        # Bước 4: Xây ontology hoàn chỉnh
        ontology, master_df = build_ontology(
            grouped_skills=grouped_skills,
            manual_aliases=MANUAL_ALIASES,
            seed_skills=DEFAULT_SEED_SKILLS,
        )

        # Bước 5: Lưu outputs
        save_outputs(ontology, master_df)

        # Bước 6: In thống kê
        print_stats(ontology, master_df, grouped_skills)

        print("\n[ONT] Hoàn thành xây dựng Skill Ontology!")

    except FileNotFoundError as e:
        print(f"\n[ONT] ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ONT] ERROR không mong muốn: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
