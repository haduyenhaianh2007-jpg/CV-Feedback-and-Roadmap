"""
Automatic Feedback Evaluator
Đánh giá chất lượng feedback từ LLM dựa trên source JSON.

Metrics:
- Hallucination Rate: skills được nhắc trong feedback nhưng không có trong JSON
- Severity Drift: gaps bị reclassify (medium → critical, v.v.)
- Number Drift: số liệu bị thay đổi so với JSON

Cách dùng:
    evaluator = FeedbackEvaluator()
    result = evaluator.evaluate(source_json, llm_feedback)
    print(result["hallucination_rate"])  # 0.0 - 1.0
    print(result["number_drift_count"])  # int
"""
import re
from typing import Dict, List, Set, Tuple


class FeedbackEvaluator:
    """
    Rule-based evaluator for LLM-generated feedback.
    Compares output against source JSON to detect hallucinations and drifts.
    """

    # Vietnamese section headers in the feedback
    SECTION_HEADERS = {
        "tổng quan": "overview",
        "điểm mạnh": "strengths",
        "khoảng trống quan trọng": "critical_gaps",
        "khoảng trống trung bình": "medium_gaps",
        "đánh giá mức độ sẵn sàng": "readiness",
        "kế hoạch cải thiện": "improvement",
    }

    def __init__(self):
        pass

    def evaluate(self, source_json: Dict, feedback_text: str) -> Dict:
        """
        Evaluate LLM feedback against source JSON.

        Args:
            source_json: The structured analysis JSON sent to LLM
            feedback_text: The LLM-generated feedback text

        Returns:
            {
                "hallucination_rate": float,  # 0.0 - 1.0
                "hallucinated_skills": list,
                "missing_skills": list,
                "severity_drift": bool,
                "number_drift_count": int,
                "number_drifts": list,
                "overall_score": float,  # 0.0 - 1.0 (higher = better)
            }
        """
        # Extract skills from source JSON
        source_skills = self._extract_source_skills(source_json)

        # Extract skills from feedback
        feedback_skills = self._extract_feedback_skills(feedback_text)

        # Calculate hallucination
        hallucinated = feedback_skills - source_skills
        missing = source_skills - feedback_skills

        hallucination_rate = (
            len(hallucinated) / len(feedback_skills)
            if feedback_skills
            else 0.0
        )

        # Check severity drift
        severity_drift, severity_issues = self._check_severity_drift(
            source_json, feedback_text
        )

        # Check number drift
        number_drifts = self._check_number_drift(source_json, feedback_text)

        # Calculate overall score
        overall_score = self._calculate_overall_score(
            hallucination_rate,
            severity_drift,
            len(number_drifts),
            len(missing),
        )

        return {
            "hallucination_rate": hallucination_rate,
            "hallucinated_skills": sorted(hallucinated),
            "missing_skills": sorted(missing),
            "severity_drift": severity_drift,
            "severity_issues": severity_issues,
            "number_drift_count": len(number_drifts),
            "number_drifts": number_drifts,
            "overall_score": overall_score,
        }

    def _extract_source_skills(self, source_json: Dict) -> Set[str]:
        """Extract all skills mentioned in source JSON."""
        skills = set()

        # Strengths
        for item in source_json.get("điểm_mạnh", []):
            if "skill" in item:
                skills.add(item["skill"])

        # Critical gaps
        for item in source_json.get("khoảng_trống_quan_trọng", []):
            if "skill" in item:
                skills.add(item["skill"])

        # Medium gaps
        for item in source_json.get("khoảng_trống_trung_bình", []):
            if "skill" in item:
                skills.add(item["skill"])

        # Improvement actions
        for item in source_json.get("hành_động_cải_thiện", []):
            if "kỹ_năng" in item:
                skills.add(item["kỹ_năng"])

        # Graph insights — skills from all 3 dimensions
        graph_insights = source_json.get("thông_tin_lộ_trình_học", {})
        if graph_insights:
            # Dimension 1: Missing skills
            missing = graph_insights.get("kỹ_năng_còn_thiếu", {})
            for skill in missing.get("danh_sách", []):
                skills.add(skill)
            for prereqs in missing.get("kiến_thức_nền_tảng_cần_bổ_sung", {}).values():
                for prereq in prereqs:
                    skills.add(prereq)

            # Dimension 2: Deepen skills
            deepen = graph_insights.get("nâng_cao_kỹ_năng_đang_có", {})
            for skill in deepen.get("kỹ_năng_mạnh_hiện_tại", []):
                skills.add(skill)
            for item in deepen.get("các_bước_nâng_cao_tiếp_theo", []):
                if item.get("kỹ_năng"):
                    skills.add(item["kỹ_năng"])
                if item.get("từ_kỹ_năng"):
                    skills.add(item["từ_kỹ_năng"])

            # Dimension 3: Expand skills
            expand = graph_insights.get("mở_rộng_sang_kỹ_năng_liên_quan", {})
            for skill in expand.get("kỹ_năng_mục_tiêu", []):
                skills.add(skill)
            for prereqs in expand.get("kiến_thức_nền_tảng_cần_thiết", {}).values():
                for prereq in prereqs:
                    skills.add(prereq)

            # Learning order
            for item in graph_insights.get("trình_tự_học_tập_được_đề_xuất", []):
                if isinstance(item, dict):
                    if item.get("kỹ_năng"):
                        skills.add(item["kỹ_năng"])
                elif isinstance(item, str):
                    skills.add(item)

        # Remove empty strings
        skills.discard("")
        return skills

    def _extract_feedback_skills(self, feedback_text: str) -> Set[str]:
        """Extract skills mentioned in feedback text using regex patterns."""
        skills = set()

        # Helper: clean a raw match by stripping trailing metadata like
        # " (64.29%)", " (Cao)", ": ...", etc.
        def clean_skill_name(raw: str) -> str:
            # Remove trailing parenthesized groups: (64.29%), (Cao), (Trung bình)
            cleaned = re.sub(r'\s*\([^)]*\)\s*$', '', raw)
            # Remove trailing colon + text
            cleaned = re.sub(r'\s*[::].*$', '', cleaned)
            # Remove trailing comma / dash
            cleaned = re.sub(r'\s*[-,]\s*$', '', cleaned)
            return cleaned.strip()

        # Pattern 1: Bold skills — **Python**, **Python (64.29%)**, **LLM (57.14%, Cao)**
        bold_pattern = r'\*\*([^*]+)\*\*'
        for raw in re.findall(bold_pattern, feedback_text):
            name = clean_skill_name(raw)
            if name and self._is_likely_skill(name):
                skills.add(name)

        # Pattern 2: Skill followed by percentage — "Python (64.29%)"
        pct_pattern = r'([A-Za-z][A-Za-z0-9\s\-\+\.\/]+?)\s*\(\d+[\.,]?\d*\s*%[^)]*\)'
        for raw in re.findall(pct_pattern, feedback_text):
            name = clean_skill_name(raw)
            if name and self._is_likely_skill(name):
                skills.add(name)

        # Pattern 3: Skills in bullet points — "- Python: ..." or "- Python (64%)"
        bullet_pattern = r'^\s*[-*]\s+([A-Za-z][A-Za-z0-9\s\-\+\.\/\(\)%]+?)(?=\s*[:：\-—]|$)'
        for raw in re.findall(bullet_pattern, feedback_text, re.MULTILINE):
            name = clean_skill_name(raw)
            if name and self._is_likely_skill(name):
                skills.add(name)

        return skills

    def _is_likely_skill(self, text: str) -> bool:
        """Heuristic to check if text looks like a skill name."""
        # Filter out obvious non-skills
        non_skill_keywords = [
            "tổng quan", "điểm mạnh", "khoảng trống", "kế hoạch",
            "đánh giá", "mức độ", "sẵn sàng", "quan trọng", "trung bình",
            "cao", "thấp", "tại sao", "hành động", "lý do",
            "ví dụ", "như", "và", "hoặc", "nhưng", "nếu",
            "bạn", "của", "trong", "ngoài", "với", "cho",
        ]

        text_lower = text.lower().strip()

        # Too long = probably a sentence, not a skill
        if len(text_lower) > 40:
            return False

        # Contains non-skill keywords
        if any(kw in text_lower for kw in non_skill_keywords):
            return False

        # Starts with number = probably not a skill
        if text_lower[0].isdigit():
            return False

        return True

    def _check_severity_drift(
        self, source_json: Dict, feedback_text: str
    ) -> Tuple[bool, List[str]]:
        """
        Check if gaps are reclassified in feedback.

        Returns:
            (has_drift, list_of_issues)
        """
        issues = []

        # Extract skills from each section in feedback
        feedback_sections = self._parse_feedback_sections(feedback_text)

        # Source data
        critical_skills = {
            item["skill"]
            for item in source_json.get("khoảng_trống_quan_trọng", [])
            if "skill" in item
        }

        medium_skills = {
            item["skill"]
            for item in source_json.get("khoảng_trống_trung_bình", [])
            if "skill" in item
        }

        # Check for drift
        # Medium gap mentioned in Critical section?
        feedback_critical = feedback_sections.get("critical_gaps", "")
        feedback_medium = feedback_sections.get("medium_gaps", "")

        for skill in medium_skills:
            if skill in feedback_critical and skill not in feedback_medium:
                issues.append(
                    f"Medium gap '{skill}' được nhắc ở section 'Quan trọng'"
                )

        for skill in critical_skills:
            if skill in feedback_medium and skill not in feedback_critical:
                issues.append(
                    f"Critical gap '{skill}' được nhắc ở section 'Trung bình'"
                )

        return len(issues) > 0, issues

    def _parse_feedback_sections(self, feedback_text: str) -> Dict[str, str]:
        """Parse feedback into sections based on headers."""
        sections = {}

        # Find section boundaries
        lines = feedback_text.split('\n')
        current_section = None
        section_content = []

        for line in lines:
            # Check if line is a header
            header_match = None
            for vi_header, en_key in self.SECTION_HEADERS.items():
                if vi_header in line.lower() and line.strip().startswith('#'):
                    header_match = en_key
                    break

            if header_match:
                # Save previous section
                if current_section:
                    sections[current_section] = '\n'.join(section_content)

                current_section = header_match
                section_content = []
            elif current_section:
                section_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = '\n'.join(section_content)

        return sections

    def _check_number_drift(
        self, source_json: Dict, feedback_text: str
    ) -> List[Dict]:
        """
        Check if numbers in feedback match source JSON.

        Returns list of drifts found.
        """
        drifts = []

        # Extract all percentages from feedback
        pct_pattern = r'(\d+[\.,]?\d*)\s*%'
        feedback_pcts = re.findall(pct_pattern, feedback_text)

        # Normalize: convert comma to dot
        feedback_pcts_normalized = [
            p.replace(',', '.') for p in feedback_pcts
        ]

        # Expected percentages from source
        expected_pcts = []

        # Readiness score
        readiness = source_json.get("điểm_sẵn_sàng", 0)
        expected_pcts.append(float(readiness))

        # Frequencies from gaps (English key: "frequency")
        for gap_type in ["khoảng_trống_quan_trọng", "khoảng_trống_trung_bình"]:
            for item in source_json.get(gap_type, []):
                if "frequency" in item:
                    expected_pcts.append(float(item["frequency"]))

        # Frequencies from strengths (English key: "frequency")
        for item in source_json.get("điểm_mạnh", []):
            if "frequency" in item:
                expected_pcts.append(float(item["frequency"]))

        # Frequencies from improvement actions (Vietnamese key: "tần_suất")
        for item in source_json.get("hành_động_cải_thiện", []):
            freq = item.get("tần_suất") or item.get("frequency")
            if freq is not None:
                expected_pcts.append(float(freq))

        # Frequencies from graph insights (source_frequency)
        graph_insights = source_json.get("thông_tin_lộ_trình_học", {})
        if graph_insights:
            # Deepen skills - source_frequency
            deepen = graph_insights.get("nâng_cao_kỹ_năng_đang_có", {})
            for item in deepen.get("các_bước_nâng_cao_tiếp_theo", []):
                freq = item.get("tần_suất_nguồn") or item.get("source_frequency")
                if freq is not None:
                    expected_pcts.append(float(freq))

        # Check if feedback percentages match expected
        for fpct in feedback_pcts_normalized:
            try:
                fpct_float = float(fpct)
                # Allow small rounding (±0.5)
                if not any(
                    abs(fpct_float - epct) < 0.5
                    for epct in expected_pcts
                ):
                    drifts.append({
                        "type": "percentage_drift",
                        "feedback_value": fpct,
                        "closest_expected": min(
                            expected_pcts,
                            key=lambda x: abs(x - fpct_float),
                            default=None
                        )
                    })
            except ValueError:
                pass

        return drifts

    def _calculate_overall_score(
        self,
        hallucination_rate: float,
        severity_drift: bool,
        number_drift_count: int,
        missing_skills_count: int,
    ) -> float:
        """
        Calculate overall score (0.0 - 1.0, higher = better).

        Penalties:
        - Hallucination: -0.3 per 10% rate
        - Severity drift: -0.2
        - Number drift: -0.1 per drift
        - Missing skills: -0.05 per skill
        """
        score = 1.0

        # Hallucination penalty
        score -= hallucination_rate * 3.0

        # Severity drift penalty
        if severity_drift:
            score -= 0.2

        # Number drift penalty
        score -= number_drift_count * 0.1

        # Missing skills penalty
        score -= missing_skills_count * 0.05

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))


