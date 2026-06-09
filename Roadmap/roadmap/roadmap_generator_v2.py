"""
Roadmap Generator V2 - Tích hợp LLM Narrative Layer

Pipeline:
Role-Pruned Graph -> Phase Builder V2 -> Graph ATS Scorer -> LLM Narrative Layer -> Full Contract

Output contract bao gồm:
- pruned_graph, phases, ats_report, user_overlay, project_mapping, metadata
- narrative: { phase_narratives, personalized_story, ats_report }
"""
from typing import Dict, List, Set, Optional
from dataclasses import dataclass, field
from pathlib import Path
import sys

from .stage_detector import StageDetector, StageResult
from .project_templates import ProjectPool

# Import V2 modules
from .role_aware_pruner import RoleAwarePruner
from .phase_builder_v2 import HardConstraintPhaseBuilder
from .graph_ats_scorer import GraphATSScorer, ATSReport
from .llm_narrative_layer import LLMNarrativeLayer

# Thêm đường dẫn cho KB+analysis+engine
kb_path = Path(__file__).parent.parent.parent / "KB+analysis+engine" / "skill_gap"
if kb_path.exists() and str(kb_path) not in sys.path:
    sys.path.insert(0, str(kb_path))

try:
    from skill_gap_engine import SkillGapEngine
    from skill_graph_engine import SkillGraphEngine
    ENGINES_AVAILABLE = True
except ImportError:
    ENGINES_AVAILABLE = False
    print("Warning: SkillGapEngine or SkillGraphEngine not available")


@dataclass
class RoadmapContractV2:
    """Roadmap contract cho frontend - phiên bản có narrative."""
    pruned_graph: Dict
    phases: List[Dict]
    ats_report: Dict
    user_overlay: Dict
    project_mapping: Dict
    metadata: Dict
    narrative: Dict  # Thêm trường narrative

    def to_dict(self) -> Dict:
        return {
            "pruned_graph": self.pruned_graph,
            "phases": self.phases,
            "ats_report": self.ats_report,
            "user_overlay": self.user_overlay,
            "project_mapping": self.project_mapping,
            "metadata": self.metadata,
            "narrative": self.narrative
        }


