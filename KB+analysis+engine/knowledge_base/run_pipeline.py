"""
Career Knowledge Base - Pipeline Orchestrator
==============================================
Chạy toàn bộ pipeline xây dựng Career Knowledge Base theo đúng thứ tự.

Sử dụng:
    python run_pipeline.py              # Chạy tất cả 7 bước
    python run_pipeline.py --step 3     # Chỉ chạy bước 3
    python run_pipeline.py --from-step 4 # Chạy từ bước 4 trở đi
    python run_pipeline.py --list       # Liệt kê các bước
"""

# Fix UTF-8 encoding cho Windows terminal
import sys
import os
if sys.platform == "win32":
    os.environ["PYTHONIOENCODING"] = "utf-8"
    # Reconfigure stdout/stderr to use UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import time
import argparse
import traceback
from pathlib import Path
from datetime import datetime

# ============================================================================
# Cấu hình đường dẫn để import các module trong cùng thư mục
# ============================================================================
PIPELINE_DIR = Path(__file__).parent.resolve()
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

OUTPUT_DIR = PIPELINE_DIR / "outputs"

# ============================================================================
# Định nghĩa các bước trong pipeline
# ============================================================================
PIPELINE_STEPS = [
    {
        "step": 1,
        "module": "01_data_loader",
        "description": "Tải và hợp nhất 4 nguồn dữ liệu → unified_data.parquet",
        "outputs": ["unified_data.parquet"],
    },
    {
        "step": 2,
        "module": "02_skill_extractor",
        "description": "Trích xuất kỹ năng từ văn bản → data_with_skills.parquet",
        "outputs": ["data_with_skills.parquet"],
    },
    {
        "step": 3,
        "module": "03_ontology_builder",
        "description": "Xây dựng ontology kỹ năng → skill_ontology.json + skills_master.csv",
        "outputs": ["skill_ontology.json", "skills_master.csv"],
    },
    {
        "step": 4,
        "module": "04_role_skill_matrix",
        "description": "Xây dựng ma trận vai trò - kỹ năng → role_skill_matrix.csv",
        "outputs": ["role_skill_matrix.csv"],
    },
    {
        "step": 5,
        "module": "05_career_transition",
        "description": "Xây dựng đồ thị chuyển đổi nghề nghiệp → career_graph.json",
        "outputs": ["career_graph.json"],
    },
    {
        "step": 6,
        "module": "06_profile_normalizer",
        "description": "Chuẩn hóa hồ sơ → resume_profiles.parquet + job_profiles.parquet",
        "outputs": ["resume_profiles.parquet", "job_profiles.parquet"],
    },
    {
        "step": 7,
        "module": "07_vector_indexer",
        "description": "Tạo vector embeddings → chroma_db/",
        "outputs": [],  # Thư mục chroma_db/ không kiểm tra file cụ thể
    },
]

# Bước 8 (08_knowledge_api.py) là API layer, không tạo output file nên không chạy tự động


def _import_main(module_name: str):
    """Import hàm main() từ một module trong pipeline."""
    try:
        mod = __import__(module_name)
        if not hasattr(mod, "main"):
            raise AttributeError(
                f"Module '{module_name}' không có hàm main()"
            )
        return mod.main
    except ImportError as e:
        raise ImportError(
            f"Không thể import module '{module_name}': {e}"
        ) from e


def run_step(step_info: dict) -> bool:
    """
    Chạy một bước trong pipeline.

    Returns:
        True nếu thành công, False nếu thất bại.
    """
    step_num = step_info["step"]
    module_name = step_info["module"]
    description = step_info["description"]
    total_steps = len(PIPELINE_STEPS)

    print(f"\n{'='*70}")
    print(f"  [BƯỚC {step_num}/{total_steps}] {description}")
    print(f"  Module: {module_name}.py")
    print(f"{'='*70}")

    start_time = time.time()

    try:
        main_func = _import_main(module_name)
        main_func()
        elapsed = time.time() - start_time
        print(f"\n  ✓ Bước {step_num} hoàn thành trong {elapsed:.1f}s")
        return True

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"\n  ✗ Bước {step_num} THẤT BẠI sau {elapsed:.1f}s")
        print(f"  Lỗi: {e}")
        traceback.print_exc()
        return False


def verify_outputs(steps_to_check: list[dict]) -> None:
    """Kiểm tra các file output đã được tạo chưa và in bảng tóm tắt."""
    print(f"\n{'='*70}")
    print("  KIỂM TRA OUTPUT")
    print(f"{'='*70}\n")

    results = []
    for step_info in steps_to_check:
        for filename in step_info["outputs"]:
            filepath = OUTPUT_DIR / filename
            exists = filepath.exists()
            size_str = ""
            if exists:
                size_bytes = filepath.stat().st_size
                if size_bytes >= 1_048_576:
                    size_str = f"{size_bytes / 1_048_576:.1f} MB"
                elif size_bytes >= 1024:
                    size_str = f"{size_bytes / 1024:.1f} KB"
                else:
                    size_str = f"{size_bytes} B"
            results.append({
                "step": step_info["step"],
                "file": filename,
                "exists": exists,
                "size": size_str,
            })

    # In bảng tóm tắt
    header = f"  {'Bước':<6} {'File Output':<30} {'Trạng thái':<12} {'Kích thước':<12}"
    print(header)
    print(f"  {'-'*60}")

    success_count = 0
    fail_count = 0
    for r in results:
        status = "✓ OK" if r["exists"] else "✗ THIẾU"
        size = r["size"] if r["exists"] else "-"
        line = f"  {r['step']:<6} {r['file']:<30} {status:<12} {size:<12}"
        print(line)
        if r["exists"]:
            success_count += 1
        else:
            fail_count += 1

    print(f"  {'-'*60}")
    print(f"  Tổng: {success_count} file OK, {fail_count} file thiếu")

    # Kiểm tra riêng thư mục chroma_db cho bước 7
    chroma_dir = OUTPUT_DIR / "chroma_db"
    if chroma_dir.exists():
        print(f"  ✓ Thư mục chroma_db/ tồn tại ({chroma_dir})")
    else:
        print(f"  ✗ Thư mục chroma_db/ chưa được tạo")


