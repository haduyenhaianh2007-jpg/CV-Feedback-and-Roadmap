"""
Test Integration V1 with real CV data
"""
import json
import sys
import io
from pathlib import Path
from skill_gap_engine import SkillGapEngine
from feedback_generator import FeedbackGenerator

# Fix console encoding
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def main():
    print("=" * 70)
    print("TESTING WITH REAL CV - Ha Duyen Hai Anh")
    print("=" * 70)

    # Load CV data
    cv_path = Path(r"C:\CV feedback and roadmap\CV extraction\examples\sample_output.json")
    with open(cv_path, 'r', encoding='utf-8') as f:
        cv_data = json.load(f)

    # Extract skills from CV
    resume_skills = cv_data['career_profile']['skills']

    print(f"\n[CV INFO]")
    print(f"Name: {cv_data['structured_data']['personal_info'][0]}")
    print(f"Current Role: {cv_data['career_profile']['current_role']}")
    print(f"Career Stage: {cv_data['career_profile']['career_stage']}")
    print(f"Total Skills: {len(resume_skills)}")
    print(f"\n[SKILLS FROM CV]")
    for i, skill in enumerate(resume_skills, 1):
        print(f"  {i}. {skill}")

    # Step 1: Analyze with Skill Gap Engine
    print("\n" + "=" * 70)
    print("[STEP 1] Analyzing CV with Skill Gap Engine...")
    print("=" * 70)

    engine = SkillGapEngine()
    target_role = "AI Engineer"

    try:
        analysis = engine.analyze(
            resume_skills=resume_skills,
            target_role=target_role
        )

        print(f"\n[OK] Readiness Score: {analysis['readiness_score']}%")
        print(f"[OK] Strengths: {len(analysis['strengths'])}")
        print(f"[OK] Critical gaps: {len(analysis['critical_gaps'])}")
        print(f"[OK] Medium gaps: {len(analysis['medium_gaps'])}")
        print(f"[OK] Optional gaps: {len(analysis['optional_gaps'])}")

        # Check unknown skills
        if analysis['unknown_skills']:
            print(f"\n[WARNING] {len(analysis['unknown_skills'])} skills not in ontology:")
            for skill in analysis['unknown_skills']:
                print(f"  - {skill}")

        # Step 2: Check graph_insights
        print("\n" + "=" * 70)
        print("[STEP 2] Checking Graph Insights...")
        print("=" * 70)

        if "graph_insights" in analysis:
            insights = analysis["graph_insights"]

            # Dimension 1: Missing skills (critical/medium gaps)
            missing = insights.get("missing_skills", {})
            print(f"\n[OK] Missing target skills: {len(missing.get('target_skills', []))}")
            print(f"[OK] Skills with missing prerequisites: {len(missing.get('missing_prerequisites', {}))}")

            # Dimension 2: Deepen skills (owned strengths -> advanced)
            deepen = insights.get("deepen_skills", {})
            print(f"[OK] Strong skills (frequency >= 50%): {len(deepen.get('current_strengths', []))}")
            print(f"[OK] Recommended next skills: {len(deepen.get('recommended_next', []))}")

            # Dimension 3: Expand skills (high-frequency optionals)
            expand = insights.get("expand_skills", {})
            print(f"[OK] High-frequency optional targets: {len(expand.get('target_skills', []))}")
            print(f"[OK] Expand prerequisites missing: {len(expand.get('missing_prerequisites', {}))}")

            # Overall learning order
            print(f"[OK] Recommended learning order: {len(insights.get('recommended_learning_order', []))} steps")

            # Save detailed graph insights
            with open("real_cv_graph_insights.json", "w", encoding="utf-8") as f:
                json.dump(insights, f, indent=2, ensure_ascii=False)
            print("[OK] Detailed graph insights saved to real_cv_graph_insights.json")

        # Step 3: Generate LLM prompt
        print("\n" + "=" * 70)
        print("[STEP 3] Building LLM Prompt...")
        print("=" * 70)

        generator = FeedbackGenerator()
        prompt = generator.generate_prompt(analysis)

        print(f"\n[OK] Prompt length: {len(prompt)} characters")

        # Save prompt to file
        with open("real_cv_prompt.txt", "w", encoding="utf-8") as f:
            f.write(prompt)
        print("[OK] Prompt saved to real_cv_prompt.txt")

        # Save clean analysis data
        clean_data = generator._prepare_clean_analysis(generator._enrich_with_metadata(analysis))
        with open("real_cv_clean_data.json", "w", encoding="utf-8") as f:
            json.dump(clean_data, f, indent=2, ensure_ascii=False)
        print("[OK] Clean analysis data saved to real_cv_clean_data.json")

        # Save full analysis
        with open("real_cv_full_analysis.json", "w", encoding="utf-8") as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        print("[OK] Full analysis saved to real_cv_full_analysis.json")

        # Step 4: Generate feedback with local LLM
        print("\n" + "=" * 70)
        print("[STEP 4] Generating Feedback with Local LLM...")
        print("=" * 70)

        try:
            import subprocess

            # Check if ollama is available
            ollama_check = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if ollama_check.returncode == 0:
                print("\n[OK] Ollama is available, generating feedback...")

                # Run ollama generate
                result = subprocess.run(
                    ["ollama", "run", "qwen2.5:14b"],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=180
                )

                if result.returncode == 0 and result.stdout:
                    print("\n" + "=" * 70)
                    print("LLM FEEDBACK (with Graph Insights):")
                    print("=" * 70)
                    print(result.stdout)
                    print("=" * 70)

                    # Save feedback
                    with open("real_cv_feedback.md", "w", encoding="utf-8") as f:
                        f.write(result.stdout)
                    print("\n[OK] Feedback saved to real_cv_feedback.md")
                else:
                    print("[WARNING] LLM generation failed or returned empty")
                    if result.stderr:
                        print(f"Error: {result.stderr[:300]}")
            else:
                print("[SKIP] Ollama not available")
                print("[INFO] Prompt saved to real_cv_prompt.txt for manual testing")

        except Exception as e:
            print(f"[SKIP] Could not run LLM: {e}")
            print("[INFO] Prompt saved to real_cv_prompt.txt for manual testing")

        print("\n" + "=" * 70)
        print("REAL CV TEST COMPLETE")
        print("=" * 70)

    except Exception as e:
        print(f"\n[ERROR] Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
