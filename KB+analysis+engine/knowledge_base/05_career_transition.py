"""
Career Transition Graph Builder
================================
Xây dựng đồ thị chuyển đổi nghề nghiệp dựa trên mức độ trùng lặp kỹ năng giữa các vai trò.

Logic:
- Tính Jaccard similarity của tập skill (freq >= 30%) giữa từng cặp role
- Nếu similarity >= 0.25 => tạo edge chuyển đổi
- Hướng: từ role ít skill hơn sang role nhiều skill hơn (heuristic junior -> senior)
- Bổ sung các transition phổ biến làm seed
"""

import json
import sys
from itertools import combinations
from pathlib import Path

import pandas as pd

# Thêm thư mục knowledge_base vào path để import config
sys.path.insert(0, str(Path(__file__).parent))
from config import CAREER_GRAPH_PATH, ROLE_SKILL_MATRIX_PATH

# ============================================================
# 1. CÁC THAM SỐ CẤU HÌNH
# ============================================================
# Ngưỡng tần suất tối thiểu để coi một skill là "đặc trưng" của role
SKILL_FREQ_THRESHOLD = 30.0

# Ngưỡng Jaccard similarity tối thiểu để tạo edge chuyển đổi
SIMILARITY_THRESHOLD = 0.25

# Ngưỡng tần suất để xác định "top skills" khi tính new_skills_needed
TOP_SKILL_FREQ_THRESHOLD = 50.0

# Các transition phổ biến làm seed (luôn được đưa vào đồ thị)
PREDEFINED_TRANSITIONS = [
    ("Data Analyst", "Data Scientist"),
    ("Data Scientist", "ML Engineer"),
    ("ML Engineer", "AI Engineer"),
    ("Frontend Developer", "Fullstack Developer"),
    ("Fullstack Developer", "Tech Lead"),
    ("Backend Developer", "Fullstack Developer"),
    ("QA Tester", "Automation QA"),
    ("Automation QA", "SDET"),
    ("Business Analyst", "Product Manager"),
]


# ============================================================
# 2. HÀM TÍNH TOÁN
# ============================================================
def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Tính Jaccard similarity giữa hai tập hợp."""
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def load_role_skill_matrix(path: Path) -> pd.DataFrame:
    """
    Đọc file role_skill_matrix.csv và trả về DataFrame.
    Kiểm tra sự tồn tại của file trước khi đọc.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file role_skill_matrix tại: {path}\n"
            "Hãy chạy module 04_role_skill_matrix.py trước."
        )

    df = pd.read_csv(path)

    # Kiểm tra các cột bắt buộc
    required_cols = {"role", "skill", "frequency_pct"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"File role_skill_matrix thiếu các cột: {missing}")

    print(f"[LOAD] Đã đọc {len(df)} dòng từ {path.name}")
    print(f"[LOAD] Số role duy nhất: {df['role'].nunique()}")
    return df


def build_role_skill_sets(df: pd.DataFrame) -> dict:
    """
    Xây dựng dictionary ánh xạ role -> tập hợp các skill có frequency_pct >= ngưỡng.
    Trả về: {role_name: set(skill_names)}
    """
    filtered = df[df["frequency_pct"] >= SKILL_FREQ_THRESHOLD]
    role_skills = {}
    for role, group in filtered.groupby("role"):
        role_skills[role] = set(group["skill"].tolist())
    print(f"[SKILLS] Đã xây dựng skill sets cho {len(role_skills)} roles "
          f"(ngưỡng freq >= {SKILL_FREQ_THRESHOLD}%)")
    return role_skills


def build_top_skills_map(df: pd.DataFrame) -> dict:
    """
    Xây dựng dictionary ánh xạ role -> tập hợp top skills (freq >= TOP_SKILL_FREQ_THRESHOLD).
    Dùng để xác định new_skills_needed khi chuyển đổi.
    """
    filtered = df[df["frequency_pct"] >= TOP_SKILL_FREQ_THRESHOLD]
    top_skills = {}
    for role, group in filtered.groupby("role"):
        top_skills[role] = set(group["skill"].tolist())
    return top_skills


def compute_transitions(role_skills: dict, top_skills_map: dict) -> list:
    """
    Tính toán tất cả transitions dựa trên Jaccard similarity.
    Hướng: từ role ít skill hơn -> role nhiều skill hơn.
    """
    transitions = []
    roles = list(role_skills.keys())

    # Duyệt qua từng cặp role
    for role_a, role_b in combinations(roles, 2):
        skills_a = role_skills[role_a]
        skills_b = role_skills[role_b]

        similarity = jaccard_similarity(skills_a, skills_b)

        if similarity < SIMILARITY_THRESHOLD:
            continue

        # Xác định hướng: từ ít skill -> nhiều skill (junior -> senior heuristic)
        if len(skills_a) <= len(skills_b):
            from_role, to_role = role_a, role_b
            from_skills, to_skills = skills_a, skills_b
        else:
            from_role, to_role = role_b, role_a
            from_skills, to_skills = skills_b, skills_a

        # Tính shared skills và new skills needed
        shared = sorted(from_skills & to_skills)
        to_top = top_skills_map.get(to_role, set())
        from_top = top_skills_map.get(from_role, set())
        new_needed = sorted(to_top - from_top)

        transitions.append({
            "from": from_role,
            "to": to_role,
            "weight": round(similarity, 4),
            "shared_skills": shared,
            "new_skills_needed": new_needed,
        })

    print(f"[TRANSITIONS] Tìm được {len(transitions)} transitions từ skill overlap")
    return transitions


