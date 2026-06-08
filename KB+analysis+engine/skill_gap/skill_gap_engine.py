"""
Skill Gap Engine - Orchestrator
Composes all sub-analyzers to produce a full skill gap report.

V1 pipeline (8 steps):
1. Normalize skills      (skill_ontology.json)
2. Validate role         (V1: direct match)
3. Strength analysis     (CV ∩ role requirements)
4. Weakness analysis     (role requirements - CV)
5. Severity analysis     (critical / medium / optional gaps)
6. Readiness score       (owned_weight / total_weight)
7. Improvement actions   (rule-based, per-gap)
8. Assemble structured JSON output
"""
import csv
import json
from pathlib import Path
from typing import List, Dict, Optional, Set

from skill_normalization import SkillNormalizer
from strength_analyzer import StrengthAnalyzer
from weakness_analyzer import WeaknessAnalyzer
from severity_analyzer import SeverityAnalyzer
from readiness_calculator import ReadinessCalculator
from improvement_analyzer import ImprovementAnalyzer
from skill_graph_engine import SkillGraphEngine


class SkillGapEngine:
    """
    Main entry point for Skill Gap Analysis V1.
    Loads the Knowledge Base once and runs the 8-step pipeline on demand.
    """

    def __init__(self, kb_root: Optional[str] = None):
        if kb_root is None:
            kb_root = Path(__file__).parent.parent / "knowledge_base" / "outputs"
        else:
            kb_root = Path(kb_root)

        self.kb_root = kb_root

        # Load KB components once
        self.normalizer = SkillNormalizer(str(kb_root / "skill_ontology.json"))
        self.role_matrix = self._load_role_matrix()

        # Sub-analyzers (stateless)
        self.strength_analyzer = StrengthAnalyzer()
        self.weakness_analyzer = WeaknessAnalyzer()
        self.severity_analyzer = SeverityAnalyzer()
        self.readiness_calculator = ReadinessCalculator()
        self.improvement_analyzer = ImprovementAnalyzer()

        # Skill Graph Engine (Integration V1)
        self.graph_engine = SkillGraphEngine()

    def _load_role_matrix(self) -> Dict[str, List[Dict]]:
        """
        Loads role_skill_matrix.csv and indexes by canonical role name.
        Returns: {role: [{"skill": ..., "frequency": ..., "count": ..., "total_jobs": ...}, ...]}
        """
        matrix: Dict[str, List[Dict]] = {}
        csv_path = self.kb_root / "role_skill_matrix.csv"

        # utf-8-sig automatically strips BOM if present
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                role = row["role"]
                entry = {
                    "skill": row["skill"],
                    "frequency": float(row["frequency_pct"]),
                    "count": int(row["count"]),
                    "total_jobs": int(row["total_jobs_in_role"])
                }
                matrix.setdefault(role, []).append(entry)

        # Sort each role's skills by frequency desc for deterministic ordering
        for role in matrix:
            matrix[role].sort(key=lambda x: x["frequency"], reverse=True)

        return matrix

    def analyze(
        self,
        resume_skills: List[str],
        target_role: str,
        max_improvement_actions: int = 5
    ) -> Dict:
        """
        Run the full 8-step Skill Gap Analysis pipeline.

        Args:
            resume_skills: raw skill names extracted from the CV
            target_role: canonical role name (V1: must match role in KB exactly)
            max_improvement_actions: cap on improvement actions in output

        Returns:
            Structured analysis dict (ready to feed to LLM feedback generator)

        Raises:
            ValueError: if target_role is not present in the knowledge base
        """
        # Step 2: Role validation (V1 - strict match)
        if target_role not in self.role_matrix:
            available = sorted(self.role_matrix.keys())[:10]
            raise ValueError(
                f"Role '{target_role}' not found in knowledge base. "
                f"Sample available roles: {available}"
            )

        role_matrix = self.role_matrix[target_role]

        # Step 1: Normalize skills
        matched_skills, unknown_skills = self.normalizer.get_canonical_names(resume_skills)

        # Step 3: Strength analysis
        # Skills in CV but NOT in role matrix are "extra skills"
        role_skill_names = [item["skill"] for item in role_matrix]
        role_skill_set = set(s.lower() for s in role_skill_names)
        extra_skills = [s for s in matched_skills if s.lower() not in role_skill_set]

        strength_result = self.strength_analyzer.analyze(
            matched_skills, role_matrix, extra_skills
        )

        # Step 4: Weakness analysis
        weakness_result = self.weakness_analyzer.analyze(matched_skills, role_matrix)

        # Step 5: Severity analysis
        severity_result = self.severity_analyzer.analyze(weakness_result["missing_skills"])

        # Step 6: Readiness score
        readiness_result = self.readiness_calculator.calculate(matched_skills, role_matrix)

        # Step 7: Improvement actions
        improvement_result = self.improvement_analyzer.analyze(
            critical_gaps=severity_result["critical_gaps"],
            medium_gaps=severity_result["medium_gaps"],
            optional_gaps=severity_result["optional_gaps"],
            max_actions=max_improvement_actions
        )

        # Step 8: Assemble final structuredured output
        output = {
            "target_role": target_role,
            "resume_skills_raw": resume_skills,
            "resume_skills_normalized": matched_skills,
            "unknown_skills": unknown_skills,
            "readiness_score": readiness_result["readiness_score"],
            "readiness_breakdown": {
                "owned_weight": readiness_result["owned_weight"],
                "total_weight": readiness_result["total_weight"],
                "owned_skills_count": readiness_result["owned_skills_count"],
                "total_skills_count": readiness_result["total_skills_count"]
            },
            "strengths": strength_result["strengths"],
            "extra_skills": strength_result.get("extra_skills", []),
            "critical_gaps": severity_result["critical_gaps"],
            "medium_gaps": severity_result["medium_gaps"],
            "optional_gaps": severity_result["optional_gaps"],
            "improvement_actions": improvement_result["improvement_actions"]
        }

        # Step 9: Generate graph insights (Integration V1)
        graph_insights = self._generate_graph_insights(
            critical_gaps=severity_result["critical_gaps"],
            medium_gaps=severity_result["medium_gaps"],
            optional_gaps=severity_result["optional_gaps"],
            strengths=strength_result["strengths"],
            matched_skills=matched_skills
        )
        output["graph_insights"] = graph_insights

        return output

    def _generate_graph_insights(
        self,
        critical_gaps: List[Dict],
        medium_gaps: List[Dict],
        optional_gaps: List[Dict],
        strengths: List[Dict],
        matched_skills: List[str]
    ) -> Dict:
        """
        Generate learning path insights from Skill Graph (2-directional).

        Dimension 1 — MISSING → PREREQUISITES:
            For critical/medium gaps, surface missing prerequisites and a
            learning order to reach them.

        Dimension 2 — OWNED → ADVANCED (deepen):
            For strong skills (frequency >= 50%) already held, surface the
            skills they naturally lead to — so the user can deepen expertise
            rather than only patching gaps.

        Dimension 3 — HIGH-FREQUENCY OPTIONAL → EXPAND:
            For optional gaps with frequency >= 20%, treat them as expansion
            targets and compute prerequisites.

        Args:
            critical_gaps: Critical gap dicts with "skill" key
            medium_gaps: Medium gap dicts with "skill" key
            optional_gaps: Optional gap dicts with "skill" and "frequency" keys
            strengths: Strength dicts with "skill" and "frequency" keys
            matched_skills: Skills user already has (normalized)

        Returns:
            {
                "missing_skills": {
                    "target_skills": [...],
                    "missing_prerequisites": {skill: [prereqs]}
                },
                "deepen_skills": {
                    "current_strengths": [...],
                    "recommended_next": [{skill, reason, source_skill}]
                },
                "expand_skills": {
                    "target_skills": [...],
                    "missing_prerequisites": {skill: [prereqs]}
                },
                "recommended_learning_order": [...]
            }
        """
        matched_set = set(matched_skills)

        # --- Dimension 1: Missing → prerequisites ---
        missing = self._build_missing_insights(
            critical_gaps + medium_gaps, matched_set
        )

        # --- Dimension 2: Owned strengths → advanced skills ---
        deepen = self._build_deepen_insights(strengths, matched_set)

        # --- Dimension 3: High-frequency optionals → expansion ---
        high_freq_optionals = [
            g for g in optional_gaps if g.get("frequency", 0) >= 20
        ]
        expand = self._build_missing_insights(high_freq_optionals, matched_set)

        # --- Merge learning order: prerequisites (dedup) → targets → deepens ---
        learning_order = self._merge_learning_order(missing, expand, deepen)

        return {
            "missing_skills": missing,
            "deepen_skills": deepen,
            "expand_skills": expand,
            "recommended_learning_order": learning_order
        }

    def _build_missing_insights(
        self, gaps: List[Dict], matched_set: Set[str]
    ) -> Dict:
        """
        For a list of gap skills, compute target_skills and missing_prerequisites.
        Used for both dimension 1 (critical/medium) and dimension 3 (optional).
        """
        target_skills: List[str] = []
        missing_prerequisites: Dict[str, List[str]] = {}

        for gap in gaps:
            skill = gap.get("skill")
            if not skill:
                continue
            target_skills.append(skill)
            prereqs = self.graph_engine.get_all_prerequisites(
                skill, current_skills=matched_set
            )
            if prereqs:
                missing_prerequisites[skill] = prereqs

        return {
            "target_skills": target_skills,
            "missing_prerequisites": missing_prerequisites
        }

    def _build_deepen_insights(
        self, strengths: List[Dict], matched_set: Set[str]
    ) -> Dict:
        """
        For owned strengths with frequency >= 50%, surface the skills they
        naturally lead to (next steps to deepen expertise).
        """
        strong_skills = [
            s for s in strengths
            if s.get("frequency", 0) >= 50
        ]
        current_strengths: List[str] = []
        recommended_next: List[Dict] = []
        seen_next: set = set()

        for strength in strong_skills:
            skill = strength.get("skill")
            if not skill:
                continue
            current_strengths.append(skill)
            leads_to = self.graph_engine.get_leads_to(skill)
            for next_skill in leads_to:
                if next_skill in matched_set:
                    continue  # already known
                if next_skill in seen_next:
                    continue
                seen_next.add(next_skill)
                recommended_next.append({
                    "skill": next_skill,
                    "reason": f"Natural progression from {skill}",
                    "source_skill": skill,
                    "source_frequency": strength.get("frequency", 0)
                })

        return {
            "current_strengths": current_strengths,
            "recommended_next": recommended_next
        }

    def _merge_learning_order(
        self, missing: Dict, expand: Dict, deepen: Dict
    ) -> List[Dict]:
        """
        Merge all three dimensions into a single deduplicated learning order.
        Priority: missing prerequisites → missing targets → expand prereqs →
        expand targets → deepen next skills.
        """
        order: List[Dict] = []
        seen: Set[str] = set()

        def add_step(skill: str, step_type: str, source: str = ""):
            if skill in seen:
                return
            seen.add(skill)
            order.append({
                "skill": skill,
                "type": step_type,
                "source": source
            })

        # Missing dimension: prerequisites first
        for skill, prereqs in missing.get("missing_prerequisites", {}).items():
            for prereq in prereqs:
                add_step(prereq, "prerequisite_for_gap", skill)
        for skill in missing.get("target_skills", []):
            add_step(skill, "gap_target", "")

        # Expand dimension
        for skill, prereqs in expand.get("missing_prerequisites", {}).items():
            for prereq in prereqs:
                add_step(prereq, "prerequisite_for_expansion", skill)
        for skill in expand.get("target_skills", []):
            add_step(skill, "expansion_target", "")

        # Deepen dimension
        for item in deepen.get("recommended_next", []):
            add_step(item["skill"], "deepen", item.get("source_skill", ""))

        return order


if __name__ == "__main__":
    # End-to-end smoke test with the spec example
    engine = SkillGapEngine()

    result = engine.analyze(
        resume_skills=["Python", "PyTorch", "Computer Vision"],
        target_role="AI Engineer"
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))
