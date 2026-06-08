"""
Weakness Analysis Module
Finds skills the target role requires but the CV lacks.
"""
from typing import List, Dict


class WeaknessAnalyzer:
    """
    Computes: required_skills - resume_skills
    """

    def analyze(
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
                "missing_skills": [
                    {"skill": "Docker", "frequency": 81},
                    ...
                ]
            }
        """
        resume_set = set(s.lower() for s in resume_skills)

        missing = []
        for item in role_matrix:
            if item["skill"].lower() not in resume_set:
                missing.append({
                    "skill": item["skill"],
                    "frequency": item["frequency"]
                })

        # Sort by frequency descending (most important gaps first)
        missing.sort(key=lambda x: x["frequency"], reverse=True)

        return {"missing_skills": missing}