def add_predefined_transitions(
    existing_transitions: list,
    role_skills: dict,
    top_skills_map: dict,
) -> list:
    """
    Bổ sung các predefined transitions nếu chưa tồn tại trong danh sách.
    Tính weight và new_skills_needed cho các seed transitions.
    """
    # Tạo set các cặp đã có để tránh trùng lặp
    existing_pairs = {(t["from"], t["to"]) for t in existing_transitions}
    added_count = 0

    for from_role, to_role in PREDEFINED_TRANSITIONS:
        if (from_role, to_role) in existing_pairs:
            continue

        # Tính skill overlap ngay cả khi role không có trong data
        from_skills = role_skills.get(from_role, set())
        to_skills = role_skills.get(to_role, set())

        if from_skills or to_skills:
            similarity = jaccard_similarity(from_skills, to_skills)
        else:
            # Cả hai role đều không có trong data => dùng weight mặc định thấp
            similarity = 0.3

        shared = sorted(from_skills & to_skills)
        to_top = top_skills_map.get(to_role, set())
        from_top = top_skills_map.get(from_role, set())
        new_needed = sorted(to_top - from_top)

        existing_transitions.append({
            "from": from_role,
            "to": to_role,
            "weight": round(similarity, 4),
            "shared_skills": shared,
            "new_skills_needed": new_needed,
        })
        existing_pairs.add((from_role, to_role))
        added_count += 1

    print(f"[SEED] Đã bổ sung {added_count} predefined transitions")
    return existing_transitions


def collect_all_roles(transitions: list) -> list:
    """Thu thập danh sách tất cả roles xuất hiện trong transitions (đã sort)."""
    roles = set()
    for t in transitions:
        roles.add(t["from"])
        roles.add(t["to"])
    return sorted(roles)


# ============================================================
# 3. HÀM CHÍNH
# ============================================================
def build_career_graph():
    """
    Hàm chính: xây dựng Career Transition Graph và lưu ra JSON.
    """
    print("=" * 60)
    print("XÂY DỰNG CAREER TRANSITION GRAPH")
    print("=" * 60)

    # Bước 1: Đọc dữ liệu role-skill matrix
    try:
        df = load_role_skill_matrix(ROLE_SKILL_MATRIX_PATH)
    except (FileNotFoundError, ValueError) as e:
        print(f"[ERROR] {e}")
        return None

    # Bước 2: Xây dựng skill sets cho từng role
    role_skills = build_role_skill_sets(df)
    if not role_skills:
        print("[ERROR] Không có role nào đủ điều kiện. Kiểm tra lại dữ liệu.")
        return None

    # Bước 3: Xây dựng top skills map (cho việc tính new_skills_needed)
    top_skills_map = build_top_skills_map(df)

    # Bước 4: Tính transitions từ skill overlap
    transitions = compute_transitions(role_skills, top_skills_map)

    # Bước 5: Bổ sung predefined transitions
    transitions = add_predefined_transitions(transitions, role_skills, top_skills_map)

    # Sắp xếp transitions theo weight giảm dần
    transitions.sort(key=lambda x: x["weight"], reverse=True)

    # Bước 6: Thu thập danh sách roles
    all_roles = collect_all_roles(transitions)

    # Bước 7: Đóng gói kết quả
    result = {
        "transitions": transitions,
        "roles": all_roles,
        "metadata": {
            "total_transitions": len(transitions),
            "total_roles": len(all_roles),
            "skill_freq_threshold": SKILL_FREQ_THRESHOLD,
            "similarity_threshold": SIMILARITY_THRESHOLD,
            "top_skill_freq_threshold": TOP_SKILL_FREQ_THRESHOLD,
        },
    }

    # Bước 8: Lưu ra file JSON
    try:
        CAREER_GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CAREER_GRAPH_PATH, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\n[SAVE] Đã lưu career graph tại: {CAREER_GRAPH_PATH}")
    except OSError as e:
        print(f"[ERROR] Không thể ghi file: {e}")
        return None

    # Bước 9: In thống kê tóm tắt
    print("\n" + "=" * 60)
    print("THỐNG KÊ TỔNG QUAN")
    print("=" * 60)
    print(f"  Tổng số transitions: {len(transitions)}")
    print(f"  Tổng số roles:       {len(all_roles)}")

    # In một vài transitions tiêu biểu
    print("\n--- Top 10 transitions (theo weight) ---")
    for i, t in enumerate(transitions[:10], 1):
        shared_str = ", ".join(t["shared_skills"][:5])
        if len(t["shared_skills"]) > 5:
            shared_str += f" (+{len(t['shared_skills']) - 5} khác)"
        new_str = ", ".join(t["new_skills_needed"][:5])
        if len(t["new_skills_needed"]) > 5:
            new_str += f" (+{len(t['new_skills_needed']) - 5} khác)"
        print(f"  {i:2d}. {t['from']} -> {t['to']} "
              f"(weight={t['weight']:.3f})")
        print(f"      Shared: [{shared_str}]")
        print(f"      Cần học thêm: [{new_str}]")

    print("\n[DONE] Hoàn thành xây dựng Career Transition Graph!")
    return result


# ============================================================
# 4. ENTRY POINT
# ============================================================
def main():
    """Entry point cho pipeline orchestrator."""
    return build_career_graph()


if __name__ == "__main__":
    main()
