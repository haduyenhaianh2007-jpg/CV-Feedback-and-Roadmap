"""
Graph Weighting System - Extends skill graph with weighted metadata

Each skill node gains:
- difficulty: 1-10 scale
- market_weight: multiplier for market demand
- ats_impact: expected ATS percentage gain when mastered
- centrality_score: importance in the graph (0-1)
"""
from typing import Dict, List, Set, Optional
from collections import defaultdict


class GraphWeightingSystem:
    """
    Weighted Skill Graph for advanced roadmap optimization.

    Provides methods to compute:
    - Node centrality (how important a skill is)
    - Learning path optimization based on weighted gain
    - Market-adjusted skill prioritization
    """

    def __init__(self, skill_graph_engine):
        """
        Initialize weighting system.

        Args:
            skill_graph_engine: SkillGraphEngine instance
        """
        self.graph = skill_graph_engine
        self._load_weights()

    def _load_weights(self):
        """Load skill weights from configuration."""
        # Default weights - can be extended via JSON
        self.weights = {
            "difficulty": {
                "Python": 2,
                "SQL": 2,
                "Machine Learning": 4,
                "Deep Learning": 5,
                "Natural Language Processing": 5,
                "LLM": 6,
                "RAG": 6,
                "Docker": 3,
                "Kubernetes": 5,
                "PyTorch": 4,
                "Computer Vision": 5,
                "Prompt Engineering": 3,
                "Vector Database": 4,
                "LangChain": 4,
                "Attention": 5,
                "Transformer": 6,
                "MLOps": 6,
                "Data Processing": 3,
                "Model Deployment": 5,
                "Evaluation": 4
            },
            "market_weight": {
                "LLM": 1.4,
                "RAG": 1.3,
                "LangChain": 1.3,
                "PyTorch": 1.2,
                "Kubernetes": 1.2,
                "AWS": 1.15,
                "Docker": 1.1,
                "TensorFlow": 1.1,
                "Python": 1.0,
                "SQL": 1.0,
                "Machine Learning": 1.1,
                "Deep Learning": 1.2
            },
            "ats_impact": {
                "Python": 8,
                "SQL": 5,
                "Machine Learning": 12,
                "Deep Learning": 10,
                "LLM": 18,
                "RAG": 15,
                "Docker": 6,
                "Kubernetes": 8,
                "PyTorch": 10,
                "Computer Vision": 7,
                "NLP": 9
            }
        }

    def get_difficulty(self, skill: str) -> int:
        """Get difficulty level (1-10)."""
        return self.weights["difficulty"].get(skill, 3)

    def get_market_weight(self, skill: str) -> float:
        """Get market weight multiplier."""
        return self.weights["market_weight"].get(skill, 1.0)

    def get_ats_impact(self, skill: str) -> int:
        """Get expected ATS percentage gain."""
        return self.weights["ats_impact"].get(skill, 5)

    def compute_centrality(self, skill: str, skills_set: Set[str]) -> float:
        """
        Compute graph centrality for a skill within a set.
        Higher centrality = more important for the skill graph.
        """
        if not skills_set:
            return 0.0

        # Get all nodes in the subgraph
        all_skills = list(skills_set)

        # Simple degree centrality within the skill set
        degree = 0
        prereqs = self.graph.get_prerequisites(skill) if hasattr(self.graph, 'get_prerequisites') else []
        leads_to = self.graph.get_leads_to(skill) if hasattr(self.graph, 'get_leads_to') else []

        for p in prereqs:
            if p in skills_set:
                degree += 1
        for l in leads_to:
            if l in skills_set:
                degree += 1

        max_possible = len(all_skills) - 1 if len(all_skills) > 1 else 1
        return degree / max_possible if max_possible > 0 else 0

    def compute_priority_score(self, skill: str, skills_set: Set[str], is_missing: bool = True) -> float:
        """
        Compute overall priority score for learning a skill.

        Higher score = higher priority to learn.

        Formula:
        priority = (market_weight × 0.4) + (ats_impact / 100 × 0.3) + (centrality × 0.2) + (difficulty_penalty)
        where difficulty_penalty = 1 / (difficulty/5) for missing, higher for lower difficulty
        """
        market_w = self.get_market_weight(skill)
        ats_impact = self.get_ats_impact(skill) / 100  # Normalize to 0-1
        centrality = self.compute_centrality(skill, skills_set)

        # Difficulty: lower difficulty = higher priority for missing skills
        difficulty = self.get_difficulty(skill)
        if is_missing:
            difficulty_factor = 1 / (difficulty / 3)  # Easier skills get higher factor
            difficulty_factor = min(1.5, difficulty_factor)
        else:
            difficulty_factor = 1.0

        score = (market_w * 0.4) + (ats_impact * 0.3) + (centrality * 0.2) + (difficulty_factor * 0.1)
        return round(score, 3)

    def prioritize_skills(self, missing_skills: List[str], skills_set: Set[str]) -> List[Dict]:
        """
        Prioritize missing skills by computed priority score.

        Returns:
            List of dicts with skill, priority_score, and breakdown
        """
        results = []
        for skill in missing_skills:
            results.append({
                "skill": skill,
                "priority_score": self.compute_priority_score(skill, skills_set, is_missing=True),
                "difficulty": self.get_difficulty(skill),
                "market_weight": self.get_market_weight(skill),
                "ats_impact": self.get_ats_impact(skill),
                "centrality": self.compute_centrality(skill, skills_set)
            })

        return sorted(results, key=lambda x: x["priority_score"], reverse=True)

    def get_skill_metadata(self, skill: str) -> Dict:
        """Get all metadata for a skill."""
        return {
            "id": skill,
            "difficulty": self.get_difficulty(skill),
            "market_weight": self.get_market_weight(skill),
            "ats_impact": self.get_ats_impact(skill)
        }


if __name__ == "__main__":
    print("GraphWeightingSystem module loaded")
