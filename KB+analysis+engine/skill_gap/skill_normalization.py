"""
Skill Normalization Module
Maps raw CV skills to canonical skill names using skill_ontology.json
"""
import json
from pathlib import Path
from typing import List, Dict, Tuple


class SkillNormalizer:
    def __init__(self, ontology_path: str = None):
        if ontology_path is None:
            ontology_path = Path(__file__).parent.parent / "knowledge_base" / "outputs" / "skill_ontology.json"

        with open(ontology_path, 'r', encoding='utf-8') as f:
            self.ontology = json.load(f)

        # Build lowercase lookup for case-insensitive matching
        self._lowercase_map = {k.lower(): v for k, v in self.ontology.items()}

    def normalize(self, skills: List[str]) -> List[Dict]:
        """
        Normalize a list of raw skills to canonical names.

        Returns list of dicts with:
        - original: raw skill name from CV
        - canonical: normalized skill name
        - status: "matched" | "unknown"
        """
        results = []
        for skill in skills:
            if not skill or not skill.strip():
                continue

            original = skill.strip()
            lookup = original.lower()

            # Try exact lowercase match
            if lookup in self._lowercase_map:
                canonical = self._lowercase_map[lookup]
                status = "matched"
            else:
                # Not in ontology - mark as unknown
                canonical = original
                status = "unknown"

            results.append({
                "original": original,
                "canonical": canonical,
                "status": status
            })

        return results

    def get_canonical_names(self, skills: List[str]) -> Tuple[List[str], List[str]]:
        """
        Convenience method: returns (matched_skills, unknown_skills)
        Deduplicates canonical names.
        """
        normalized = self.normalize(skills)

        matched = list(dict.fromkeys(
            item["canonical"] for item in normalized if item["status"] == "matched"
        ))
        unknown = list(dict.fromkeys(
            item["original"] for item in normalized if item["status"] == "unknown"
        ))

        return matched, unknown


if __name__ == "__main__":
    # Quick test
    normalizer = SkillNormalizer()
    test_skills = ["py", "python3", "pytorch", "docker", "SuperNewFramework2027", "Computer Vision"]
    matched, unknown = normalizer.get_canonical_names(test_skills)
    print(f"Matched: {matched}")
    print(f"Unknown: {unknown}")
