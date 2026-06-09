import sys
import json
from pathlib import Path

# ThÃẂm ÄÆḞáṠng dáẃḋn
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "KB+analysis+engine" / "skill_gap"))
sys.path.insert(0, str(Path(__file__).parent.parent / "KB+analysis+engine" / "skill_graph"))

from roadmap.roadmap_generator_v2 import RoadmapGeneratorV2

try:
    from skill_gap_engine import SkillGapEngine
    from skill_graph_engine import SkillGraphEngine
    print("[OK] Import engines thÃ nh cÃṀng")
except ImportError as e:
    print(f"[FAIL] LáṠi import: {e}")
    sys.exit(1)

# KháṠi táẃḂo engines
gap_engine = SkillGapEngine()
graph_engine = SkillGraphEngine()

# KháṠi táẃḂo RoadmapGeneratorV2
generator = RoadmapGeneratorV2(
    skill_gap_engine=gap_engine,
    skill_graph_engine=graph_engine
)
print("[OK] KháṠi táẃḂo RoadmapGeneratorV2 thÃ nh cÃṀng")

# ÄáṠc dáṠŸ liáṠu CV máẃḋu
cv_path = Path(__file__).parent.parent / "skill_gap" / "real_cv_full_analysis.json"
if not cv_path.exists():
    print(f"[FAIL] KhÃṀng tÃỲm tháẃċy file CV: {cv_path}")
    sys.exit(1)

with open(cv_path, "r", encoding="utf-8") as f:
    cv_data = json.load(f)

target_role = cv_data.get("target_role", "AI Engineer")
print(f"[OK] ÄáṠc CV thÃ nh cÃṀng. Target role: {target_role}")

# TáẃḂo roadmap
print("\n--- Äang táẃḂo roadmap ---")
result = generator.generate(
    cv_data=cv_data,
    target_role=target_role
)
print("[OK] TáẃḂo roadmap thÃ nh cÃṀng")

# Ghi káẃṡt quáẃ£ ra file
output_file = Path(__file__).parent / "roadmap_output_v2.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

print(f"\nâ ÄÃ£ xuáẃċt roadmap ra file: {output_file}")
print(f"ŵ SáṠ phases: {len(result.phases)}")
print(f"ŵŸ ATS hiáṠn táẃḂi: {result.ats_report['current_score']}% â dáṠḟ kiáẃṡn: {result.ats_report['final_score']}%")

# In tháṠ­ máṠt pháẃ§n narrative ÄáṠ kiáṠm tra
print("\n--- Máẃḋu narrative (phase 1) ---")
if result.narrative and result.narrative.get("phase_narratives"):
    print(result.narrative["phase_narratives"][0]["narrative"])

print("\n--- Personalized story ---")
if result.narrative and result.narrative.get("personalized_story"):
    print(result.narrative["personalized_story"]["summary"])

print("\n--- ATS report narrative ---")
if result.narrative and result.narrative.get("ats_report"):
    print(result.narrative["ats_report"]["report"])

print("\nâ HoÃ n thÃ nh!")