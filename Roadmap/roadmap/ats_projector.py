"""
ATS Projector - Calculate projected ATS readiness scores

Simulates readiness scores after completing each roadmap phase by:
1. Accumulating skills from current + roadmap phases
2. Re-running SkillGapEngine with projected skill set
3. Returning readiness scores per phase
"""
from typing import Dict, List
from dataclasses import dataclass, field


@dataclass
class ATSProjection:
    """Projected ATS readiness scores across roadmap phases"""
    current: int
    phases: Dict[str, int] = field(default_factory=dict)
    final: int = 0
    improvement_delta: int = 0

    def to_dict(self) -> Dict:
        result = {
            "current": self.current,
            "final": self.final,
            "improvement_delta": self.improvement_delta
        }
        result.update(self.phases)
        return result


class ATSProjector:
    """
    Calculate projected ATS readiness scores.

    Uses SkillGapEngine to simulate readiness after each phase,
    ensuring consistency with actual readiness calculation logic.
    """

    def __init__(self, skill_gap_engine):
        """
        Initialize ATS projector.

        Args:
            skill_gap_engine: SkillGapEngine instance for readiness calculation
        """
        self.gap_engine = skill_gap_engine

    def project(
        self,
        current_skills: List[str],
        phases: List[Dict],
        target_role: str
    ) -> ATSProjection:
        """
        Project ATS readiness scores across roadmap phases.

        Args:
            current_skills: List of current skills (normalized)
            phases: List of roadmap phases, each with "skills" key
            target_role: Target job role

        Returns:
            ATSProjection with scores for current, each phase, and final
        """
        # Calculate current readiness
        current_readiness = self._calc_readiness(current_skills, target_role)

        # Project readiness after each phase
        accumulated_skills = set(current_skills)
        phase_scores = {}

        for i, phase in enumerate(phases, 1):
            # Add phase skills to accumulated set
            phase_skills = self._extract_phase_skills(phase)
            accumulated_skills.update(phase_skills)

            # Calculate readiness with accumulated skills
            phase_readiness = self._calc_readiness(
                list(accumulated_skills), target_role
            )

            phase_scores[f"phase_{i}"] = phase_readiness

        # Final readiness (after all phases)
        final_readiness = phase_scores.get(f"phase_{len(phases)}", current_readiness)
        improvement_delta = final_readiness - current_readiness

        return ATSProjection(
            current=current_readiness,
            phases=phase_scores,
            final=final_readiness,
            improvement_delta=improvement_delta
        )

    def _calc_readiness(self, skills: List[str], target_role: str) -> int:
        """
        Calculate readiness score for a given skill set.

        Reuses SkillGapEngine to ensure consistency with actual
        readiness calculation logic.

        Args:
            skills: List of skills
            target_role: Target job role

        Returns:
            Readiness score (0-100)
        """
        try:
            result = self.gap_engine.analyze(
                resume_skills=skills,
                target_role=target_role
            )
            return int(result["readiness_score"])
        except (ValueError, KeyError) as e:
            # Fallback: if role not found or error, return 0
            print(f"Warning: Could not calculate readiness: {e}")
            return 0

    def _extract_phase_skills(self, phase: Dict) -> List[str]:
        """
        Extract skill names from a phase.

        Handles both formats:
        - Simple list: ["SQL", "Machine Learning"]
        - Dict list: [{"skill": "SQL"}, {"skill": "Machine Learning"}]

        Args:
            phase: Phase dict with "skills" key

        Returns:
            List of skill names
        """
        skills = phase.get("skills", [])

        if not skills:
            return []

        # Check if skills are dicts or strings
        if isinstance(skills[0], dict):
            return [s.get("skill", "") for s in skills]
        else:
            return skills


if __name__ == "__main__":
    # Demo (requires SkillGapEngine)
    print("ATS Projector Demo")
    print("="*70)

    # Mock data for demonstration
    current_skills = ["Python", "PyTorch", "Computer Vision"]

    phases = [
        {
            "phase": 1,
            "skills": ["SQL", "Machine Learning"]
        },
        {
            "phase": 2,
            "skills": ["Deep Learning", "Natural Language Processing"]
        },
        {
            "phase": 3,
            "skills": ["LLM", "Prompt Engineering"]
        },
        {
            "phase": 4,
            "skills": ["RAG", "Docker", "AI Agent"]
        }
    ]

    print(f"Current skills: {current_skills}")
    print(f"Phases: {len(phases)}")
    print()

    # Note: This demo requires SkillGapEngine to be imported
    # Uncomment below to run with actual engine:
    # from skill_gap import SkillGapEngine
    # gap_engine = SkillGapEngine()
    # projector = ATSProjector(gap_engine)
    # projection = projector.project(current_skills, phases, "AI Engineer")
    # print(f"Projection: {projection.to_dict()}")

    print("Demo requires SkillGapEngine - see code comments")