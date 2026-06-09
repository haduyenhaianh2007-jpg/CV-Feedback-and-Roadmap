"""
ATS Projector V2 - Weighted + Penalty + Market-adjusted scoring

Formula:
ATS = Σ(skill_weight × mastery_level × market_factor) - dependency_penalty + synergy_bonus

Where:
- skill_weight: base weight from role matrix frequency
- mastery_level: 1.0 (completed), 0.5 (partial/in_progress), 0.0 (missing)
- market_factor: multiplier based on market demand (e.g., LLM=1.3, SQL=1.0)
- dependency_penalty: -15% if missing prerequisite for a skill
- synergy_bonus: small bonus for skills that naturally complement each other
"""
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field


@dataclass
class ATSProjectionV2:
    """Projected ATS readiness scores with detailed breakdown."""
    current: int
    phases: Dict[str, int] = field(default_factory=dict)
    final: int = 0
    improvement_delta: int = 0
    breakdown: Dict[str, Dict] = field(default_factory=dict)
    penalties: List[Dict] = field(default_factory=list)
    synergy_bonus: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "current": self.current,
            "final": self.final,
            "improvement_delta": self.improvement_delta,
            "phases": self.phases,
            "breakdown": self.breakdown,
            "penalties": self.penalties,
            "synergy_bonus": self.synergy_bonus
        }


