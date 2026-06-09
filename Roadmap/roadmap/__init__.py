"""
Roadmap Module - Career Roadmap Generator

This module generates personalized learning roadmaps based on:
- Skill Gap Analysis (what to learn)
- Skill Graph Insights (learning order)
- Career Stage Detection (appropriate difficulty)
- Market Insights (trending skills)

Core Components:
- StageDetector: Detects career stage (Student/Fresher/Junior/Middle)
- RoadmapGenerator: Orchestrates roadmap creation (rule-based)
- ATSProjector: Calculates projected ATS readiness scores
- ProjectPool: Suggests hands-on projects per phase

Usage:
    from roadmap import RoadmapGenerator, StageDetector

    generator = RoadmapGenerator(
        skill_gap_engine=gap_engine,
        skill_graph_engine=graph_engine
    )

    roadmap = generator.generate(
        cv_data=cv_data,
        target_role="AI Engineer"
    )
"""

from .stage_detector import StageDetector, StageResult
from .roadmap_generator import RoadmapGenerator
from .ats_projector import ATSProjector
from .project_templates import ProjectPool

__all__ = [
    "StageDetector",
    "StageResult",
    "RoadmapGenerator",
    "ATSProjector",
    "ProjectPool",
]

__version__ = "1.0.0"
