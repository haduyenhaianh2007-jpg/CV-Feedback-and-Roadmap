"""
Project Templates - Rule-based project suggestion system

Selects appropriate projects for each roadmap phase based on:
- Phase skills
- User career stage
- Project difficulty matching
"""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ProjectSuggestion:
    """Suggested project for a roadmap phase"""
    name: str
    difficulty: str
    primary_skills: List[str]
    tech_stack: List[str]
    deliverables: List[str]
    learning_outcomes: List[str]
    estimated_hours: int
    match_score: float

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "difficulty": self.difficulty,
            "primary_skills": self.primary_skills,
            "tech_stack": self.tech_stack,
            "deliverables": self.deliverables,
            "learning_outcomes": self.learning_outcomes,
            "estimated_hours": self.estimated_hours
        }


class ProjectPool:
    """
    Rule-based project selection system.

    Selects projects from a predefined pool based on:
    - Skill overlap with phase requirements
    - Difficulty appropriate for user's career stage
    - Estimated hours alignment
    """

    def __init__(self, pool_file: Optional[str] = None):
        """
        Initialize project pool.

        Args:
            pool_file: Path to project_pool.json (optional)
        """
        if pool_file is None:
            pool_file = Path(__file__).parent / "data" / "project_pool.json"

        self.pool_file = Path(pool_file)
        self._load_pool()

    def _load_pool(self):
        """Load project pool from JSON file."""
        if not self.pool_file.exists():
            self.projects = {}
            self.selection_strategy = {}
            return

        with open(self.pool_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.projects = data.get("projects", {})
        self.selection_strategy = data.get("selection_strategy", {})

    def select(
        self,
        phase_skills: List[str],
        stage: str,
        max_suggestions: int = 3
    ) -> List[ProjectSuggestion]:
        """
        Select appropriate projects for a roadmap phase.

        Args:
            phase_skills: List of skills to be learned in this phase
            stage: User's career stage (Student/Fresher/Junior/Middle)
            max_suggestions: Maximum number of project suggestions

        Returns:
            List of ProjectSuggestion objects, sorted by match score
        """
        if not self.projects:
            return []

        candidates = []
        match_threshold = self.selection_strategy.get("match_threshold", 0.5)

        for project_name, project_data in self.projects.items():
            # Check if difficulty is appropriate for stage
            if not self._is_difficulty_appropriate(project_data, stage):
                continue

            # Calculate skill match score
            match_score = self._calculate_match_score(
                phase_skills, project_data["primary_skills"]
            )

            if match_score >= match_threshold:
                candidates.append(ProjectSuggestion(
                    name=project_name,
                    difficulty=project_data["difficulty"],
                    primary_skills=project_data["primary_skills"],
                    tech_stack=project_data["tech_stack"],
                    deliverables=project_data["deliverables"],
                    learning_outcomes=project_data["learning_outcomes"],
                    estimated_hours=project_data["estimated_hours"],
                    match_score=match_score
                ))

        # Sort by match score descending
        candidates.sort(key=lambda x: x.match_score, reverse=True)

        return candidates[:max_suggestions]

    def select_best(
        self,
        phase_skills: List[str],
        stage: str
    ) -> Optional[ProjectSuggestion]:
        """
        Select the single best project for a roadmap phase.

        Args:
            phase_skills: List of skills to be learned in this phase
            stage: User's career stage

        Returns:
            Best matching ProjectSuggestion or None if no match
        """
        suggestions = self.select(phase_skills, stage, max_suggestions=1)
        return suggestions[0] if suggestions else None

    def _is_difficulty_appropriate(self, project_data: Dict, stage: str) -> bool:
        """Check if project difficulty is appropriate for career stage."""
        difficulty_mapping = self.selection_strategy.get("difficulty_mapping", {})

        project_difficulty = project_data.get("difficulty", "Intermediate")
        suitable_stages = project_data.get("suitable_stages", ["Fresher", "Junior"])

        # Check if stage is in suitable stages
        if stage in suitable_stages:
            return True

        # Fallback to difficulty mapping
        allowed_difficulties = difficulty_mapping.get(stage, ["Intermediate"])
        return project_difficulty in allowed_difficulties

    def _calculate_match_score(
        self,
        phase_skills: List[str],
        project_skills: List[str]
    ) -> float:
        """
        Calculate skill match score between phase and project.

        Score = (number of matching skills) / (total unique skills)
        """
        phase_set = set(s.lower() for s in phase_skills)
        project_set = set(s.lower() for s in project_skills)

        if not project_set:
            return 0.0

        matches = phase_set & project_set
        total = phase_set | project_set

        return len(matches) / len(total) if total else 0.0

    def get_all_projects(self) -> Dict[str, Dict]:
        """Get all projects in the pool."""
        return self.projects

    def get_project_by_name(self, name: str) -> Optional[Dict]:
        """Get a specific project by name."""
        return self.projects.get(name)


if __name__ == "__main__":
    # Demo
    pool = ProjectPool()

    # Test case 1: Phase with SQL + ML
    phase1_skills = ["SQL", "Machine Learning"]
    stage = "Student"

    suggestions = pool.select(phase1_skills, stage, max_suggestions=3)
    print(f"Phase skills: {phase1_skills}")
    print(f"Stage: {stage}")
    print(f"Suggestions: {len(suggestions)}")

    for i, proj in enumerate(suggestions, 1):
        print(f"\n{i}. {proj.name}")
        print(f"   Difficulty: {proj.difficulty}")
        print(f"   Match score: {proj.match_score:.2f}")
        print(f"   Tech stack: {', '.join(proj.tech_stack)}")
        print(f"   Hours: {proj.estimated_hours}")

    print("\n" + "="*70)

    # Test case 2: Phase with LLM + RAG
    phase2_skills = ["LLM", "RAG"]
    stage = "Junior"

    suggestions2 = pool.select(phase2_skills, stage, max_suggestions=2)
    print(f"\nPhase skills: {phase2_skills}")
    print(f"Stage: {stage}")
    print(f"Suggestions: {len(suggestions2)}")

    for i, proj in enumerate(suggestions2, 1):
        print(f"\n{i}. {proj.name}")
        print(f"   Match score: {proj.match_score:.2f}")