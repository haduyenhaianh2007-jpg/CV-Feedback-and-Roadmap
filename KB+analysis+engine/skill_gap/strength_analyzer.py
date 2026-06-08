"""
Strength Analysis Module
Finds skills the CV owns that are valuable for the target role.
"""
from typing import List, Dict


class StrengthAnalyzer:
    """
    Analyzes skills present in CV that match role requirements.

    Level classification (threshold-based):
    - Core: frequency >= 50% (appears in 50%+ of JDs for this role)
    - Important: 20% <= frequency < 50%
    - Bonus: frequency < 20% (still present in some JDs)
    """

    CORE_THRESHOLD = 50
    IMPORTANT_THRESHOLD = 20

    def analyze(
        self,
        resume_skills: List[str],
        role_matrix: List[Dict],
        extra_skills: List[str] = None
    ) -> Dict:
        """
        Args:
            resume_skills: canonical skill names from CV (matched in KB)
            role_matrix: list of {skill, frequency} dicts for target role
            extra_skills: canonical skills from CV not in role matrix (valuable but not core to role)

        Returns:
            {
                "strengths": [...],
                "extra_skills": [...]
            }
        """
        resume_set = set(s.lower() for s in resume_skills)

        # Build role skill lookup (case-insensitive)
        role_lookup = {
            item["skill"].lower(): item
            for item in role_matrix
        }

        strengths = []
        for skill in resume_skills:
            skill_lower = skill.lower()
            if skill_lower in role_lookup:
                item = role_lookup[skill_lower]
                freq = item["frequency"]

                strengths.append({
                    "skill": item["skill"],
                    "frequency": freq,
                    "level": self._classify_level(freq)
                })

        # Sort by frequency descending (most valuable strengths first)
        strengths.sort(key=lambda x: x["frequency"], reverse=True)

        result = {"strengths": strengths}

        if extra_skills:
            result["extra_skills"] = [
                {"skill": s, "status": "extra_skill"} for s in extra_skills
            ]

        return result

    def _classify_level(self, frequency: float) -> str:
        if frequency >= self.CORE_THRESHOLD:
            return "Core"
        elif frequency >= self.IMPORTANT_THRESHOLD:
            return "Important"
        else:
            return "Bonus"
