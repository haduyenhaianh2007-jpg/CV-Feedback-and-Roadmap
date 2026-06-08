"""
LLM Feedback Generator Module
Transforms structured skill gap analysis into natural language career advice.

Two modes:
1. generate_prompt() - Returns formatted prompt string (user sends to their LLM)
2. generate_feedback() - Optional: Calls Claude API directly if ANTHROPIC_API_KEY is set
"""
import json
import os
from pathlib import Path
from typing import Dict, List, Optional


class FeedbackGenerator:
    """
    Generates natural language career advice from structured skill gap analysis.
    Enriches the prompt with skill metadata for more contextual feedback.
    """

    def __init__(self, metadata_path: Optional[str] = None, prompt_template_path: Optional[str] = None):
        if metadata_path is None:
            metadata_path = Path(__file__).parent / "skill_metadata.json"
        if prompt_template_path is None:
            prompt_template_path = Path(__file__).parent / "prompts" / "skill_gap_feedback.txt"

        # Load skill metadata
        with open(metadata_path, 'r', encoding='utf-8') as f:
            self.metadata = json.load(f)

        # Load prompt template
        with open(prompt_template_path, 'r', encoding='utf-8') as f:
            self.prompt_template = f.read()

    def _enrich_with_metadata(self, analysis: Dict) -> Dict:
        """
        Add skill metadata (category, description) to the analysis for richer LLM context.
        """
        enriched = analysis.copy()

        # Enrich strengths
        if "strengths" in enriched:
            for item in enriched["strengths"]:
                skill = item["skill"]
                if skill in self.metadata:
                    item["category"] = self.metadata[skill]["category"]
                    item["description"] = self.metadata[skill]["description"]

        # Enrich gaps
        for gap_type in ["critical_gaps", "medium_gaps"]:
            if gap_type in enriched:
                for item in enriched[gap_type]:
                    skill = item["skill"]
                    if skill in self.metadata:
                        item["category"] = self.metadata[skill]["category"]
                        item["description"] = self.metadata[skill]["description"]

        # Enrich improvement actions
        if "improvement_actions" in enriched:
            for item in enriched["improvement_actions"]:
                skill = item["skill"]
                if skill in self.metadata:
                    item["category"] = self.metadata[skill]["category"]
                    item["description"] = self.metadata[skill]["description"]
                    item["importance_reason"] = self.metadata[skill]["importance_reason"]

        return enriched

    def _prepare_clean_analysis(self, analysis: Dict) -> Dict:
        """
        Prepare a clean version of the analysis with Vietnamese keys,
        only containing data that should appear in the LLM prompt.

        This implements the architecture insight:
        - Data layer uses final language (Vietnamese)
        - Only pass data that should be mentioned in output
        - Remove optional_gaps (to prevent hallucination)
        """
        # Priority translation map
        priority_map = {
            "High": "Cao",
            "Medium": "Trung bình",
            "Low": "Thấp"
        }

        # Start with a clean dict
        clean = {}

        # Core fields - translate keys to Vietnamese
        clean["vai_trò_mục_tiêu"] = analysis.get("target_role", "")
        clean["điểm_sẵn_sàng"] = analysis.get("readiness_score", 0)

        # Readiness breakdown - Vietnamese keys
        breakdown = analysis.get("readiness_breakdown", {})
        clean["phân_tích_chi_tiết"] = {
            "tổng_trọng_số_kỹ_năng_hiện_có": breakdown.get("owned_weight", 0),
            "tổng_trọng_số_kỹ_năng_yêu_cầu": breakdown.get("total_weight", 0),
            "số_kỹ_năng_đang_có": breakdown.get("owned_skills_count", 0),
            "tổng_số_kỹ_năng_thị_trường": breakdown.get("total_skills_count", 0),
        }

        # Strengths - keep as is, enrich with metadata
        if "strengths" in analysis:
            clean["điểm_mạnh"] = analysis["strengths"]

        # Critical gaps - only if non-empty
        if analysis.get("critical_gaps"):
            clean["khoảng_trống_quan_trọng"] = analysis["critical_gaps"]

        # Medium gaps - only if non-empty
        if analysis.get("medium_gaps"):
            clean["khoảng_trống_trung_bình"] = analysis["medium_gaps"]

        # Improvement actions - convert to Vietnamese keys and translate priority
        if "improvement_actions" in analysis:
            clean_actions = []
            for action in analysis["improvement_actions"]:
                clean_action = {
                    "kỹ_năng": action.get("skill", ""),
                    "mức_độ_ưu_tiên": priority_map.get(action.get("priority", ""), action.get("priority", "")),
                    "tần_suất": action.get("frequency", 0),
                    "lý_do": action.get("reason", ""),
                    "hành_động": action.get("actions", [])
                }
                clean_actions.append(clean_action)
            clean["hành_động_cải_thiện"] = clean_actions

        # Graph insights - pass full 3-dimensional structure for deep analysis
        if "graph_insights" in analysis:
            insights = analysis["graph_insights"]
            # Only include if there are meaningful insights
            if (insights.get("missing_skills", {}).get("target_skills") or
                insights.get("deepen_skills", {}).get("recommended_next") or
                insights.get("expand_skills", {}).get("target_skills")):
                clean["thông_tin_lộ_trình_học"] = {
                    # Dimension 1: Missing skills and prerequisites
                    "kỹ_năng_còn_thiếu": {
                        "danh_sách": insights.get("missing_skills", {}).get("target_skills", []),
                        "kiến_thức_nền_tảng_cần_bổ_sung": insights.get("missing_skills", {}).get("missing_prerequisites", {})
                    },
                    # Dimension 2: Deepen existing strengths
                    "nâng_cao_kỹ_năng_đang_có": {
                        "kỹ_năng_mạnh_hiện_tại": insights.get("deepen_skills", {}).get("current_strengths", []),
                        "các_bước_nâng_cao_tiếp_theo": [
                            {
                                "kỹ_năng": item["skill"],
                                "lý_do": item["reason"],
                                "từ_kỹ_năng": item["source_skill"],
                                "tần_suất_nguồn": item.get("source_frequency", 0)
                            }
                            for item in insights.get("deepen_skills", {}).get("recommended_next", [])
                        ]
                    },
                    # Dimension 3: Expand to adjacent skills
                    "mở_rộng_sang_kỹ_năng_liên_quan": {
                        "kỹ_năng_mục_tiêu": insights.get("expand_skills", {}).get("target_skills", []),
                        "kiến_thức_nền_tảng_cần_thiết": insights.get("expand_skills", {}).get("missing_prerequisites", {})
                    },
                    # Learning order (merged from all 3 dimensions)
                    "trình_tự_học_tập_được_đề_xuất": insights.get("recommended_learning_order", [])
                }

        # NOTE: We deliberately exclude:
        # - optional_gaps (to prevent LLM from mentioning them as "extra skills")
        # - resume_skills_raw (internal data, not needed in prompt)
        # - unknown_skills (internal data, not needed in prompt)

        return clean

    def generate_prompt(self, analysis: Dict) -> str:
        """
        Generate a formatted prompt string ready to send to LLM.

        Args:
            analysis: Structured analysis dict from SkillGapEngine

        Returns:
            Formatted prompt string with enriched context
        """
        # Enrich with metadata first
        enriched = self._enrich_with_metadata(analysis)

        # Prepare clean version with Vietnamese keys
        clean = self._prepare_clean_analysis(enriched)

        # Format as JSON
        analysis_json = json.dumps(clean, indent=2, ensure_ascii=False)

        # Substitute into template
        prompt = self.prompt_template.replace("{structured_analysis}", analysis_json)

        return prompt

    def generate_feedback(
        self,
        analysis: Dict,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-6",
        max_tokens: int = 2000
    ) -> str:
        """
        Optional: Call Claude API directly to generate feedback.

        Requires ANTHROPIC_API_KEY environment variable or api_key parameter.

        Args:
            analysis: Structured analysis dict from SkillGapEngine
            api_key: Anthropic API key (defaults to env var)
            model: Claude model to use
            max_tokens: Maximum response length

        Returns:
            Generated feedback text in Vietnamese

        Raises:
            ImportError: If anthropic package not installed
            ValueError: If no API key provided
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic package not installed. "
                "Install with: pip install anthropic"
            )

        if api_key is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "No API key provided. Set ANTHROPIC_API_KEY environment variable "
                    "or pass api_key parameter."
                )

        prompt = self.generate_prompt(analysis)

        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        return message.content[0].text


if __name__ == "__main__":
    # Force UTF-8 encoding for Windows console
    import sys
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    # Demo: Generate prompt for the example analysis
    from skill_gap_engine import SkillGapEngine

    engine = SkillGapEngine()
    analysis = engine.analyze(
        resume_skills=["Python", "PyTorch", "Computer Vision"],
        target_role="AI Engineer"
    )

    generator = FeedbackGenerator()
    prompt = generator.generate_prompt(analysis)

    print("=" * 80)
    print("GENERATED PROMPT (ready to send to LLM)")
    print("=" * 80)
    print(prompt)
    print("=" * 80)
    print(f"\nPrompt length: {len(prompt)} characters")
    print(f"\nTo generate feedback via Claude API:")
    print(f"  feedback = generator.generate_feedback(analysis)")
    print(f"  print(feedback)")
