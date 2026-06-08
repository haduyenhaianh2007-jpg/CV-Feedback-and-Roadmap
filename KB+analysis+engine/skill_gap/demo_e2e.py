"""
End-to-end demo: CV -> Skill Gap Engine -> Local LLM -> Feedback Report
With automatic evaluation metrics
"""
import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import json
from skill_gap_engine import SkillGapEngine
from feedback_generator import FeedbackGenerator
from local_llm import LocalLLMClient
from feedback_evaluator import FeedbackEvaluator


def demo():
    print("=" * 70)
    print("SKILL GAP ANALYSIS - END-TO-END DEMO")
    print("=" * 70)
    print()

    # Step 1: Check LLM is ready
    print("[STEP 1] Checking local LLM...")
    client = LocalLLMClient()
    if not client.is_ready():
        print(client.diagnose())
        print("\n[ABORT] Local LLM not ready. Please start Ollama first.")
        return
    print("[OK] Local LLM is ready (Qwen2.5)")
    print()

    # Step 2: Analyze CV
    print("[STEP 2] Analyzing CV with Skill Gap Engine...")
    engine = SkillGapEngine()
    analysis = engine.analyze(
        resume_skills=["Python", "PyTorch", "Computer Vision"],
        target_role="AI Engineer"
    )
    print(f"[OK] Readiness: {analysis['readiness_score']}%")
    print(f"[OK] Strengths: {len(analysis['strengths'])}")
    print(f"[OK] Gaps: {len(analysis['medium_gaps'])} medium, {len(analysis['critical_gaps'])} critical")
    print()

    # Step 3: Generate prompt
    print("[STEP 3] Building LLM prompt...")
    generator = FeedbackGenerator()
    prompt = generator.generate_prompt(analysis)
    print(f"[OK] Prompt length: {len(prompt)} characters")
    print()

    # Extract source JSON for evaluation
    json_start = prompt.find('{')
    json_end = prompt.rfind('}') + 1
    source_json_str = prompt[json_start:json_end]
    source_json = json.loads(source_json_str)

    # Step 4: Call Local LLM
    print("[STEP 4] Calling Qwen2.5 to generate feedback...")
    print("-" * 70)
    print()
    feedback = client.generate(prompt)
    print(feedback)
    print()
    print("-" * 70)
    print()

    # Step 5: Automatic Evaluation
    print("[STEP 5] Running automatic evaluation...")
    print("-" * 70)
    evaluator = FeedbackEvaluator()
    result = evaluator.evaluate(source_json, feedback)

    print(f"\n📊 EVALUATION RESULTS:")
    print(f"  • Hallucination Rate: {result['hallucination_rate']:.2%}")
    if result['hallucinated_skills']:
        print(f"    Hallucinated: {', '.join(result['hallucinated_skills'])}")
    else:
        print(f"    ✅ No hallucinated skills detected")

    print(f"\n  • Severity Drift: {result['severity_drift']}")
    if result['severity_issues']:
        for issue in result['severity_issues']:
            print(f"    ⚠️  {issue}")
    else:
        print(f"    ✅ All gaps correctly classified")

    print(f"\n  • Number Drift: {result['number_drift_count']} issues")
    if result['number_drifts']:
        for drift in result['number_drifts'][:3]:  # Show first 3
            print(f"    ⚠️  Feedback: {drift['feedback_value']}% vs Expected: {drift['closest_expected']}%")
    else:
        print(f"    ✅ All numbers match source JSON")

    print(f"\n  • Missing Skills: {len(result['missing_skills'])}")
    if result['missing_skills']:
        print(f"    (Skills in JSON but not mentioned in feedback: {', '.join(result['missing_skills'][:5])})")

    print(f"\n  • Overall Score: {result['overall_score']:.2f} / 1.00")
    print("-" * 70)
    print(f"\n[DONE] Feedback generated ({len(feedback)} characters)")


if __name__ == "__main__":
    demo()
