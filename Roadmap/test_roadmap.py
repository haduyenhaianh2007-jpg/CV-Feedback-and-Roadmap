"""
Test script for Roadmap Module
Tests with real CV data from skill_gap/real_cv_full_analysis.json
"""
import sys
import json
from pathlib import Path
import io

# Ensure UTF-8 output encoding for Vietnamese characters
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add KB+analysis+engine to path (both skill_gap and skill_graph)
kb_skill_gap_path = project_root / "KB+analysis+engine" / "skill_gap"
kb_skill_graph_path = project_root / "KB+analysis+engine" / "skill_graph"
sys.path.insert(0, str(kb_skill_gap_path))
sys.path.insert(0, str(kb_skill_graph_path))

# Also add the parent directory of KB+analysis+engine to path
sys.path.insert(0, str(project_root / "KB+analysis+engine"))

# Import as package
from roadmap.roadmap_generator import RoadmapGenerator
from roadmap.stage_detector import StageDetector
from roadmap.project_templates import ProjectPool
from roadmap.ats_projector import ATSProjector

try:
    # Try direct import first
    from skill_gap_engine import SkillGapEngine
    from skill_graph_engine import SkillGraphEngine
    print("[OK] Successfully imported SkillGapEngine and SkillGraphEngine")
except ImportError:
    try:
        # Try with skill_gap.skill_gap_engine format
        from skill_gap.skill_gap_engine import SkillGapEngine
        from skill_graph.skill_graph_engine import SkillGraphEngine
        print("[OK] Successfully imported from skill_gap/skill_graph submodules")
    except ImportError as e:
        print(f"[FAIL] Failed to import engines: {e}")
        sys.exit(1)


def load_real_cv():
    """Load real CV data for testing."""
    cv_path = project_root / "skill_gap" / "real_cv_full_analysis.json"

    if not cv_path.exists():
        print(f"[FAIL] CV file not found: {cv_path}")
        return None

    with open(cv_path, 'r', encoding='utf-8') as f:
        cv_data = json.load(f)

    print(f"[OK] Loaded CV from: {cv_path}")
    print(f"  Target role: {cv_data.get('target_role', 'N/A')}")
    print(f"  Readiness score: {cv_data.get('readiness_score', 'N/A')}")
    print(f"  Strengths: {len(cv_data.get('strengths', []))}")
    print(f"  Improvement actions: {len(cv_data.get('improvement_actions', []))}")

    return cv_data


def test_stage_detector(cv_data):
    """Test stage detector with CV data."""
    print("\n" + "="*70)
    print("TEST 1: Stage Detector")
    print("="*70)

    detector = StageDetector()

    # Prepare CV data for stage detection
    cv_for_stage = {
        "work_history": [],  # No work history in real CV
        "skills": [s["skill"] for s in cv_data.get("strengths", [])],
        "education": {"degree": "Bachelor", "status": "graduated"}
    }

    result = detector.detect(cv_for_stage)

    print(f"Stage: {result.stage}")
    print(f"Confidence: {result.confidence:.2f}")
    print(f"Signals:")
    for key, value in result.signals.items():
        print(f"  - {key}: {value}")

    return result


def test_project_pool():
    """Test project pool selection."""
    print("\n" + "="*70)
    print("TEST 2: Project Pool")
    print("="*70)

    pool = ProjectPool()

    # Test with SQL + ML skills
    phase_skills = ["SQL", "Machine Learning"]
    stage = "Fresher"

    suggestions = pool.select(phase_skills, stage, max_suggestions=3)

    print(f"Phase skills: {phase_skills}")
    print(f"Stage: {stage}")
    print(f"Suggestions found: {len(suggestions)}")

    for i, proj in enumerate(suggestions, 1):
        print(f"\n{i}. {proj.name}")
        print(f"   Difficulty: {proj.difficulty}")
        print(f"   Match score: {proj.match_score:.2f}")
        print(f"   Tech stack: {', '.join(proj.tech_stack)}")

    return pool