class ATSProjectorV2:
    """
    Advanced ATS scoring engine with weighted scoring, mastery levels,
    dependency penalties, and market adjustment.
    """

    # Mastery level mapping
    MASTERY_LEVELS = {
        "completed": 1.0,
        "in_progress": 0.5,
        "partial": 0.5,
        "missing": 0.0
    }

    # Default market factors (can be overridden)
    DEFAULT_MARKET_FACTORS = {
        "LLM": 1.4,
        "RAG": 1.3,
        "LangChain": 1.3,
        "PyTorch": 1.2,
        "TensorFlow": 1.1,
        "Docker": 1.1,
        "Kubernetes": 1.2,
        "AWS": 1.15,
        "Python": 1.0,
        "SQL": 1.0,
        "Machine Learning": 1.1,
        "Deep Learning": 1.2,
        "Computer Vision": 1.0,
        "NLP": 1.1
    }

    def __init__(self, skill_gap_engine, skill_graph_engine, market_factors: Dict[str, float] = None):
        """
        Initialize ATS projector.

        Args:
            skill_gap_engine: SkillGapEngine instance for role matrix
            skill_graph_engine: SkillGraphEngine instance for prerequisites
            market_factors: Optional custom market factor overrides
        """
        self.gap_engine = skill_gap_engine
        self.graph_engine = skill_graph_engine
        self.market_factors = market_factors or self.DEFAULT_MARKET_FACTORS
        self.penalty_per_missing_prereq = 0.15  # 15% penalty per missing prerequisite chain
        self.synergy_bonus_cap = 0.10  # Max 10% synergy bonus

    def calculate_readiness(
        self,
        skills_with_status: Dict[str, str],
        target_role: str
    ) -> Dict:
        """
        Calculate ATS readiness score with full breakdown.

        Args:
            skills_with_status: Dict of skill_name -> status ("completed", "in_progress", "missing")
            target_role: Target job role

        Returns:
            Dict with score, breakdown, penalties, synergy
        """
        # Get role requirements
        role_entries = self.gap_engine.role_matrix.get(target_role, [])
        if not role_entries:
            return {"score": 0, "breakdown": {}, "penalties": [], "synergy_bonus": 0}

        # Build skill info dict
        skill_info = {item["skill"]: item for item in role_entries}

        total_weighted_score = 0.0
        total_weight = 0.0
        breakdown = {}
        penalties_applied = []

        # Calculate base weighted score
        for skill, info in skill_info.items():
            base_weight = info["frequency"] / 100.0  # Convert from percentage
            status = skills_with_status.get(skill, "missing")
            mastery = self.MASTERY_LEVELS.get(status, 0.0)
            market_factor = self.market_factors.get(skill, 1.0)

            weighted_contribution = base_weight * mastery * market_factor
            total_weighted_score += weighted_contribution
            total_weight += base_weight

            breakdown[skill] = {
                "base_weight": round(base_weight, 3),
                "mastery": mastery,
                "market_factor": market_factor,
                "contribution": round(weighted_contribution, 3),
                "status": status
            }

        # Calculate dependency penalties
        missing_skills = [s for s, status in skills_with_status.items() if status == "missing" and s in skill_info]
        for skill in missing_skills:
            prereqs = self.graph_engine.get_prerequisites(skill) if hasattr(self.graph_engine, 'get_prerequisites') else []
            missing_prereqs = [p for p in prereqs if skills_with_status.get(p, "missing") == "missing"]
            if missing_prereqs:
                penalty = self.penalty_per_missing_prereq * len(missing_prereqs)
                penalties_applied.append({
                    "skill": skill,
                    "missing_prerequisites": missing_prereqs,
                    "penalty": round(penalty, 3)
                })
                total_weighted_score *= (1 - min(penalty, 0.5))  # Cap penalty at 50%

        # Calculate synergy bonus (skills that work well together)
        synergy_bonus = self._calculate_synergy_bonus(skills_with_status, skill_info)

        # Final score
        raw_score = (total_weighted_score / total_weight) * 100 if total_weight > 0 else 0
        final_score = min(100, raw_score * (1 + synergy_bonus))

        return {
            "score": round(final_score),
            "raw_score": round(raw_score),
            "breakdown": breakdown,
            "penalties": penalties_applied,
            "synergy_bonus": round(synergy_bonus, 3),
            "total_weight": round(total_weight, 3),
            "total_weighted_score": round(total_weighted_score, 3)
        }

    def _calculate_synergy_bonus(self, skills_with_status: Dict[str, str], skill_info: Dict) -> float:
        """Calculate synergy bonus for complementary skill pairs."""
        completed = [s for s, status in skills_with_status.items() if status == "completed" and s in skill_info]

        # Define synergy pairs (skills that boost each other)
        synergy_pairs = [
            ("Python", "Machine Learning"),
            ("Python", "Deep Learning"),
            ("Machine Learning", "Deep Learning"),
            ("Deep Learning", "LLM"),
            ("LLM", "RAG"),
            ("Docker", "Kubernetes"),
            ("PyTorch", "Deep Learning"),
            ("SQL", "Data Processing")
        ]

        bonus = 0.0
        for skill1, skill2 in synergy_pairs:
            if skill1 in completed and skill2 in completed:
                bonus += 0.02  # 2% bonus per pair
            elif skill1 in completed and skill2 in skills_with_status.get(skill2, "missing") == "in_progress":
                bonus += 0.01

        return min(bonus, self.synergy_bonus_cap)

    def project_phases(
        self,
        current_skills: List[str],
        phases: List[Dict],
        target_role: str
    ) -> ATSProjectionV2:
        """
        Project ATS readiness across roadmap phases.

        Args:
            current_skills: List of current skills (normalized)
            phases: List of phases, each with "skills" key
            target_role: Target role

        Returns:
            ATSProjectionV2 with scores per phase
        """
        # Build initial skill status
        skill_status = {skill: "completed" for skill in current_skills}

        # Calculate current readiness
        current_result = self.calculate_readiness(skill_status, target_role)
        current_score = current_result["score"]

        # Project through phases
        accumulated_skills = set(current_skills)
        phase_scores = {}
        phase_breakdowns = {}

        for i, phase in enumerate(phases, 1):
            phase_skills = phase.get("skills", [])
            if isinstance(phase_skills[0], dict):
                phase_skills = [s["skill"] for s in phase_skills]

            # Add phase skills
            for skill in phase_skills:
                if skill not in accumulated_skills:
                    accumulated_skills.add(skill)
                    skill_status[skill] = "completed"

            # Calculate new readiness
            phase_result = self.calculate_readiness(skill_status, target_role)
            phase_scores[f"phase_{i}"] = phase_result["score"]
            phase_breakdowns[f"phase_{i}"] = phase_result

        final_score = phase_scores.get(f"phase_{len(phases)}", current_score) if phases else current_score
        improvement_delta = final_score - current_score

        return ATSProjectionV2(
            current=current_score,
            phases=phase_scores,
            final=final_score,
            improvement_delta=improvement_delta,
            breakdown=phase_breakdowns,
            penalties=current_result.get("penalties", []),
            synergy_bonus=current_result.get("synergy_bonus", 0)
        )


if __name__ == "__main__":
    print("ATSProjectorV2 module loaded")