if __name__ == "__main__":
    # Demo: evaluate a sample feedback
    from skill_gap_engine import SkillGapEngine
    from feedback_generator import FeedbackGenerator
    from local_llm import LocalLLMClient

    print("=" * 70)
    print("FEEDBACK EVALUATOR DEMO")
    print("=" * 70)

    # Generate analysis
    engine = SkillGapEngine()
    analysis = engine.analyze(
        resume_skills=["Python", "PyTorch", "Computer Vision"],
        target_role="AI Engineer"
    )

    # Prepare prompt (with Vietnamese keys)
    generator = FeedbackGenerator()
    prompt = generator.generate_prompt(analysis)

    # Extract the JSON part from prompt for evaluation
    import json
    json_start = prompt.find('{')
    json_end = prompt.rfind('}') + 1
    source_json_str = prompt[json_start:json_end]
    source_json = json.loads(source_json_str)

    evaluator = FeedbackEvaluator()

    print("\n[INFO] Source JSON extracted for evaluation")
    print(f"[INFO] Skills in source: {evaluator._extract_source_skills(source_json)}")

    # Simulate feedback (in real use, this comes from LLM)
    sample_feedback = """
## Tổng quan
Với điểm sẵn sàng 18%, bạn đã có nền tảng nhất định.

## Điểm mạnh
- **Python (64.29%)**: Ngôn ngữ lập trình đa dụng.
- **Computer Vision (50.0%)**: Lĩnh vực AI xử lý hình ảnh.
- **PyTorch (21.43%)**: Framework ML.

## Khoảng trống quan trọng
Tin tốt: bạn không có khoảng trống nghiêm trọng.

## Khoảng trống trung bình
- **LLM (57.14%)**: Mô hình ngôn ngữ lớn.
- **RAG (57.14%)**: Kết hợp tra cứu và tạo nội dung.

## Đánh giá mức độ sẵn sàng
Điểm 18% cho thấy cần cải thiện nhiều.

## Kế hoạch cải thiện
- **LLM (57.14%, Cao)**: Học transformer.
"""

    result = evaluator.evaluate(source_json, sample_feedback)

    print("\n[RESULT] Evaluation:")
    print(f"  Hallucination Rate: {result['hallucination_rate']:.2%}")
    print(f"  Hallucinated Skills: {result['hallucinated_skills']}")
    print(f"  Missing Skills: {result['missing_skills']}")
    print(f"  Severity Drift: {result['severity_drift']}")
    print(f"  Number Drift Count: {result['number_drift_count']}")
    print(f"  Overall Score: {result['overall_score']:.2f}")