def test_full_roadmap(cv_data):
    """Test full roadmap generation."""
    print("\n" + "="*70)
    print("TEST 3: Full Roadmap Generation")
    print("="*70)

    # Initialize engines
    gap_engine = SkillGapEngine()
    graph_engine = SkillGraphEngine()

    print("[OK] Initialized SkillGapEngine and SkillGraphEngine")

    # Initialize roadmap generator
    generator = RoadmapGenerator(
        skill_gap_engine=gap_engine,
        skill_graph_engine=graph_engine
    )

    print("[OK] Initialized RoadmapGenerator")

    # Prepare CV data
    cv_for_roadmap = {
        "work_history": [],
        "skills": [s["skill"] for s in cv_data.get("strengths", [])],
        "education": {"degree": "Bachelor", "status": "graduated"}
    }

    target_role = cv_data.get("target_role", "AI Engineer")

    print(f"\nGenerating roadmap for:")
    print(f"  Current skills: {cv_for_roadmap['skills']}")
    print(f"  Target role: {target_role}")

    # Generate roadmap
    roadmap = generator.generate(
        cv_data=cv_for_roadmap,
        target_role=target_role
    )

    print("\n[OK] Roadmap generated successfully!")

    # Display results
    print("\n" + "="*70)
    print("ROADMAP RESULTS (CONTRACT)")
    print("="*70)

    print(f"\nStage: {roadmap.metadata['stage']} (confidence: {roadmap.metadata['confidence']:.2f})")
    print(f"Target role: {roadmap.metadata['target_role']}")
    print(f"Current readiness: {roadmap.ats_projection['current']}%")
    print(f"Final projected readiness: {roadmap.ats_projection['final']}%")

    print(f"\nUser Skill Overlay:")
    print(f"  🟢 Completed ({len(roadmap.user_overlay['completed'])}): {', '.join(roadmap.user_overlay['completed'])}")
    print(f"  🟡 Partial ({len(roadmap.user_overlay['partial'])}): {', '.join(roadmap.user_overlay['partial'])}")
    print(f"  🔴 Missing ({len(roadmap.user_overlay['missing'])}): {', '.join(roadmap.user_overlay['missing'])}")
    print(f"  Recommended next: {', '.join(roadmap.user_overlay['recommended_next'][:5])}")

    print(f"\nATS Projection by Phase:")
    for phase_proj in roadmap.ats_projection['by_phase']:
        print(f"  - Phase {phase_proj['phase']}: {phase_proj['score']}%")

    print(f"\nRoadmap Phases: {len(roadmap.phases)}")
    for phase in roadmap.phases:
        print(f"\n  Phase {phase['phase_id']}: {phase['title']}")
        print(f"  Duration: {phase['duration_weeks']} weeks")
        print(f"  Expected readiness: {phase['expected_ats']}%")
        print(f"  Skills: {', '.join(phase['skills'])}")

        # Check project mapping
        phase_str = str(phase['phase_id'])
        if phase_str in roadmap.project_mapping:
            proj = roadmap.project_mapping[phase_str]
            print(f"  Project: {proj['name']} (Difficulty: {proj['difficulty']})")
            print(f"    Skills used: {', '.join(proj['skills_used'])}")

    # Export to JSON
    output_file = Path(__file__).parent / "test_roadmap_output.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(roadmap.to_dict(), f, indent=2, ensure_ascii=False)

    print(f"\n[OK] Full roadmap contract exported to: {output_file}")

    return roadmap


def main():
    """Run all tests."""
    print("="*70)
    print("ROADMAP MODULE TEST SUITE")
    print("="*70)

    # Load CV
    cv_data = load_real_cv()
    if cv_data is None:
        return

    # Test 1: Stage Detector
    try:
        stage_result = test_stage_detector(cv_data)
        print("\n[OK] Stage Detector test passed")
    except Exception as e:
        print(f"\n[FAIL] Stage Detector test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 2: Project Pool
    try:
        pool = test_project_pool()
        print("\n[OK] Project Pool test passed")
    except Exception as e:
        print(f"\n[FAIL] Project Pool test failed: {e}")
        import traceback
        traceback.print_exc()

    # Test 3: Full Roadmap
    try:
        roadmap = test_full_roadmap(cv_data)
        print("\n[OK] Full Roadmap test passed")
    except Exception as e:
        print(f"\n[FAIL] Full Roadmap test failed: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*70)
    print("TEST SUITE COMPLETE")
    print("="*70)


if __name__ == "__main__":
    main()