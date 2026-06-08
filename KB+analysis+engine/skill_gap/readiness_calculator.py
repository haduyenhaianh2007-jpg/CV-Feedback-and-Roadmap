"""
Readiness Calculator Module
Computes market readiness score: how well the CV matches the target role.
"""
from typing import List, Dict


class ReadinessCalculator:
    """
    Formula:
        readiness = owned_weight / total_weight * 100

    Where weight = frequency_pct from role_skill_matrix.
    Only counts skills that exist in both CV and role matrix.
    """

    def calculate(
        self,
        resume_skills: List[str],
        role_matrix: List[Dict]
    ) -> Dict:
        """
        Args:
            resume_skills: canonical skill names from CV
            role_matrix: list of {skill, frequency, ...} dicts for target role

        Returns:
            {
                "readiness_score": 40,          # integer 0-100
                "owned_weight": 147.0,
                "total_weight": 365.0,
                "owned_skills_count": 2,
                "total_skills_count": 5
            }
        """
        resume_set = set(s.lower() for s in resume_skills)

        total_weight = 0.0
        owned_weight = 0.0
        owned_count = 0

        for item in role_matrix:
            freq = item["frequency"]
            total_weight += freq

            if item["skill"].lower() in resume_set:
                owned_weight += freq
                owned_count += 1

        if total_weight == 0:
            score = 0
        else:
            score = round(owned_weight / total_weight * 100)

        return {
            "readiness_score": score,
            "owned_weight": round(owned_weight, 2),
            "total_weight": round(total_weight, 2),
            "owned_skills_count": owned_count,
            "total_skills_count": len(role_matrix)
        }
