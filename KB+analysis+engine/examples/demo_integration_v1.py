"""
Demo script for Skill Graph Integration V1
Tests the full pipeline with graph_insights in output
"""
import json
from skill_gap_engine import SkillGapEngine
from feedback_generator import FeedbackGenerator

def main():
    print("=" * 70)
    print("SKILL GAP ANALYSIS - INTEGRATION V1 DEMO")
    print("=" * 70)

    # Step 1: Analyze CV with Skill Gap Engine
    print("\n[STEP 1] Analyzing CV with Skill Gap Engine...")
    engine = SkillGapEngine()

    analysis = engine.analyze(
        resume_skills=["Python", "PyTorch", "Computer Vision"],
        target_role="AI Engineer"
    )

    print(f"[OK] Readiness: {analysis['readiness_score']}%")
    print(f"[OK] Strengths: {len(analysis['strengths'])}")
    print(f"[OK] Critical gaps: {len(analysis['critical_gaps'])}")
    print(f"[OK] Medium gaps: {len(analysis['medium_gaps'])}")

    # Step 2: Check graph_insights
    print("\n[STEP 2] Checking graph_insights...")
    if "graph_insights" in analysis:
        insights = analysis["graph_insights"]
        print(f"[OK] Target skills: {insights['target_skills']}")
        print(f"[OK] Skills with missing prerequisites: {len(insights['missing_prerequisites'])}")
        print(f"[OK] Recommended learning order: {len(insights['recommended_learning_order'])} skills")

        # Save detailed graph insights to file (avoid console encoding issues)
        with open("graph_insights_detail.json", "w", encoding="utf-8") as f:
            json.dump(insights, f, indent=2, ensure_ascii=False)
        print("[OK] Detailed graph insights saved to graph_insights_detail.json")
    else:
        print("[WARNING] graph_insights not found in analysis")

    # Step 3: Generate LLM prompt
    print("\n[STEP 3] Building LLM prompt...")
    generator = FeedbackGenerator()
    prompt = generator.generate_prompt(analysis)

    print(f"[OK] Prompt length: {len(prompt)} characters")

    # Step 4: Save clean analysis data (what LLM sees) to file
    print("\n[STEP 4] Saving clean analysis data (what LLM sees)...")
    clean_data = generator._prepare_clean_analysis(generator._enrich_with_metadata(analysis))
    with open("integration_v1_clean_data.json", "w", encoding="utf-8") as f:
        json.dump(clean_data, f, indent=2, ensure_ascii=False)
    print("[OK] Saved to integration_v1_clean_data.json")

    # Step 5: Save full output
    print("\n[STEP 5] Saving full analysis to file...")
    with open("integration_v1_output.json", "w", encoding="utf-8") as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    print("[OK] Saved to integration_v1_output.json")

    print("\n" + "=" * 70)
    print("INTEGRATION V1 DEMO COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
