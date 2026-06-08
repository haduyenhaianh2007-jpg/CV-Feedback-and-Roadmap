"""
Skill Gap Analysis V1 package

Public API:
    from skill_gap import SkillGapEngine

    engine = SkillGapEngine()
    result = engine.analyze(resume_skills=[...], target_role="AI Engineer")
"""
from skill_gap_engine import SkillGapEngine

__all__ = ["SkillGapEngine"]
