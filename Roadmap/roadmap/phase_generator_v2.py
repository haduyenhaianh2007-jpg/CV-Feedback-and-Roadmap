"""
Phase Generator V2 - Graph Clustering + Topo-aware Phase Builder

Upgraded from heuristic 2-phase to dynamic multi-phase generation:
1. Topological sort of skill graph based on prerequisites
2. Group nodes by dependency depth, skill weight, and ATS impact
3. Apply constraints: 3-6 skills per phase, prerequisites in earlier phases
4. Balance effort across phases
"""
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque
import math


class PhaseGeneratorV2:
    """Dynamic phase generator using graph clustering and topological ordering."""

    def __init__(self, skill_graph_engine, market_weights: Dict[str, float] = None):
        """
        Initialize phase generator.

        Args:
            skill_graph_engine: SkillGraphEngine instance with prerequisite data
            market_weights: Optional dict of skill -> market weight multiplier
        """
        self.graph = skill_graph_engine
        self.market_weights = market_weights or {}
        self.max_skills_per_phase = 5
        self.min_skills_per_phase = 2
        self.max_phases = 6

    def generate_phases(
        self,
        missing_skills: List[str],
        current_skills: List[str],
        target_role: str = None,
        max_skills_per_phase: int = 5,
        min_skills_per_phase: int = 2,
        max_phases: int = 6
    ) -> List[Dict]:
        """
        Generate optimized learning phases from missing skills.

        Args:
            missing_skills: Skills the user needs to learn
            current_skills: Skills the user already has
            target_role: Optional target role for context
            max_skills_per_phase: Max skills per phase (default 5)
            min_skills_per_phase: Min skills per phase (default 2)
            max_phases: Max number of phases (default 6)

        Returns:
            List of phases with phase_id, title, skills, reason, avg_depth
        """
        self.max_skills_per_phase = max_skills_per_phase
        self.min_skills_per_phase = min_skills_per_phase
        self.max_phases = max_phases

        # Step 1: Expand missing skills to include all prerequisites
        all_nodes = set(missing_skills)
        for skill in missing_skills:
            prereqs = self._collect_all_prerequisites(skill, current_skills)
            all_nodes.update(prereqs)

        # Filter out already mastered skills
        current_set = set(current_skills)
        nodes_to_learn = [s for s in all_nodes if s not in current_set]

        if not nodes_to_learn:
            return []

        # Step 2: Compute topological depth (longest path from current skills)
        depth_map = self._compute_depths(nodes_to_learn, current_set)

        # Step 3: Group by depth
        depth_groups = defaultdict(list)
        for skill in nodes_to_learn:
            depth_groups[depth_map.get(skill, 0)].append(skill)

        # Step 4: Weight each group by market demand and depth
        weighted_groups = self._weight_groups(depth_groups)

        # Step 5: Cluster into balanced phases
        phases = self._cluster_into_phases(weighted_groups)

        # Step 6: Enrich with metadata
        return self._enrich_phases(phases, depth_map)

    def _collect_all_prerequisites(self, skill: str, current_skills: List[str]) -> List[str]:
        """Collect all prerequisites not already mastered."""
        all_prereqs = []
        visited = set()
        queue = [skill]
        current_set = set(current_skills)

        while queue:
            s = queue.pop(0)
            if s in visited:
                continue
            visited.add(s)
            prereqs = self.graph.get_prerequisites(s) if hasattr(self.graph, 'get_prerequisites') else []
            for p in prereqs:
                if p not in current_set and p not in visited:
                    all_prereqs.append(p)
                    queue.append(p)
        return all_prereqs

    def _compute_depths(self, nodes: List[str], current_skills: Set[str]) -> Dict[str, int]:
        """Compute topological depth for each node (longest path from current skills)."""
        depths = {s: 0 for s in nodes}

        # Build reverse graph for propagation
        reverse_graph = defaultdict(list)
        for skill in nodes:
            prereqs = self.graph.get_prerequisites(skill) if hasattr(self.graph, 'get_prerequisites') else []
            for p in prereqs:
                if p in nodes or p in current_skills:
                    reverse_graph[p].append(skill)

        # Start from current skills (depth 0)
        queue = deque()
        for skill in current_skills:
            queue.append(skill)

        while queue:
            current = queue.popleft()
            current_depth = depths.get(current, 0)
            for next_skill in reverse_graph.get(current, []):
                if next_skill in nodes:
                    new_depth = current_depth + 1
                    if new_depth > depths.get(next_skill, 0):
                        depths[next_skill] = new_depth
                        queue.append(next_skill)

        return depths

    def _weight_groups(self, depth_groups: Dict[int, List[str]]) -> List[Tuple[int, float, List[str]]]:
        """Assign weight to each skill based on market demand and depth."""
        weighted = []
        for depth, skills in depth_groups.items():
            total_weight = 0.0
            for skill in skills:
                market_w = self.market_weights.get(skill, 1.0)
                depth_contrib = min(1.0, depth / 10.0)
                total_weight += market_w * (1 + depth_contrib)
            weighted.append((depth, total_weight, skills))
        return sorted(weighted, key=lambda x: x[0])  # Sort by depth

    def _cluster_into_phases(self, weighted_groups: List[Tuple[int, float, List[str]]]) -> List[List[str]]:
        """Cluster depth groups into balanced phases."""
        # Flatten all skills preserving depth order
        all_skills = []
        for _, _, skills in weighted_groups:
            all_skills.extend(skills)

        total_skills = len(all_skills)
        if total_skills == 0:
            return []

        target_phase_count = min(self.max_phases, max(1, math.ceil(total_skills / self.max_skills_per_phase)))
        skills_per_phase = max(self.min_skills_per_phase, math.ceil(total_skills / target_phase_count))

        phases = []
        for i in range(0, total_skills, skills_per_phase):
            phase_skills = all_skills[i:i + skills_per_phase]
            if phase_skills:
                phases.append(phase_skills)

        # Ensure prerequisites are in earlier phases
        phases = self._validate_prereqs(phases)
        return phases

    def _validate_prereqs(self, phases: List[List[str]]) -> List[List[str]]:
        """Ensure no skill appears before its prerequisites."""
        skill_to_phase = {}
        for idx, phase_skills in enumerate(phases):
            for skill in phase_skills:
                skill_to_phase[skill] = idx

        # Check and fix violations
        modified = True
        while modified:
            modified = False
            for idx, phase_skills in enumerate(phases):
                for skill in phase_skills[:]:
                    prereqs = self.graph.get_prerequisites(skill) if hasattr(self.graph, 'get_prerequisites') else []
                    for prereq in prereqs:
                        if prereq in skill_to_phase and skill_to_phase[prereq] > idx:
                            # Move skill to a later phase
                            if idx + 1 < len(phases):
                                phases[idx + 1].append(skill)
                            else:
                                phases.append([skill])
                            phase_skills.remove(skill)
                            modified = True
                            # Update skill_to_phase
                            for new_idx, new_skills in enumerate(phases):
                                for s in new_skills:
                                    skill_to_phase[s] = new_idx
                            break
                    if modified:
                        break
                if modified:
                    break
        return phases

    def _enrich_phases(self, phases: List[List[str]], depth_map: Dict[str, int]) -> List[Dict]:
        """Add titles, reasons, and metadata to each phase."""
        phase_titles = [
            "Nền tảng cơ bản",
            "Kỹ năng cốt lõi",
            "Phát triển chuyên sâu",
            "Kỹ năng nâng cao",
            "Production-ready",
            "Tối ưu & Mở rộng"
        ]

        enriched = []
        for idx, skills in enumerate(phases):
            if not skills:
                continue

            avg_depth = sum(depth_map.get(s, 0) for s in skills) / len(skills)

            enriched.append({
                "phase_id": idx + 1,
                "title": phase_titles[idx] if idx < len(phase_titles) else f"Phase {idx + 1}",
                "skills": skills,
                "avg_depth": round(avg_depth, 2),
                "skill_count": len(skills),
                "reason": self._generate_phase_reason(skills, avg_depth)
            })

        return enriched

    def _generate_phase_reason(self, skills: List[str], avg_depth: float) -> str:
        """Generate reason for phase grouping."""
        if avg_depth < 1:
            return "Kiến thức nền tảng, làm quen với các khái niệm cơ bản"
        elif avg_depth < 2:
            return "Kỹ năng cốt lõi, xây dựng nền tảng vững chắc"
        elif avg_depth < 3:
            return "Phát triển chuyên sâu, áp dụng vào dự án thực tế"
        else:
            return "Kỹ năng nâng cao, tối ưu và mở rộng hệ thống"


if __name__ == "__main__":
    # Quick test
    print("PhaseGeneratorV2 module loaded")
