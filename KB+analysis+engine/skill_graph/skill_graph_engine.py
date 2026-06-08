"""
Skill Graph Engine
Phân tích mối quan hệ giữa các kỹ năng và gợi ý lộ trình học tập.

Features:
- Query prerequisites cho một skill
- Tìm related skills (kỹ năng bổ trợ)
- Gợi ý learning path từ current skills đến target skill
- Phân tích skill clusters
- Suggest next skills dựa trên current skills và target role
"""
import json
from typing import Dict, List, Set, Optional, Tuple
from pathlib import Path


class SkillGraphEngine:
    """
    Engine để truy vấn và phân tích mối quan hệ giữa các kỹ năng.

    Graph Structure:
    - Nodes: Skills (Python, PyTorch, LLM, etc.)
    - Edges:
        * prerequisites: skills cần học trước
        * related: skills bổ trợ, thường đi cùng nhau
        * leads_to: skills có thể học tiếp theo

    Use Cases:
    - Learning path recommendation
    - Skill clustering
    - Career roadmap generation
    - "What should I learn next?" suggestions
    """

    def __init__(self, relationships_file: str = None):
        """
        Initialize Skill Graph Engine.

        Args:
            relationships_file: Path to skill_relationships.json
        """
        if relationships_file is None:
            # Default: same directory as this file
            relationships_file = Path(__file__).parent / "skill_relationships.json"

        self.relationships_file = Path(relationships_file)
        self._load_graph()

    def _load_graph(self):
        """Load skill relationships from JSON file."""
        if not self.relationships_file.exists():
            raise FileNotFoundError(
                f"Skill relationships file not found: {self.relationships_file}"
            )

        with open(self.relationships_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.skills = data.get("skills", {})
        self.skill_clusters = data.get("skill_clusters", {})

        # Build reverse indices for fast lookup
        self._build_indices()

    def _build_indices(self):
        """Build reverse indices for efficient queries."""
        # Index: skill -> which skills require it as prerequisite
        self.required_by = {}
        for skill, data in self.skills.items():
            for prereq in data.get("prerequisites", []):
                if prereq not in self.required_by:
                    self.required_by[prereq] = []
                self.required_by[prereq].append(skill)

        # Index: skill -> which skills it leads to
        self.leads_to_index = {}
        for skill, data in self.skills.items():
            self.leads_to_index[skill] = data.get("leads_to", [])

    def get_skill_info(self, skill: str) -> Optional[Dict]:
        """
        Get full information about a skill.

        Args:
            skill: Skill name (canonical)

        Returns:
            Skill data dict or None if not found
        """
        return self.skills.get(skill)

    def get_prerequisites(self, skill: str) -> List[str]:
        """
        Get skills that are prerequisites for the given skill.

        Args:
            skill: Target skill

        Returns:
            List of prerequisite skills
        """
        skill_data = self.skills.get(skill)
        if not skill_data:
            return []
        return skill_data.get("prerequisites", [])

    def get_all_prerequisites(self, skill: str, current_skills: Set[str] = None) -> List[str]:
        """
        Get ALL prerequisites (including transitive) that user doesn't have.

        Args:
            skill: Target skill
            current_skills: Skills user already has

        Returns:
            List of missing prerequisites (ordered by depth)
        """
        if current_skills is None:
            current_skills = set()

        missing = []
        visited = set()
        queue = [(skill, 0)]  # (skill, depth)

        while queue:
            current, depth = queue.pop(0)

            if current in visited:
                continue
            visited.add(current)

            prereqs = self.get_prerequisites(current)
            for prereq in prereqs:
                if prereq not in current_skills and prereq not in visited:
                    missing.append((prereq, depth + 1))
                    queue.append((prereq, depth + 1))

        # Sort by depth (shallowest first) and remove duplicates
        seen = set()
        result = []
        for prereq, depth in sorted(missing, key=lambda x: x[1]):
            if prereq not in seen:
                seen.add(prereq)
                result.append(prereq)

        return result

    def get_related_skills(self, skill: str) -> List[str]:
        """
        Get skills that are related to the given skill.

        Args:
            skill: Source skill

        Returns:
            List of related skills
        """
        skill_data = self.skills.get(skill)
        if not skill_data:
            return []
        return skill_data.get("related", [])

    def get_leads_to(self, skill: str) -> List[str]:
        """
        Get skills that this skill leads to (natural progression).

        Args:
            skill: Source skill

        Returns:
            List of skills that can be learned next
        """
        skill_data = self.skills.get(skill)
        if not skill_data:
            return []
        return skill_data.get("leads_to", [])

    def get_learning_path(
        self,
        target_skill: str,
        current_skills: Set[str] = None
    ) -> List[Dict]:
        """
        Generate a learning path from current skills to target skill.

        Args:
            target_skill: Skill user wants to learn
            current_skills: Skills user already has

        Returns:
            List of steps with skill name and reason
        """
        if current_skills is None:
            current_skills = set()

        # Get all missing prerequisites
        missing_prereqs = self.get_all_prerequisites(target_skill, current_skills)

        # Build learning path
        path = []

        # Add prerequisites
        for prereq in missing_prereqs:
            path.append({
                "skill": prereq,
                "reason": f"Prerequisite for {target_skill}",
                "type": "prerequisite"
            })

        # Add target skill
        path.append({
            "skill": target_skill,
            "reason": "Target skill",
            "type": "target"
        })

        return path

    def suggest_next_skills(
        self,
        current_skills: Set[str],
        target_role: str = None,
        max_suggestions: int = 5
    ) -> List[Dict]:
        """
        Suggest skills to learn next based on current skills.

        Strategy:
        1. Find skills that current skills lead to
        2. Filter out skills already known
        3. Prioritize skills with most prerequisites met

        Args:
            current_skills: Skills user already has
            target_role: Optional target role for context
            max_suggestions: Max number of suggestions

        Returns:
            List of suggested skills with scores
        """
        candidates = {}

        # For each current skill, find what it leads to
        for skill in current_skills:
            leads_to = self.get_leads_to(skill)
            for next_skill in leads_to:
                if next_skill not in current_skills:
                    if next_skill not in candidates:
                        candidates[next_skill] = {
                            "skill": next_skill,
                            "score": 0,
                            "prerequisites_met": [],
                            "prerequisites_missing": []
                        }

                    candidates[next_skill]["score"] += 1
                    candidates[next_skill]["prerequisites_met"].append(skill)

        # Check prerequisites for each candidate
        for skill_name, data in candidates.items():
            prereqs = self.get_prerequisites(skill_name)
            for prereq in prereqs:
                if prereq in current_skills:
                    if prereq not in data["prerequisites_met"]:
                        data["prerequisites_met"].append(prereq)
                else:
                    data["prerequisites_missing"].append(prereq)

            # Adjust score based on prerequisites
            total_prereqs = len(prereqs)
            if total_prereqs > 0:
                met_ratio = len(data["prerequisites_met"]) / total_prereqs
                data["score"] *= met_ratio

        # Sort by score and return top N
        sorted_candidates = sorted(
            candidates.values(),
            key=lambda x: x["score"],
            reverse=True
        )

        return sorted_candidates[:max_suggestions]

    def get_skill_cluster(self, skill: str) -> Optional[str]:
        """
        Get the cluster name for a skill.

        Args:
            skill: Skill name

        Returns:
            Cluster name or None
        """
        for cluster_name, skills in self.skill_clusters.items():
            if skill in skills:
                return cluster_name
        return None

    def get_cluster_skills(self, cluster_name: str) -> List[str]:
        """
        Get all skills in a cluster.

        Args:
            cluster_name: Name of the cluster

        Returns:
            List of skills in the cluster
        """
        return self.skill_clusters.get(cluster_name, [])

    def analyze_skill_coverage(
        self,
        current_skills: Set[str],
        target_cluster: str = None
    ) -> Dict:
        """
        Analyze how well current skills cover a cluster or all clusters.

        Args:
            current_skills: Skills user has
            target_cluster: Optional specific cluster to analyze

        Returns:
            Coverage analysis with stats
        """
        if target_cluster:
            clusters_to_analyze = {target_cluster: self.skill_clusters.get(target_cluster, [])}
        else:
            clusters_to_analyze = self.skill_clusters

        analysis = {}

        for cluster_name, cluster_skills in clusters_to_analyze.items():
            owned = [s for s in cluster_skills if s in current_skills]
            missing = [s for s in cluster_skills if s not in current_skills]

            coverage = len(owned) / len(cluster_skills) if cluster_skills else 0

            analysis[cluster_name] = {
                "total_skills": len(cluster_skills),
                "owned_skills": owned,
                "missing_skills": missing,
                "coverage_percent": round(coverage * 100, 2)
            }

        return analysis

    def get_skill_dependencies_graph(self, skills: List[str]) -> Dict:
        """
        Build a dependency graph for a set of skills.

        Args:
            skills: List of skills to analyze

        Returns:
            Graph structure with nodes and edges
        """
        nodes = []
        edges = []

        for skill in skills:
            if skill in self.skills:
                nodes.append({
                    "id": skill,
                    "category": self.skills[skill].get("category", "Unknown")
                })

                # Add prerequisite edges
                for prereq in self.get_prerequisites(skill):
                    if prereq in skills:
                        edges.append({
                            "from": prereq,
                            "to": skill,
                            "type": "prerequisite"
                        })

                # Add related edges
                for related in self.get_related_skills(skill):
                    if related in skills:
                        edges.append({
                            "from": skill,
                            "to": related,
                            "type": "related"
                        })

        return {
            "nodes": nodes,
            "edges": edges
        }


if __name__ == "__main__":
    # Demo: Skill Graph Engine
    print("=" * 70)
    print("SKILL GRAPH ENGINE DEMO")
    print("=" * 70)
    print()

    # Initialize engine
    engine = SkillGraphEngine()

    # Test 1: Get prerequisites
    print("[TEST 1] Prerequisites for LLM:")
    prereqs = engine.get_prerequisites("LLM")
    print(f"  Direct prerequisites: {prereqs}")
    print()

    # Test 2: Get all prerequisites (transitive)
    print("[TEST 2] All prerequisites for LLM (user has Python):")
    all_prereqs = engine.get_all_prerequisites("LLM", current_skills={"Python"})
    print(f"  Missing prerequisites: {all_prereqs}")
    print()

    # Test 3: Learning path
    print("[TEST 3] Learning path to LLM (user has Python, SQL):")
    path = engine.get_learning_path("LLM", current_skills={"Python", "SQL"})
    for step in path:
        print(f"  - {step['skill']}: {step['reason']}")
    print()

    # Test 4: Suggest next skills
    print("[TEST 4] Suggest next skills (user has Python, Machine Learning):")
    suggestions = engine.suggest_next_skills(
        current_skills={"Python", "Machine Learning"},
        max_suggestions=5
    )
    for sugg in suggestions:
        print(f"  - {sugg['skill']} (score: {sugg['score']:.2f})")
        print(f"    Prerequisites met: {sugg['prerequisites_met']}")
        print(f"    Prerequisites missing: {sugg['prerequisites_missing']}")
    print()

    # Test 5: Skill cluster analysis
    print("[TEST 5] Analyze skill coverage (user has Python, PyTorch):")
    coverage = engine.analyze_skill_coverage(
        current_skills={"Python", "PyTorch"},
        target_cluster="Generative AI Stack"
    )
    for cluster, stats in coverage.items():
        print(f"  Cluster: {cluster}")
        print(f"    Coverage: {stats['coverage_percent']}%")
        print(f"    Owned: {stats['owned_skills']}")
        print(f"    Missing: {stats['missing_skills']}")
    print()

    print("=" * 70)
    print("[DONE] Skill Graph Engine demo complete")