def list_steps() -> None:
    """Liệt kê tất cả các bước trong pipeline."""
    print("\n  CÁC BƯỚC TRONG CAREER KNOWLEDGE BASE PIPELINE\n")
    print(f"  {'Bước':<6} {'Module':<25} {'Mô tả'}")
    print(f"  {'-'*70}")
    for s in PIPELINE_STEPS:
        print(f"  {s['step']:<6} {s['module']:<25} {s['description']}")
    print(f"\n  Bước 8: 08_knowledge_api.py (API layer, không chạy tự động)")
    print()


def build_parser() -> argparse.ArgumentParser:
    """Xây dựng argument parser cho CLI."""
    parser = argparse.ArgumentParser(
        description="Career Knowledge Base - Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Ví dụ:
  python run_pipeline.py                Chạy toàn bộ pipeline
  python run_pipeline.py --step 3       Chỉ chạy bước 3 (Ontology Builder)
  python run_pipeline.py --from-step 4  Chạy từ bước 4 đến hết
  python run_pipeline.py --list         Liệt kê các bước
""",
    )
    parser.add_argument(
        "--step",
        type=int,
        default=None,
        help="Chỉ chạy một bước cụ thể (1-7)",
    )
    parser.add_argument(
        "--from-step",
        type=int,
        default=None,
        dest="from_step",
        help="Chạy từ bước này trở đi (1-7)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Liệt kê tất cả các bước trong pipeline",
    )
    return parser


def main():
    """Hàm chính điều phối toàn bộ pipeline."""
    parser = build_parser()
    args = parser.parse_args()

    # Xử lý --list
    if args.list:
        list_steps()
        return

    # Xác định các bước cần chạy
    if args.step is not None:
        if args.step < 1 or args.step > len(PIPELINE_STEPS):
            print(f"Lỗi: --step phải nằm trong khoảng 1-{len(PIPELINE_STEPS)}")
            sys.exit(1)
        steps_to_run = [s for s in PIPELINE_STEPS if s["step"] == args.step]
        mode_desc = f"chạy bước {args.step}"
    elif args.from_step is not None:
        if args.from_step < 1 or args.from_step > len(PIPELINE_STEPS):
            print(f"Lỗi: --from-step phải nằm trong khoảng 1-{len(PIPELINE_STEPS)}")
            sys.exit(1)
        steps_to_run = [s for s in PIPELINE_STEPS if s["step"] >= args.from_step]
        mode_desc = f"chạy từ bước {args.from_step} trở đi"
    else:
        steps_to_run = PIPELINE_STEPS[:]
        mode_desc = "chạy toàn bộ pipeline"

    # Đảm bảo thư mục outputs tồn tại
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # In thông tin bắt đầu
    print(f"\n{'#'*70}")
    print(f"  CAREER KNOWLEDGE BASE PIPELINE")
    print(f"  Thời gian bắt đầu: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Chế độ: {mode_desc}")
    print(f"  Số bước sẽ chạy: {len(steps_to_run)}")
    print(f"  Thư mục output: {OUTPUT_DIR}")
    print(f"{'#'*70}")

    pipeline_start = time.time()
    step_results = {}

    # Chạy từng bước theo thứ tự
    for step_info in steps_to_run:
        success = run_step(step_info)
        step_results[step_info["step"]] = success

        # Nếu bước thất bại, in cảnh báo nhưng vẫn tiếp tục
        if not success:
            print(f"\n  ⚠ CẢNH BÁO: Bước {step_info['step']} thất bại.")
            print(f"    Pipeline sẽ tiếp tục chạy bước tiếp theo.")
            print(f"    Một số bước sau có thể bị ảnh hưởng do thiếu dữ liệu đầu vào.\n")

    # Tính tổng thời gian
    total_elapsed = time.time() - pipeline_start

    # In kết quả từng bước
    print(f"\n{'='*70}")
    print("  KẾT QUẢ PIPELINE")
    print(f"{'='*70}\n")

    for step_info in steps_to_run:
        step_num = step_info["step"]
        status = "✓ THÀNH CÔNG" if step_results.get(step_num, False) else "✗ THẤT BẠI"
        print(f"  Bước {step_num}: {step_info['module']:<25} {status}")

    # Kiểm tra output files
    verify_outputs(steps_to_run)

    # In tổng kết
    succeeded = sum(1 for v in step_results.values() if v)
    failed = sum(1 for v in step_results.values() if not v)

    print(f"\n{'#'*70}")
    print(f"  TỔNG KẾT")
    print(f"  Thời gian kết thúc: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Tổng thời gian: {total_elapsed:.1f}s ({total_elapsed/60:.1f} phút)")
    print(f"  Thành công: {succeeded}/{len(steps_to_run)} bước")
    if failed > 0:
        print(f"  Thất bại: {failed}/{len(steps_to_run)} bước")
    print(f"{'#'*70}\n")

    # Trả về exit code phù hợp
    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
