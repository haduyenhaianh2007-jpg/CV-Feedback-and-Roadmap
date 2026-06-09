"""
Roadmap Generator - Core orchestrator for career roadmap generation

Combines:
- Skill Gap Analysis (what to learn)
- Skill Graph Insights (learning order)
- Stage Detection (appropriate difficulty)
- ATS Projection (gamification)
- Project Selection (hands-on practice)

Generates structured roadmap with:
- Phased learning plan
- Project suggestions per phase
- ATS readiness projection
- Alternative paths
"""
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json

from .stage_detector import StageDetector, StageResult
from .project_templates import ProjectPool
from .ats_projector import ATSProjector, ATSProjection

# Try to import engines from KB+analysis+engine
import sys
from pathlib import Path

# Add KB+analysis+engine to path
kb_engine_path = Path(__file__).parent.parent.parent / "KB+analysis+engine" / "skill_gap"
if kb_engine_path.exists() and str(kb_engine_path) not in sys.path:
    sys.path.insert(0, str(kb_engine_path))

try:
    from skill_gap_engine import SkillGapEngine
    from skill_graph_engine import SkillGraphEngine
    ENGINES_AVAILABLE = True
except ImportError:
    ENGINES_AVAILABLE = False


@dataclass
class Phase:
    """A single phase in the roadmap"""
    phase: int
    name: str
    duration_months: int
    estimated_hours: int
    skills: List[Dict]
    project: Optional[Dict] = None
    success_criteria: List[str] = field(default_factory=list)
    expected_readiness: int = 0
    readiness_gain: int = 0

    def to_dict(self) -> Dict:
        result = {
            "phase": self.phase,
            "name": self.name,
            "duration_months": self.duration_months,
            "estimated_hours": self.estimated_hours,
            "skills": self.skills,
            "success_criteria": self.success_criteria,
            "expected_readiness": self.expected_readiness,
            "readiness_gain": self.readiness_gain
        }
        if self.project:
            result["project"] = self.project
        return result


@dataclass
class RoadmapContract:
    """Final Roadmap Contract for frontend and LLM Narrative consumption"""
    master_graph: Dict
    user_overlay: Dict
    phases: List[Dict]
    skill_trees: List[Dict]
    prerequisite_paths: List[Dict]
    market_insights: Dict
    ats_projection: Dict
    project_mapping: Dict
    metadata: Dict

    def to_dict(self) -> Dict:
        return {
            "master_graph": self.master_graph,
            "user_overlay": self.user_overlay,
            "phases": self.phases,
            "skill_trees": self.skill_trees,
            "prerequisite_paths": self.prerequisite_paths,
            "market_insights": self.market_insights,
            "ats_projection": self.ats_projection,
            "project_mapping": self.project_mapping,
            "metadata": self.metadata
        }


