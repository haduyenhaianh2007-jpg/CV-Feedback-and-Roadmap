"""
Stage Detector - Detect career stage from CV data

Detects one of: Student, Fresher, Junior, Middle
Based on:
- Work experience years
- Skill depth (advanced skills count)
- Job titles
- Education signals
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class StageResult:
    """Result of stage detection"""
    stage: str  # "Student" | "Fresher" | "Junior" | "Middle"
    confidence: float  # 0.0 - 1.0
    signals: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "stage": self.stage,
            "confidence": round(self.confidence, 2),
            "signals": self.signals
        }


class StageDetector:
    """
    Detect career stage from CV structured data.

    Uses rule-based heuristics with confidence scoring.
    """

    STAGES = ["Student", "Fresher", "Junior", "Middle"]

    def __init__(self, rules_file: Optional[str] = None):
        """
        Initialize stage detector.

        Args:
            rules_file: Path to stage_rules.json (optional)
        """
        if rules_file is None:
            rules_file = Path(__file__).parent / "data" / "stage_rules.json"

        self.rules_file = Path(rules_file)
        self._load_rules()

    def _load_rules(self):
        """Load stage detection rules from JSON file."""
        if not self.rules_file.exists():
            # Use default rules if file not found
            self.rules = self._default_rules()
            return

        with open(self.rules_file, 'r', encoding='utf-8') as f:
            self.rules = json.load(f)

    def _default_rules(self) -> Dict:
        """Default rules if JSON file not found."""
        return {
            "rules": {
                "experience_thresholds": {
                    "Student": {"max_years": 0},
                    "Fresher": {"min_years": 0, "max_years": 1},
                    "Junior": {"min_years": 1, "max_years": 3},
                    "Middle": {"min_years": 3, "max_years": 6}
                },
                "skill_depth_adjustments": {
                    "advanced_skills": ["LLM", "RAG", "LangChain", "Kubernetes", "Docker", "MLOps"]
                }
            }
        }

    def detect(self, cv_data: Dict) -> StageResult:
        """
        Detect career stage from CV data.

        Args:
            cv_data: Structured CV data with keys:
                - work_history: List of work experiences
                - skills: List of skills
                - education: Education info (optional)
                - job_titles: List of job titles (optional)

        Returns:
            StageResult with stage, confidence, and signals
        """
        signals = {}
        confidence = 0.7  # Base confidence

        # Extract experience years
        exp_years = self._extract_experience_years(cv_data)
        signals["work_experience_years"] = exp_years

        # Base stage from experience
        base_stage = self._stage_from_experience(exp_years)

        # Skill depth adjustment
        skill_depth = self._analyze_skill_depth(cv_data)
        signals["skill_count"] = skill_depth["total_skills"]
        signals["advanced_skill_count"] = skill_depth["advanced_skills"]
        signals["has_advanced_skills"] = skill_depth["advanced_skills"] > 0

        adjusted_stage = self._adjust_stage_by_skills(
            base_stage, skill_depth
        )

        # Job title signals
        job_title_stage = self._detect_stage_from_titles(cv_data)
        if job_title_stage:
            signals["job_title_stage"] = job_title_stage
            if job_title_stage == adjusted_stage:
                confidence += 0.1

        # Education signals
        edu_stage = self._detect_stage_from_education(cv_data)
        if edu_stage:
            signals["education_stage"] = edu_stage

        # Refine reason
        signals["refined_reason"] = self._build_reason(
            exp_years, skill_depth, adjusted_stage
        )

        # Confidence adjustments
        if exp_years is None:
            confidence -= 0.2
        if skill_depth["advanced_skills"] > 0:
            confidence += 0.1

        confidence = max(0.0, min(1.0, confidence))

        return StageResult(
            stage=adjusted_stage,
            confidence=confidence,
            signals=signals
        )

    def _extract_experience_years(self, cv_data: Dict) -> Optional[float]:
        """Extract total work experience in years."""
        work_history = cv_data.get("work_history", [])

        if not work_history:
            # Try to infer from other fields
            if "experience_years" in cv_data:
                return float(cv_data["experience_years"])
            return None

        total_months = 0
        for job in work_history:
            duration = job.get("duration_months", 0)
            if duration:
                total_months += duration

        return total_months / 12.0 if total_months > 0 else None

    def _stage_from_experience(self, exp_years: Optional[float]) -> str:
        """Determine base stage from experience years."""
        if exp_years is None:
            return "Student"

        thresholds = self.rules["rules"]["experience_thresholds"]

        if exp_years <= thresholds["Student"]["max_years"]:
            return "Student"
        elif exp_years <= thresholds["Fresher"]["max_years"]:
            return "Fresher"
        elif exp_years <= thresholds["Junior"]["max_years"]:
            return "Junior"
        else:
            return "Middle"

    def _analyze_skill_depth(self, cv_data: Dict) -> Dict:
        """Analyze skill depth from CV."""
        skills = cv_data.get("skills", [])
        if isinstance(skills, list):
            skill_names = skills
        else:
            skill_names = [s.get("skill", "") for s in skills]

        advanced_skills = self.rules["rules"]["skill_depth_adjustments"]["advanced_skills"]

        advanced_count = sum(1 for skill in skill_names if skill in advanced_skills)

        return {
            "total_skills": len(skill_names),
            "advanced_skills": advanced_count,
            "advanced_skill_list": [s for s in skill_names if s in advanced_skills]
        }

    def _adjust_stage_by_skills(self, base_stage: str, skill_depth: Dict) -> str:
        """Adjust stage based on skill depth."""
        advanced_count = skill_depth["advanced_skills"]

        if advanced_count == 0:
            return base_stage

        stage_index = self.STAGES.index(base_stage)

        # Adjustment rules
        if advanced_count >= 5:
            # Expert level - jump 2 stages
            new_index = min(stage_index + 2, len(self.STAGES) - 1)
        elif advanced_count >= 3:
            # Strong depth - jump 1 stage
            new_index = min(stage_index + 1, len(self.STAGES) - 1)
        else:
            new_index = stage_index

        return self.STAGES[new_index]

    def _detect_stage_from_titles(self, cv_data: Dict) -> Optional[str]:
        """Detect stage from job titles."""
        job_titles = cv_data.get("job_titles", [])
        if not job_titles:
            return None

        keywords = self.rules["rules"].get("job_title_keywords", {})

        for stage, keywords_list in keywords.items():
            for title in job_titles:
                title_lower = title.lower()
                if any(kw in title_lower for kw in keywords_list):
                    return stage

        return None

    def _detect_stage_from_education(self, cv_data: Dict) -> Optional[str]:
        """Detect stage from education signals."""
        education = cv_data.get("education", {})
        if not education:
            return None

        edu_text = str(education).lower()
        edu_signals = self.rules["rules"].get("education_signals", {})

        if "currently_studying" in edu_signals:
            indicators = edu_signals["currently_studying"]["indicators"]
            if any(ind in edu_text for ind in indicators):
                return "Student"

        if "recent_graduate" in edu_signals:
            indicators = edu_signals["recent_graduate"]["indicators"]
            if any(ind in edu_text for ind in indicators):
                return "Fresher"

        return None

    def _build_reason(self, exp_years: Optional[float], skill_depth: Dict, stage: str) -> str:
        """Build human-readable reason for stage detection."""
        parts = []

        if exp_years is not None:
            parts.append(f"{exp_years:.1f} năm kinh nghiệm")
        else:
            parts.append("không có thông tin kinh nghiệm")

        parts.append(f"{skill_depth['total_skills']} core skills")

        if skill_depth["advanced_skills"] > 0:
            parts.append(f"có {skill_depth['advanced_skills']} advanced skills")

        return " + ".join(parts)


if __name__ == "__main__":
    # Demo
    detector = StageDetector()

    # Test case 1: Student
    cv1 = {
        "work_history": [],
        "skills": ["Python", "SQL", "Machine Learning"],
        "education": "Đang học năm 4"
    }

    result1 = detector.detect(cv1)
    print(f"CV1: {result1.stage} (confidence: {result1.confidence:.2f})")
    print(f"Signals: {result1.signals}")
    print()

    # Test case 2: Fresher with advanced skills
    cv2 = {
        "work_history": [{"duration_months": 6}],
        "skills": ["Python", "LLM", "RAG", "LangChain", "Docker"],
    }

    result2 = detector.detect(cv2)
    print(f"CV2: {result2.stage} (confidence: {result2.confidence:.2f})")
    print(f"Signals: {result2.signals}")
    print()

    # Test case 3: Junior
    cv3 = {
        "work_history": [
            {"duration_months": 12},
            {"duration_months": 18}
        ],
        "skills": ["Python", "PyTorch", "Docker", "AWS"],
        "job_titles": ["Junior AI Engineer"]
    }

    result3 = detector.detect(cv3)
    print(f"CV3: {result3.stage} (confidence: {result3.confidence:.2f})")
    print(f"Signals: {result3.signals}")