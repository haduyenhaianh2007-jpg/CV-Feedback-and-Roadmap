"""
Role-aware Graph Pruning Engine

Cб»‘t lГөi: Extract optimal subgraph for a job role
Input: full_master_graph, target_role, user_profile (optional), market_signals
Output: role_pruned_graph (clean DAG) + node_scores + pruning_report

Scoring model:
score(node) = role_relevance * market_demand * graph_centrality * prerequisite_importance
"""
import json
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
import math


@dataclass
class NodeScore:
    """Score breakdown for a skill node."""
    skill: str
    total_score: float
    role_relevance: float
    market_demand: float
    centrality: float
    prerequisite_boost: float
    depth: int


@dataclass
class PruningReport:
    """Report of pruning operation."""
    original_nodes: int
    pruned_nodes: int
    removed_nodes: List[Dict]
    statistics: Dict


class RoleAwarePruner:
    """
    Prune full skill graph to role-specific subgraph.

    Strategy:
    1. Hard filter: remove nodes with role_relevance < threshold
    2. Soft ranking: sort remaining by final_score
    3. Keep top-K per depth layer
    4. Dependency preservation: if node kept, must include all prerequisites
    """

    def __init__(self, skill_graph_engine):
        """
        Initialize pruner.

        Args:
            skill_graph_engine: SkillGraphEngine with prerequisite data
        """
        self.graph = skill_graph_engine

        # Default role relevance scores (can be overridden from role_matrix)
        self.role_relevance_defaults = {
            # Core AI/ML skills
            "Python": 0.95,
            "Machine Learning": 0.95,
            "Deep Learning": 0.92,
            "Natural Language Processing": 0.85,
            "LLM": 1.0,
            "RAG": 0.95,
            "LangChain": 0.85,
            "PyTorch": 0.90,
            "TensorFlow": 0.85,
            "Computer Vision": 0.75,
            "Prompt Engineering": 0.80,
            "Vector Database": 0.80,
            "Attention": 0.75,
            "Transformer": 0.85,
            "Embedding": 0.75,
            "Tokenization": 0.70,

            # Data skills
            "SQL": 0.70,
            "Data Processing": 0.70,
            "Pandas": 0.65,
            "NumPy": 0.65,

            # MLOps/Production
            "Docker": 0.70,
            "Kubernetes": 0.60,
            "MLOps": 0.65,
            "Model Deployment": 0.65,
            "Evaluation": 0.60,
            "CI/CD": 0.50,

            # Low relevance (filtered out)
            "React": 0.10,
            "Angular": 0.05,
            "C#": 0.10,
            "Scala": 0.15,
            "Java": 0.20,
            "Excel": 0.15,
            "Jira": 0.10,
            "Agile": 0.15,
            "Scrum": 0.10,
            "CSS": 0.05,
            "HTML": 0.05,
            "JavaScript": 0.10,
            "TypeScript": 0.10,
            "Go": 0.15,
            "Cassandra": 0.20,
            "Elasticsearch": 0.25,
            "MongoDB": 0.20,
            "PostgreSQL": 0.30,
            "Microservices": 0.25,
            "System Design": 0.40,
            "REST API": 0.35,
            "AWS": 0.50,
            "Azure": 0.40,
            "Git": 0.30,
            "GitHub": 0.30,
        }

        # Market demand factors
        self.market_factors = {
            "LLM": 1.4,
            "RAG": 1.3,
            "LangChain": 1.3,
            "PyTorch": 1.2,
            "Kubernetes": 1.1,
            "Docker": 1.0,
            "Python": 1.0,
            "SQL": 0.9,
            "Machine Learning": 1.1,
            "Deep Learning": 1.2,
        }

        # Configuration
        self.relevance_threshold = 0.2  # Hard filter
        self.max_nodes_per_depth = 8    # Keep top 8 per depth level

    def get_role_relevance(self, skill: str, role_matrix: Dict = None) -> float:
        """
        Get role relevance score for a skill.

        Priority:
        1. From role_matrix frequency (if provided)
        2. From defaults
        3. Default 0.1 (low relevance)
        """
        # Try role_matrix first (frequency / 100)
        if role_matrix and skill in role_matrix:
            return role_matrix[skill].get("frequency", 50) / 100.0

        # Fallback to defaults
        return self.role_relevance_defaults.get(skill, 0.1)

    def get_market_demand(self, skill: str) -> float:
        """Get market demand multiplier."""
        return self.market_factors.get(skill, 0.8)

    def compute_centrality(self, skill: str, all_skills: Set[str]) -> float:
        """
        Compute graph centrality (how many other skills depend on this).
        Higher centrality = more important.
        """
        # Count how many skills have this as prerequisite
        dependent_count = 0
        for other in all_skills:
            prereqs = self.graph.get_prerequisites(other) if hasattr(self.graph, 'get_prerequisites') else []
            if skill in prereqs:
                dependent_count += 1

        max_possible = len(all_skills) - 1 if len(all_skills) > 1 else 1
        return dependent_count / max_possible if max_possible > 0 else 0

    def compute_depth(self, skill: str, current_skills: Set[str]) -> int:
        """
        Compute topological depth (minimum steps from current skills).
        """
        if skill in current_skills:
            return 0

        # BFS to find shortest path from any current skill
        visited = set()
        queue = deque([(skill, 0)])

        while queue:
            current, depth = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            if current in current_skills:
                return depth

            prereqs = self.graph.get_prerequisites(current) if hasattr(self.graph, 'get_prerequisites') else []
            for prereq in prereqs:
                if prereq not in visited:
                    queue.append((prereq, depth + 1))

        return 999  # Very deep (no path from current skills)

    def compute_prerequisite_boost(self, skill: str, all_skills: Set[str], role_skills: Set[str]) -> float:
        """
        Boost score if skill is prerequisite for high-value role skills.
        """
        # Find which role skills depend on this skill
        dependent_role_skills = []
        for role_skill in role_skills:
            prereqs = self.graph.get_prerequisites(role_skill) if hasattr(self.graph, 'get_prerequisites') else []
            if skill in prereqs:
                dependent_role_skills.append(role_skill)

        if not dependent_role_skills:
            return 1.0

        # Boost based on how many and how important
        boost = 1.0 + (len(dependent_role_skills) * 0.1)
        return min(boost, 1.5)  # Cap at 1.5x

    def compute_node_score(
        self,
        skill: str,
        all_skills: Set[str],
        role_skills: Set[str],
        current_skills: Set[str],
        role_matrix: Dict = None
    ) -> NodeScore:
        """Compute complete score for a skill node."""

        role_relevance = self.get_role_relevance(skill, role_matrix)
        market_demand = self.get_market_demand(skill)
        centrality = self.compute_centrality(skill, all_skills)
        prerequisite_boost = self.compute_prerequisite_boost(skill, all_skills, role_skills)
        depth = self.compute_depth(skill, current_skills)

        # Total score = product of all factors
        total_score = role_relevance * market_demand * centrality * prerequisite_boost

        # Boost if low depth (easier to learn)
        if depth < 2:
            total_score *= 1.2

        return NodeScore(
            skill=skill,
            total_score=round(total_score, 4),
            role_relevance=round(role_relevance, 3),
            market_demand=round(market_demand, 3),
            centrality=round(centrality, 3),
            prerequisite_boost=round(prerequisite_boost, 3),
            depth=depth
        )

    def prune(
        self,
        full_graph: Dict,
        target_role: str,
        current_skills: List[str] = None,
        role_matrix: Dict = None,
        max_nodes_per_depth: int = None
    ) -> Dict:
        """
        Prune full graph to role-specific subgraph.

        Args:
            full_graph: Dict with 'nodes' and 'edges'
            target_role: Target job role (e.g., "AI Engineer")
            current_skills: Skills user already has
            role_matrix: Role matrix from SkillGapEngine
            max_nodes_per_depth: Override default max nodes per depth

        Returns:
            Dict with pruned_graph, node_scores, removed_nodes, statistics
        """
        if current_skills is None:
            current_skills = []

        if max_nodes_per_depth is not None:
            self.max_nodes_per_depth = max_nodes_per_depth

        current_set = set(current_skills)

        # Extract all skill names from graph
        all_skills = set()
        skill_info = {}

        for node in full_graph.get("nodes", []):
            skill_name = node.get("id", node.get("skill", node.get("name", "")))
            if skill_name:
                all_skills.add(skill_name)
                skill_info[skill_name] = node

        # Define role skills (high relevance)
        role_skills = set()
        for skill in all_skills:
            relevance = self.get_role_relevance(skill, role_matrix)
            if relevance >= self.relevance_threshold:
                role_skills.add(skill)

        # Compute scores for all skills
        node_scores = []
        for skill in all_skills:
            score = self.compute_node_score(
                skill=skill,
                all_skills=all_skills,
                role_skills=role_skills,
                current_skills=current_set,
                role_matrix=role_matrix
            )
            node_scores.append(score)

        # Hard filter: remove low relevance nodes
        kept_skills = set()
        removed_nodes = []

        for score in node_scores:
            if score.role_relevance >= self.relevance_threshold:
                kept_skills.add(score.skill)
            else:
                removed_nodes.append({
                    "id": score.skill,
                    "reason": f"low_role_relevance ({score.role_relevance})",
                    "score": score.role_relevance
                })

        # Group kept skills by depth
        depth_groups = defaultdict(list)
        for score in node_scores:
            if score.skill in kept_skills:
                depth_groups[score.depth].append(score)

        # Soft ranking: keep top-K per depth
        final_kept = set()
        for depth, scores in depth_groups.items():
            # Sort by total_score descending
            sorted_scores = sorted(scores, key=lambda x: x.total_score, reverse=True)
            top_k = sorted_scores[:self.max_nodes_per_depth]
            for score in top_k:
                final_kept.add(score.skill)

        # Dependency preservation: if node kept, must include all prerequisites
        expanded_kept = set(final_kept)
        for skill in list(final_kept):
            prereqs = self.graph.get_prerequisites(skill) if hasattr(self.graph, 'get_prerequisites') else []
            for prereq in prereqs:
                if prereq in all_skills:
                    expanded_kept.add(prereq)

        # Build pruned graph
        pruned_nodes = []
        for node in full_graph.get("nodes", []):
            skill_name = node.get("id", node.get("skill", node.get("name", "")))
            if skill_name in expanded_kept:
                pruned_nodes.append(node)

        pruned_edges = []
        for edge in full_graph.get("edges", []):
            from_skill = edge.get("from", "")
            to_skill = edge.get("to", "")
            if from_skill in expanded_kept and to_skill in expanded_kept:
                pruned_edges.append(edge)

        # Prepare final node scores for output
        output_scores = []
        for score in node_scores:
            if score.skill in expanded_kept:
                output_scores.append({
                    "id": score.skill,
                    "score": score.total_score,
                    "components": {
                        "role_relevance": score.role_relevance,
                        "market": score.market_demand,
                        "centrality": score.centrality,
                        "prerequisite_boost": score.prerequisite_boost
                    },
                    "depth": score.depth
                })

        # Statistics
        statistics = {
            "original_nodes": len(all_skills),
            "pruned_nodes": len(expanded_kept),
            "removed_nodes_count": len(removed_nodes),
            "reduction_ratio": round(1 - (len(expanded_kept) / len(all_skills) if all_skills else 0), 3),
            "kept_by_relevance": len(kept_skills),
            "kept_by_dependency": len(expanded_kept - final_kept)
        }

        return {
            "pruned_graph": {
                "nodes": pruned_nodes,
                "edges": pruned_edges
            },
            "node_scores": output_scores,
            "removed_nodes": removed_nodes,
            "statistics": statistics
        }


if __name__ == "__main__":
    print("RoleAwarePruner module loaded")

    # Quick test with mock data
    class MockGraph:
        def get_prerequisites(self, skill):
            mock_prereqs = {
                "LLM": ["Deep Learning", "NLP"],
                "Deep Learning": ["Machine Learning"],
                "Machine Learning": ["Python", "SQL"],
                "RAG": ["LLM"],
                "Python": [],
                "SQL": [],
                "React": [],
            }
            return mock_prereqs.get(skill, [])

    mock_graph = MockGraph()
    pruner = RoleAwarePruner(mock_graph)

    mock_full_graph = {
        "nodes": [
            {"id": "Python"}, {"id": "SQL"}, {"id": "Machine Learning"},
            {"id": "Deep Learning"}, {"id": "NLP"}, {"id": "LLM"},
            {"id": "RAG"}, {"id": "React"}, {"id": "Angular"}, {"id": "C#"}
        ],
        "edges": []
    }

    result = pruner.prune(
        full_graph=mock_full_graph,
        target_role="AI Engineer",
        current_skills=["Python"]
    )

    print(f"Statistics: {result['statistics']}")
    print(f"Kept nodes: {[n['id'] for n in result['pruned_graph']['nodes']]}")
