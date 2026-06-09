"""
Hard Constraint Phase Builder (no duplication DAG partition)

Thay vì depth-based clustering đơn giản, module này:
1. Gán mỗi skill vào đúng 1 phase duy nhất (no duplication)
2. Enforce: prerequisite luôn nằm phase trước
3. Cân bằng số lượng skill giữa các phase
4. Tuân thủ DAG structure hoàn toàn

Algorithm:
- Topological sort toàn bộ DAG
- Depth assignment (longest path from root)
- Partition by depth với balancing
- Validate constraints (prerequisite phase < current phase)
"""
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque
import math


class HardConstraintPhaseBuilder:
    """
    Phase builder with strict DAG constraints.
    - No skill appears in more than one phase
    - All prerequisites are in earlier phases
    - Balanced skill distribution across phases
    """

    def __init__(self, skill_graph_engine, max_skills_per_phase: int = 5):
        """
        Initialize phase builder.

        Args:
            skill_graph_engine: SkillGraphEngine with prerequisite data
            max_skills_per_phase: Maximum skills per phase (default 5)
        """
        self.graph = skill_graph_engine
        self.max_skills_per_phase = max_skills_per_phase
        self.min_skills_per_phase = 2

    def build_phases(
        self,
        skills: List[str],
        current_skills: List[str] = None,
        user_priorities: Dict[str, float] = None
    ) -> List[Dict]:
        """
        Build strictly ordered phases from DAG.

        Args:
            skills: List of skills to include (already pruned for role)
            current_skills: Skills user already has (treated as depth 0)
            user_priorities: Optional dict of skill -> priority score

        Returns:
            List of phases with phase_id, title, skills, depth_range, reason
        """
        if current_skills is None:
            current_skills = []

        current_set = set(current_skills)

        # Step 1: Compute topological depth for each skill
        depth_map = self._compute_depths(skills, current_set)

        # Step 2: Group by depth
        depth_groups = defaultdict(list)
        for skill in skills:
            depth = depth_map.get(skill, 0)
            depth_groups[depth].append(skill)

        # Step 3: Flatten depth groups into ordered list (preserve depth order)
        ordered_skills = []
        for depth in sorted(depth_groups.keys()):
            ordered_skills.extend(depth_groups[depth])

        # Step 4: Partition into balanced phases
        phases = self._partition_into_phases(ordered_skills, depth_map)

        # Step 5: Validate constraints
        phases = self._validate_and_fix(phases, depth_map)

        # Step 6: Enrich with metadata
        return self._enrich_phases(phases, depth_map)

    def _compute_depths(self, skills: List[str], current_skills: Set[str]) -> Dict[str, int]:
        """
        Compute topological depth (longest path from current skills).

        Depth 0 = skills already mastered or no prerequisites.
        Higher depth = requires more prerequisites.
        """
        # Build graph for these skills only
        skill_set = set(skills)

        # Compute depth via BFS/longest path
        depths = {}
        for skill in skills:
            if skill in current_skills:
                depths[skill] = 0
                continue

            # Find longest path from any current skill to this skill
            max_depth = self._longest_path_to(skill, skill_set, current_skills)
            depths[skill] = max_depth if max_depth is not None else 0

        return depths

    def _longest_path_to(self, target: str, skill_set: Set[str], current_skills: Set[str]) -> Optional[int]:
        """
        Find longest path length from any current skill to target.
        Returns None if no path exists.
        """
        # Build adjacency list (prerequisite -> dependent)
        graph = defaultdict(list)
        for skill in skill_set:
            prereqs = self.graph.get_prerequisites(skill) if hasattr(self.graph, 'get_prerequisites') else []
            for prereq in prereqs:
                if prereq in skill_set or prereq in current_skills:
                    graph[prereq].append(skill)

        # DFS with memoization for longest path
        memo = {}

        def dfs(node: str, visited: Set[str]) -> int:
            if node in memo:
                return memo[node]
            if node in current_skills:
                return 0
            if node not in graph:
                return 0 if node in current_skills else -1

            max_len = -1
            for child in graph.get(node, []):
                if child in visited:
                    continue
                visited.add(child)
                child_len = dfs(child, visited)
                visited.remove(child)
                if child_len >= 0:
                    max_len = max(max_len, child_len + 1)

            memo[node] = max_len if max_len >= 0 else -1
            return memo[node]

        # Start from target and go backwards? Actually we want path from current to target.
        # Simpler: BFS from current skills and record distances
        distances = {s: 0 for s in current_skills}
        queue = deque(current_skills)

        while queue:
            current = queue.popleft()
            current_dist = distances.get(current, 0)
            for next_skill in graph.get(current, []):
                if next_skill not in distances or distances[next_skill] < current_dist + 1:
                    distances[next_skill] = current_dist + 1
                    queue.append(next_skill)

        return distances.get(target, -1) if target in distances else None

    def _partition_into_phases(self, ordered_skills: List[str], depth_map: Dict[str, int]) -> List[List[str]]:
        """
        Partition ordered skills into balanced phases.
        Each phase has 2-5 skills (unless very small total).
        """
        total = len(ordered_skills)
        if total == 0:
            return []

        # Determine number of phases
        target_phase_count = max(1, math.ceil(total / self.max_skills_per_phase))
        skills_per_phase = max(self.min_skills_per_phase, math.ceil(total / target_phase_count))

        phases = []
        for i in range(0, total, skills_per_phase):
            phase_skills = ordered_skills[i:i + skills_per_phase]
            if phase_skills:
                phases.append(phase_skills)

        # Ensure last phase is not too small
        if len(phases) > 1 and len(phases[-1]) < self.min_skills_per_phase:
            # Merge last two phases
            phases[-2].extend(phases[-1])
            phases.pop()

        return phases

    def _validate_and_fix(self, phases: List[List[str]], depth_map: Dict[str, int]) -> List[List[str]]:
        """
        Validate that for every skill, all prerequisites are in earlier phases.
        If violation found, move skill to later phase.
        """
        # Map each skill to its phase index
        skill_to_phase = {}
        for idx, phase_skills in enumerate(phases):
            for skill in phase_skills:
                skill_to_phase[skill] = idx

        # Check each skill
        fixed = False
        for idx, phase_skills in enumerate(phases):
            for skill in phase_skills[:]:
                prereqs = self.graph.get_prerequisites(skill) if hasattr(self.graph, 'get_prerequisites') else []
                for prereq in prereqs:
                    if prereq in skill_to_phase and skill_to_phase[prereq] > idx:
                        # Prerequisite is in a later phase -> move skill
                        if idx + 1 < len(phases):
                            phases[idx + 1].append(skill)
                        else:
                            phases.append([skill])
                        phase_skills.remove(skill)
                        fixed = True
                        # Update mapping
                        for new_idx, new_skills in enumerate(phases):
                            for s in new_skills:
                                skill_to_phase[s] = new_idx
                        break
                if fixed:
                    break
            if fixed:
                return self._validate_and_fix(phases, depth_map)

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

            # Compute average depth for this phase
            avg_depth = sum(depth_map.get(s, 0) for s in skills) / len(skills)

            enriched.append({
                "phase_id": idx + 1,
                "title": phase_titles[idx] if idx < len(phase_titles) else f"Phase {idx + 1}",
                "skills": skills,
                "skill_count": len(skills),
                "avg_depth": round(avg_depth, 2),
                "reason": self._generate_reason(avg_depth, len(skills))
            })

        return enriched

    def _generate_reason(self, avg_depth: float, skill_count: int) -> str:
        """Generate human-readable reason for phase grouping."""
        if avg_depth < 1:
            return f"Kiến thức nền tảng, {skill_count} kỹ năng cơ bản"
        elif avg_depth < 2:
            return f"Kỹ năng cốt lõi, xây dựng nền tảng vững chắc"
        elif avg_depth < 3:
            return f"Phát triển chuyên sâu, áp dụng vào dự án thực tế"
        else:
            return f"Kỹ năng nâng cao, tối ưu và mở rộng hệ thống"


if __name__ == "__main__":
    print("HardConstraintPhaseBuilder module loaded")

    # Quick test
    class MockGraph:
        def get_prerequisites(self, skill):
            mock = {
                "Deep Learning": ["Machine Learning"],
                "LLM": ["Deep Learning", "NLP"],
                "RAG": ["LLM"],
                "Machine Learning": ["Python", "SQL"],
                "NLP": ["Machine Learning"],
                "Python": [],
                "SQL": []
            }
            return mock.get(skill, [])

    graph = MockGraph()
    builder = HardConstraintPhaseBuilder(graph, max_skills_per_phase=3)

    skills = ["Python", "SQL", "Machine Learning", "Deep Learning", "NLP", "LLM", "RAG"]
    phases = builder.build_phases(skills, current_skills=["Python"])

    print("Phases generated:")
    for phase in phases:
        print(f"  Phase {phase['phase_id']}: {phase['title']}")
        print(f"    Skills: {phase['skills']}")
        print(f"    Reason: {phase['reason']}")