class RoadmapGenerator:
    """
    Core orchestrator for career roadmap generation.

    Rule-based approach - no LLM calls in core logic.
    """

    def __init__(
        self,
        skill_gap_engine,
        skill_graph_engine,
        stage_detector: Optional[StageDetector] = None,
        project_pool: Optional[ProjectPool] = None
    ):
        """
        Initialize roadmap generator.

        Args:
            skill_gap_engine: SkillGapEngine instance
            skill_graph_engine: SkillGraphEngine instance
            stage_detector: StageDetector instance (optional)
            project_pool: ProjectPool instance (optional)
        """
        self.gap_engine = skill_gap_engine
        self.graph_engine = skill_graph_engine
        self.stage_detector = stage_detector or StageDetector()
        self.project_pool = project_pool or ProjectPool()
        self.ats_projector = ATSProjector(skill_gap_engine)

    def generate(
        self,
        cv_data: Dict,
        target_role: str,
        gap_analysis: Optional[Dict] = None
    ) -> RoadmapContract:
        """
        Generate a complete career roadmap.

        Args:
            cv_data: Structured CV data
            target_role: Target job role
            gap_analysis: Pre-computed gap analysis (optional)

        Returns:
            RoadmapContract with complete roadmap structures
        """
        # Step 1: Detect career stage
        stage_result = self.stage_detector.detect(cv_data)

        # Step 2: Get or compute gap analysis
        if gap_analysis is None:
            resume_skills = cv_data.get("skills", [])
            if isinstance(resume_skills, list) and len(resume_skills) > 0:
                if isinstance(resume_skills[0], dict):
                    resume_skills = [s.get("skill", "") for s in resume_skills]

            gap_analysis = self.gap_engine.analyze(
                resume_skills=resume_skills,
                target_role=target_role
            )

        current_readiness = int(gap_analysis["readiness_score"])
        current_skills = gap_analysis["resume_skills_normalized"]

        # Step 3: Extract graph insights
        graph_insights = gap_analysis.get("graph_insights", {})

        # Step 4: Build phased plan
        phases = self._build_phases(
            stage_result.stage,
            graph_insights,
            gap_analysis,
            target_role
        )

        # Step 5: Attach projects to phases
        phases = self._attach_projects(phases, stage_result.stage)

        # Step 6: Calculate ATS projection
        phases_dicts = [p.to_dict() for p in phases]
        ats_projection = self.ats_projector.project(
            current_skills=current_skills,
            phases=phases_dicts,
            target_role=target_role
        )

        # Step 7: Update phases with expected readiness
        phases = self._update_readiness_gains(phases, ats_projection)

        # --- ORCHESTRATE ROADMAP CONTRACT ---

        # (1) Master Graph
        role_matrix_entries = self.gap_engine.role_matrix.get(target_role, [])
        role_skills = [item["skill"] for item in role_matrix_entries]
        master_graph = self.graph_engine.get_skill_dependencies_graph(role_skills)

        # (2) User Skill Overlay
        completed = [s for s in gap_analysis.get("resume_skills_normalized", [])]
        missing = []
        for gap in gap_analysis.get("critical_gaps", []) + gap_analysis.get("medium_gaps", []) + gap_analysis.get("optional_gaps", []):
            missing.append(gap["skill"])

        # Compute partial: missing skills that have at least one prerequisite met
        partial = []
        for s in missing:
            prereqs = self.graph_engine.get_prerequisites(s)
            if prereqs and any(p in completed for p in prereqs):
                partial.append(s)
        missing = [s for s in missing if s not in partial]

        # Recommended next skills
        suggestions = self.graph_engine.suggest_next_skills(set(completed), target_role=target_role)
        recommended_next = [s["skill"] for s in suggestions]

        user_overlay = {
            "completed": completed,
            "partial": partial,
            "missing": missing,
            "recommended_next": recommended_next
        }

        # (3) Phases
        phases_list = []
        for p in phases:
            phases_list.append({
                "phase_id": p.phase,
                "title": p.name,
                "skills": [s["skill"] for s in p.skills],
                "duration_weeks": p.duration_months * 4,
                "expected_ats": p.expected_readiness
            })

        # (4) Skill Trees per phase
        skill_trees = []
        for p in phases:
            phase_trees = []
            for s_info in p.skills:
                skill_name = s_info["skill"]
                children = self.graph_engine.get_leads_to(skill_name)
                if not children:
                    children = self.graph_engine.get_related_skills(skill_name)
                phase_trees.append({
                    "root": skill_name,
                    "children": children
                })
            skill_trees.append({
                "phase_id": p.phase,
                "trees": phase_trees
            })

        # (5) Prerequisite Paths (global reasoning)
        prerequisite_paths = []
        all_gaps = list(set(user_overlay["missing"] + user_overlay["partial"]))
        for s in all_gaps:
            path = self._get_prerequisite_path(s)
            prerequisite_paths.append({
                "target_skill": s,
                "path": path
            })

        # (6) Market Insights (Tooltip data)
        market_insights = {}
        skill_to_entry = {item["skill"]: item for item in role_matrix_entries}
        
        priority_map = {}
        for gap in gap_analysis.get("critical_gaps", []):
            priority_map[gap["skill"]] = "High"
        for gap in gap_analysis.get("medium_gaps", []):
            priority_map[gap["skill"]] = "Medium"
        for gap in gap_analysis.get("optional_gaps", []):
            priority_map[gap["skill"]] = "Low"

        for skill_name, entry in skill_to_entry.items():
            freq = entry.get("frequency", 0.0)
            priority = priority_map.get(skill_name, "Low")
            market_insights[skill_name] = {
                "frequency": freq,
                "priority": priority,
                "reason": f"Xuất hiện trong {freq:.0f}% tin tuyển dụng {target_role}"
            }

        # (7) ATS Projection Output
        ats_projection_output = {
            "current": ats_projection.current,
            "final": ats_projection.final,
            "by_phase": [
                {"phase": int(k.split("_")[1]), "score": v}
                for k, v in ats_projection.phases.items()
            ]
        }

        # (8) Project Mapping Layer
        project_mapping = {}
        for p in phases:
            if p.project:
                project_mapping[str(p.phase)] = {
                    "name": p.project["name"],
                    "skills_used": p.project.get("primary_skills", p.project.get("tech_stack", [])),
                    "difficulty": p.project["difficulty"]
                }

        # (9) Metadata
        metadata = {
            "target_role": target_role,
            "stage": stage_result.stage,
            "confidence": round(stage_result.confidence, 2)
        }

        return RoadmapContract(
            master_graph=master_graph,
            user_overlay=user_overlay,
            phases=phases_list,
            skill_trees=skill_trees,
            prerequisite_paths=prerequisite_paths,
            market_insights=market_insights,
            ats_projection=ats_projection_output,
            project_mapping=project_mapping,
            metadata=metadata
        )

    def _get_prerequisite_path(self, target_skill: str) -> List[str]:
        """Generate a linear prerequisite chain leading up to target_skill."""
        path = []
        visited = set()
        curr = target_skill
        while curr and curr not in visited:
            path.append(curr)
            visited.add(curr)
            prereqs = self.graph_engine.get_prerequisites(curr)
            if prereqs:
                curr = prereqs[0]
            else:
                curr = None
        path.reverse()
        return path

    def _build_phases(
        self,
        stage: str,
        graph_insights: Dict,
        gap_analysis: Dict,
        target_role: str
    ) -> List[Phase]:
        """
        Build phased learning plan from graph insights.

        Uses graph structure to determine logical learning order:
        - Prerequisites first
        - Core skills next
        - Advanced skills last
        """
        phases = []

        # Extract skills from graph insights
        missing_prereqs = graph_insights.get("missing_prerequisites", {})
        recommended_order = graph_insights.get("recommended_learning_order", [])

        # Get gaps by priority
        critical_gaps = gap_analysis.get("critical_gaps", [])
        medium_gaps = gap_analysis.get("medium_gaps", [])
        optional_gaps = gap_analysis.get("optional_gaps", [])

        # Phase 1: Foundation (prerequisites)
        phase1_skills = self._extract_prerequisite_skills(missing_prereqs)
        if phase1_skills:
            phases.append(Phase(
                phase=1,
                name="Nền tảng cơ bản",
                duration_months=2,
                estimated_hours=60,
                skills=phase1_skills,
                success_criteria=["Hoàn thành tất cả prerequisite skills"]
            ))

        # Phase 2: Core (medium gaps)
        phase2_skills = self._extract_core_skills(medium_gaps, recommended_order)
        if phase2_skills:
            phases.append(Phase(
                phase=2,
                name="Kỹ năng cốt lõi",
                duration_months=3,
                estimated_hours=80,
                skills=phase2_skills,
                success_criteria=["Xây dựng được project với core skills"]
            ))

        # Phase 3: Advanced (critical gaps + high-freq optional)
        phase3_skills = self._extract_advanced_skills(
            critical_gaps, optional_gaps, recommended_order
        )
        if phase3_skills:
            phases.append(Phase(
                phase=3,
                name="Kỹ năng nâng cao",
                duration_months=3,
                estimated_hours=90,
                skills=phase3_skills,
                success_criteria=["Hoàn thành advanced project"]
            ))

        # Phase 4: Production (deepen + expand)
        phase4_skills = self._extract_production_skills(graph_insights)
        if phase4_skills:
            phases.append(Phase(
                phase=4,
                name="Production-ready",
                duration_months=2,
                estimated_hours=70,
                skills=phase4_skills,
                success_criteria=["Deploy production project"]
            ))

        return phases

    def _extract_prerequisite_skills(self, missing_prereqs: Dict) -> List[Dict]:
        """Extract prerequisite skills for Phase 1."""
        prereq_skills = []
        seen = set()

        for target_skill, prereqs in missing_prereqs.items():
            for prereq in prereqs:
                if prereq not in seen:
                    seen.add(prereq)
                    prereq_skills.append({
                        "skill": prereq,
                        "reason": f"Prerequisite cho {target_skill}"
                    })

        return prereq_skills[:3]  # Limit to 3 skills per phase

    def _extract_core_skills(
        self,
        medium_gaps: List[Dict],
        recommended_order: List[Dict]
    ) -> List[Dict]:
        """Extract core skills for Phase 2."""
        core_skills = []

        # Prioritize medium gaps
        for gap in medium_gaps[:2]:
            skill = gap.get("skill")
            freq = gap.get("frequency", 0)
            core_skills.append({
                "skill": skill,
                "reason": f"Medium gap - frequency {freq:.1f}%"
            })

        return core_skills

    def _extract_advanced_skills(
        self,
        critical_gaps: List[Dict],
        optional_gaps: List[Dict],
        recommended_order: List[Dict]
    ) -> List[Dict]:
        """Extract advanced skills for Phase 3."""
        advanced_skills = []

        # Critical gaps first
        for gap in critical_gaps[:2]:
            skill = gap.get("skill")
            freq = gap.get("frequency", 0)
            advanced_skills.append({
                "skill": skill,
                "reason": f"Critical gap - frequency {freq:.1f}%"
            })

        # High-frequency optional gaps
        high_freq = [g for g in optional_gaps if g.get("frequency", 0) >= 30]
        for gap in high_freq[:1]:
            skill = gap.get("skill")
            freq = gap.get("frequency", 0)
            advanced_skills.append({
                "skill": skill,
                "reason": f"High-frequency optional - {freq:.1f}%"
            })

        return advanced_skills

    def _extract_production_skills(self, graph_insights: Dict) -> List[Dict]:
        """Extract production skills for Phase 4."""
        production_skills = []

        # Deepen skills (from graph)
        deepen = graph_insights.get("deepen_skills", {})
        recommended_next = deepen.get("recommended_next", [])

        for item in recommended_next[:2]:
            skill = item.get("skill")
            source = item.get("source_skill", "")
            production_skills.append({
                "skill": skill,
                "reason": f"Natural progression từ {source}"
            })

        # Add Docker if not already included
        skill_names = [s["skill"] for s in production_skills]
        if "Docker" not in skill_names:
            production_skills.append({
                "skill": "Docker",
                "reason": "Production deployment skill"
            })

        return production_skills

    def _attach_projects(self, phases: List[Phase], stage: str) -> List[Phase]:
        """Attach project suggestions to each phase."""
        for phase in phases:
            phase_skills = [s["skill"] for s in phase.skills]
            project = self.project_pool.select_best(phase_skills, stage)

            if project:
                phase.project = project.to_dict()
                phase.success_criteria.extend(project.learning_outcomes[:2])
                phase.estimated_hours = project.estimated_hours

        return phases

    def _update_readiness_gains(
        self,
        phases: List[Phase],
        ats_projection: ATSProjection
    ) -> List[Phase]:
        """Update phases with expected readiness scores."""
        prev_readiness = ats_projection.current

        for i, phase in enumerate(phases, 1):
            phase_key = f"phase_{i}"
            expected_readiness = ats_projection.phases.get(phase_key, prev_readiness)

            phase.expected_readiness = expected_readiness
            phase.readiness_gain = expected_readiness - prev_readiness
            prev_readiness = expected_readiness

        return phases

    def _generate_optional_stretch(self, graph_insights: Dict) -> List[Dict]:
        """Generate optional stretch skills."""
        optional = []

        deepen = graph_insights.get("deepen_skills", {})
        recommended_next = deepen.get("recommended_next", [])

        for item in recommended_next[2:5]:  # Skip first 2 (already in phases)
            optional.append({
                "skill": item.get("skill"),
                "reason": item.get("reason", "Deepen skill")
            })

        return optional

    def _generate_alternatives(self, stage: str) -> Dict:
        """Generate alternative learning paths."""
        return {
            "if_has_cloud_already": "Skip cloud skills, add MLOps focus",
            "if_prefers_research": "Replace Phase 4 with 'Research & Paper Reproduction'",
            "if_targeting_startup": "Add full-stack skills (JavaScript, React)"
        }


if __name__ == "__main__":
    # Demo (requires engines)
    print("Roadmap Generator Demo")
    print("="*70)
    print("This demo requires SkillGapEngine and SkillGraphEngine")
    print("See examples/demo_roadmap.py for full working demo")