"""
Severity Analysis Module
Categorizes missing skills by how critical they are for the target role.
"""
from typing import List, Dict


class SeverityAnalyzer:
    """
    V1 thresholds (hard-coded):
    - Critical: frequency >= 70
    - Medium:   50 <= frequency < 70
    - Optional: frequency < 50
    """

    CRITICAL_THRESHOLD = 70
    MEDIUM_THRESHOLD = 50

    def analyze(self, missing_skills: List[Dict]) -> Dict:
        """
        Args:
            missing_skills: list of {skill, frequency} dicts from WeaknessAnalyzer

        Returns:
            {
                "critical_gaps": [{"skill": ..., "frequency": ...}, ...],
                "medium_gaps": [...],
                "optional_gaps": [...]
            }
        """
        critical, medium, optional = [], [], []

        for item in missing_skills:
            freq = item["frequency"]
            entry = {"skill": item["skill"], "frequency": freq}

            if freq >= self.CRITICAL_THRESHOLD:
                critical.append(entry)
            elif freq >= self.MEDIUM_THRESHOLD:
                medium.append(entry)
            else:
                optional.append(entry)

        # Each list is already sorted by frequency desc (preserved from weakness analyzer)
        return {
            "critical_gaps": critical,
            "medium_gaps": medium,
            "optional_gaps": optional
        }