class RoadmapGeneratorV2:
    """
    Roadmap Generator v2 với graph-based pipeline và LLM narrative layer.
    """

    def __init__(
        self,
        skill_gap_engine,
        skill_graph_engine,
        stage_detector: Optional[StageDetector] = None,
        project_pool: Optional[ProjectPool] = None
    ):
        self.gap_engine = skill_gap_engine
        self.graph_engine = skill_graph_engine
        self.stage_detector = stage_detector or StageDetector()
        self.project_pool = project_pool or ProjectPool()

        # Khởi tạo V2 modules
        self.pruner = RoleAwarePruner(skill_graph_engine)
        self.phase_builder = HardConstraintPhaseBuilder(
            skill_graph_engine,
            max_skills_per_phase=5
        )
        self.ats_scorer = GraphATSScorer(
            skill_graph_engine,
            role_matrix=skill_gap_engine.role_matrix if hasattr(skill_gap_engine, 'role_matrix') else None
        )
        self.narrative_engine = LLMNarrativeLayer()

    def generate(
        self,
        cv_data: Dict,
        target_role: str,
        gap_analysis: Optional[Dict] = None
    ) -> RoadmapContractV2:
        """
        Tạo roadmap hoàn chỉnh có narrative.
        """
        # Step 1: Stage detection
        stage_result = self.stage_detector.detect(cv_data)

        # Step 2: Gap analysis (nếu chưa có)
        if gap_analysis is None:
            resume_skills = cv_data.get("skills", [])
            if isinstance(resume_skills, list) and len(resume_skills) > 0:
                if isinstance(resume_skills[0], dict):
                    resume_skills = [s.get("skill", "") for s in resume_skills]

            gap_analysis = self.gap_engine.analyze(
                resume_skills=resume_skills,
                target_role=target_role
            )

        current_skills = gap_analysis.get("resume_skills_normalized", [])
        current_readiness = gap_analysis.get("readiness_score", 0)

        # Step 3: Lấy full graph từ role matrix
        role_matrix_entries = self.gap_engine.role_matrix.get(target_role, [])
        role_skills = [item["skill"] for item in role_matrix_entries]
        full_graph = self._build_full_graph(role_skills)

        # Step 4: Role-aware pruning
        pruning_result = self.pruner.prune(
            full_graph=full_graph,
            target_role=target_role,
            current_skills=current_skills,
            role_matrix={item["skill"]: item for item in role_matrix_entries}
        )

        pruned_graph = pruning_result["pruned_graph"]
        pruned_skills = [node.get("id", node.get("skill", ""))
                        for node in pruned_graph.get("nodes", [])]

        # Step 5: Phase building (hard constraints)
        phases = self.phase_builder.build_phases(
            skills=pruned_skills,
            current_skills=current_skills
        )

        # Step 6: ATS scoring (graph-based)
        phases_for_ats = [{"skills": p["skills"]} for p in phases]
        ats_result = self.ats_scorer.project_phases(
            current_skills=current_skills,
            phases=phases_for_ats,
            target_role=target_role
        )

        # Step 7: User skill overlay
        user_overlay = self._build_user_overlay(gap_analysis, current_skills)

        # Step 8: Project mapping
        project_mapping = self._attach_projects(phases, stage_result.stage)

        # Step 9: Metadata
        metadata = {
            "target_role": target_role,
            "stage": stage_result.stage,
            "confidence": round(stage_result.confidence, 2),
            "pruning_stats": pruning_result["statistics"]
        }

        # Convert phases to dict format
        phases_dict = []
        for p in phases:
            phases_dict.append({
                "phase_id": p["phase_id"],
                "title": p["title"],
                "skills": p["skills"],
                "skill_count": p["skill_count"],
                "avg_depth": p["avg_depth"],
                "reason": p["reason"]
            })

        # Convert ATS report to dict
        ats_dict = {
            "current_score": ats_result.current_score,
            "final_score": ats_result.final_score,
            "phase_contributions": ats_result.phase_contributions,
            "bottlenecks": ats_result.bottlenecks,
            "penalties": ats_result.penalties
        }

        # Step 10: Tạo narrative (chỉ explain, không compute)
        user_status_for_narrative = {
            "completed": user_overlay.get("completed", []),
            "missing": user_overlay.get("missing", []),
            "partial": user_overlay.get("partial", []),
            "stage": stage_result.stage
        }

        narrative = self.narrative_engine.generate_full_narrative(
            roadmap_data={"phases": phases_dict},
            ats_data=ats_dict,
            user_status=user_status_for_narrative,
            target_role=target_role
        )

        return RoadmapContractV2(
            pruned_graph=pruned_graph,
            phases=phases_dict,
            ats_report=ats_dict,
            user_overlay=user_overlay,
            project_mapping=project_mapping,
            metadata=metadata,
            narrative=narrative
        )

    def _build_full_graph(self, skills: List[str]) -> Dict:
        """Xây dựng full graph từ danh sách skills."""
        nodes = []
        for skill in skills:
            nodes.append({"id": skill, "type": "skill"})

        edges = []
        for skill in skills:
            prereqs = self.graph_engine.get_prerequisites(skill) if hasattr(self.graph_engine, 'get_prerequisites') else []
            for prereq in prereqs:
                if prereq in skills:
                    edges.append({"from": prereq, "to": skill, "type": "prerequisite"})

        return {"nodes": nodes, "edges": edges}

    def _build_user_overlay(self, gap_analysis: Dict, current_skills: List[str]) -> Dict:
        """Xây dựng user skill overlay."""
        completed = current_skills.copy()

        missing = []
        for gap in gap_analysis.get("critical_gaps", []) + gap_analysis.get("medium_gaps", []):
            missing.append(gap["skill"])

        # Partial: missing skills có ít nhất một prerequisite đã có
        partial = []
        for s in missing[:]:
            prereqs = self.graph_engine.get_prerequisites(s) if hasattr(self.graph_engine, 'get_prerequisites') else []
            if prereqs and any(p in completed for p in prereqs):
                partial.append(s)
                missing.remove(s)

        return {
            "completed": completed,
            "partial": partial,
            "missing": missing,
            "total_completed": len(completed),
            "total_partial": len(partial),
            "total_missing": len(missing)
        }

    def _attach_projects(self, phases: List[Dict], stage: str) -> Dict:
        """Gán project cho từng phase."""
        mapping = {}
        for phase in phases:
            project = self.project_pool.select_best(phase["skills"], stage)
            if project:
                mapping[str(phase["phase_id"])] = {
                    "name": project.name,
                    "skills_used": project.primary_skills,
                    "difficulty": project.difficulty,
                    "estimated_hours": project.estimated_hours
                }
        return mapping


if __name__ == "__main__":
    print("RoadmapGeneratorV2 module loaded")
    print("Đã tích hợp: RoleAwarePruner + HardConstraintPhaseBuilder + GraphATSScorer + LLMNarrativeLayer")
    print("Output contract đã có trường 'narrative' với 3 loại: phase_narratives, personalized_story, ats_report")
