"""
Graph-based ATS Scoring Engine

ATS = path_coverage_score + market_alignment - dependency_penalty

Công thức chi tiết:
- Với mỗi target skill (từ role-pruned graph)
- Tìm shortest path từ current skills đến target
- score += skill_weight * (completed_steps / total_steps)
- Dependency penalty: nếu thiếu prerequisite -> nhân với 0.85
- Market boost: nhân với market_demand_weight[skill]
"""
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class SkillScore:
    """Score breakdown for a single skill."""
    skill: str
    weight: float
    path_completion: float
    market_boost: float
    final_contribution: float


@dataclass
class ATSReport:
    """Complete ATS scoring report."""
    current_score: int
    final_score: int
    skill_scores: List[Dict]
    phase_contributions: List[Dict]
    bottlenecks: List[str]
    penalties: List[Dict]


class GraphATSScorer:
    """
    Graph-based ATS scoring engine.

    Tính điểm dựa trên độ hoàn thành của các đường đi trong DAG,
    không phải dựa trên phase index.
    """

    # Mức độ thành thạo
    MASTERY_LEVELS = {
        "completed": 1.0,
        "in_progress": 0.5,
        "partial": 0.5,
        "missing": 0.0
    }

    # Hệ số market mặc định
    DEFAULT_MARKET_FACTORS = {
        "LLM": 1.4, "RAG": 1.3, "LangChain": 1.3,
        "PyTorch": 1.2, "Kubernetes": 1.2, "Docker": 1.1,
        "Python": 1.0, "SQL": 0.9, "Machine Learning": 1.1,
        "Deep Learning": 1.2, "Computer Vision": 1.0, "NLP": 1.1
    }

    def __init__(self, skill_graph_engine, role_matrix: Dict = None, market_factors: Dict = None):
        """
        Khởi tạo ATS scorer.

        Args:
            skill_graph_engine: SkillGraphEngine với dữ liệu prerequisite
            role_matrix: Role matrix từ SkillGapEngine (chứa frequency)
            market_factors: Hệ số market tùy chỉnh
        """
        self.graph = skill_graph_engine
        self.role_matrix = role_matrix or {}
        self.market_factors = market_factors or self.DEFAULT_MARKET_FACTORS

        # Cấu hình
        self.penalty_per_missing_prereq = 0.15  # 15% penalty mỗi chain
        self.synergy_bonus_cap = 0.10  # Tối đa 10% bonus

    def get_skill_weight(self, skill: str, target_role: str) -> float:
        """
        Lấy trọng số của skill dựa trên frequency trong role matrix.
        """
        role_skills = self.role_matrix.get(target_role, [])
        for item in role_skills:
            if item.get("skill") == skill:
                return item.get("frequency", 50) / 100.0
        return 0.3  # Mặc định 30%

    def get_market_boost(self, skill: str) -> float:
        """Lấy hệ số market boost."""
        return self.market_factors.get(skill, 1.0)

    def find_shortest_path_from_current(
        self,
        target: str,
        current_skills: Set[str]
    ) -> Tuple[List[str], float]:
        """
        Tìm shortest path từ bất kỳ current skill nào đến target.

        Returns:
            (path, completion_ratio) với completion_ratio = (số bước đã hoàn thành) / (tổng số bước)
        """
        # BFS từ target ngược về current skills
        visited = set()
        queue = deque([(target, [target])])

        while queue:
            current, path = queue.popleft()
            if current in visited:
                continue
            visited.add(current)

            # Nếu current là skill đã có, trả về path
            if current in current_skills:
                # Tính completion ratio
                # Path hiện tại là từ target xuống current (reverse)
                # Các bước trong path: target -> ... -> current
                # Nhưng thứ tự học phải từ current lên target
                # completion = 1 nếu current là bước cuối? Cần làm rõ
                # Đơn giản: completion_ratio = 1.0 (đã có target? Không)
                # Thực tế: target chưa có, path là các bước cần học
                # completion_ratio = (số bước đã có) / (tổng số bước)
                # Ở đây current có sẵn, các bước còn lại cần học
                steps_needed = len(path)  # path bao gồm target đến current
                steps_completed = 1 if current in current_skills else 0
                completion = steps_completed / steps_needed if steps_needed > 0 else 1.0
                return (path, completion)

            # Lấy prerequisites của current (đi ngược lên)
            prereqs = self.graph.get_prerequisites(current) if hasattr(self.graph, 'get_prerequisites') else []
            for prereq in prereqs:
                if prereq not in visited:
                    queue.append((prereq, path + [prereq]))

        # Không tìm thấy path -> cần học toàn bộ từ đầu
        # Lấy toàn bộ prerequisite chain từ target
        all_prereqs = self._collect_all_prerequisites(target, current_skills)
        full_path = [target] + all_prereqs
        return (full_path, 0.0)

    def _collect_all_prerequisites(self, skill: str, current_skills: Set[str]) -> List[str]:
        """Thu thập tất cả prerequisite chưa có."""
        all_prereqs = []
        visited = set()
        queue = [skill]

        while queue:
            s = queue.pop(0)
            if s in visited:
                continue
            visited.add(s)
            prereqs = self.graph.get_prerequisites(s) if hasattr(self.graph, 'get_prerequisites') else []
            for p in prereqs:
                if p not in current_skills and p not in visited:
                    all_prereqs.append(p)
                    queue.append(p)
        return all_prereqs

    def calculate_readiness(
        self,
        skills_with_status: Dict[str, str],
        target_role: str,
        target_skills: List[str] = None
    ) -> Dict:
        """
        Tính ATS readiness dựa trên graph path completion.

        Args:
            skills_with_status: Dict skill -> status ("completed", "in_progress", "missing")
            target_role: Vai trò mục tiêu
            target_skills: Danh sách skill cần đạt (nếu None, lấy từ role matrix)

        Returns:
            Dict với score, skill_scores, bottlenecks, penalties
        """
        if target_skills is None:
            # Lấy từ role matrix
            role_skills = self.role_matrix.get(target_role, [])
            target_skills = [item["skill"] for item in role_skills]

        current_set = set(s for s, status in skills_with_status.items()
                         if status in ["completed", "in_progress"])

        total_weight = 0.0
        total_weighted_score = 0.0
        skill_scores = []
        penalties = []

        for skill in target_skills:
            weight = self.get_skill_weight(skill, target_role)
            if weight == 0:
                continue

            total_weight += weight

            status = skills_with_status.get(skill, "missing")

            # Nếu đã completed, đóng góp full weight
            if status == "completed":
                contribution = weight
                path_completion = 1.0
            else:
                # Tìm shortest path
                path, completion = self.find_shortest_path_from_current(skill, current_set)
                path_completion = completion

                # Đóng góp dựa trên completion ratio
                contribution = weight * path_completion

                # Kiểm tra dependency penalty
                if status == "missing":
                    missing_prereqs = self._collect_all_prerequisites(skill, current_set)
                    if missing_prereqs:
                        penalty = self.penalty_per_missing_prereq * len(missing_prereqs)
                        penalty = min(penalty, 0.5)  # Cap at 50%
                        penalties.append({
                            "skill": skill,
                            "missing_prerequisites": missing_prereqs,
                            "penalty": round(penalty, 3)
                        })
                        contribution *= (1 - penalty)

            # Market boost
            market_boost = self.get_market_boost(skill)
            final_contribution = contribution * market_boost

            total_weighted_score += final_contribution

            skill_scores.append({
                "skill": skill,
                "weight": round(weight, 3),
                "path_completion": round(path_completion, 3),
                "market_boost": market_boost,
                "final_contribution": round(final_contribution, 3),
                "status": status
            })

        # Tính điểm cuối
        raw_score = (total_weighted_score / total_weight) * 100 if total_weight > 0 else 0
        final_score = min(100, raw_score)

        # Xác định bottlenecks (skills có path_completion thấp nhất)
        bottlenecks = sorted(
            skill_scores,
            key=lambda x: x["path_completion"]
        )[:3]

        return {
            "score": round(final_score),
            "raw_score": round(raw_score),
            "skill_scores": skill_scores,
            "bottlenecks": [b["skill"] for b in bottlenecks if b["path_completion"] < 0.5],
            "penalties": penalties,
            "total_weight": round(total_weight, 3),
            "total_weighted_score": round(total_weighted_score, 3)
        }

    def project_phases(
        self,
        current_skills: List[str],
        phases: List[Dict],
        target_role: str
    ) -> ATSReport:
        """
        Dự đoán ATS qua các phase.

        Args:
            current_skills: Danh sách skill hiện tại
            phases: Danh sách phase, mỗi phase có key "skills"
            target_role: Vai trò mục tiêu

        Returns:
            ATSReport với score hiện tại, score từng phase, bottlenecks
        """
        # Trạng thái ban đầu
        skill_status = {skill: "completed" for skill in current_skills}

        # Tính điểm hiện tại
        current_result = self.calculate_readiness(skill_status, target_role)
        current_score = current_result["score"]

        # Dự đoán qua từng phase
        accumulated_skills = set(current_skills)
        phase_scores = {}
        phase_bottlenecks = {}

        for i, phase in enumerate(phases, 1):
            phase_skills = phase.get("skills", [])
            if isinstance(phase_skills[0], dict):
                phase_skills = [s["skill"] for s in phase_skills]

            # Thêm skill của phase
            for skill in phase_skills:
                if skill not in accumulated_skills:
                    accumulated_skills.add(skill)
                    skill_status[skill] = "completed"

            # Tính lại readiness
            phase_result = self.calculate_readiness(skill_status, target_role)
            phase_scores[f"phase_{i}"] = phase_result["score"]
            phase_bottlenecks[f"phase_{i}"] = phase_result["bottlenecks"]

        final_score = phase_scores.get(f"phase_{len(phases)}", current_score) if phases else current_score
        improvement_delta = final_score - current_score

        # Tính phase contributions (mức tăng sau mỗi phase)
        phase_contributions = []
        prev_score = current_score
        for i in range(1, len(phases) + 1):
            phase_score = phase_scores.get(f"phase_{i}", prev_score)
            delta = phase_score - prev_score
            phase_contributions.append({
                "phase_id": i,
                "score": phase_score,
                "delta": delta
            })
            prev_score = phase_score

        return ATSReport(
            current_score=current_score,
            final_score=final_score,
            skill_scores=current_result["skill_scores"],
            phase_contributions=phase_contributions,
            bottlenecks=current_result["bottlenecks"],
            penalties=current_result["penalties"]
        )


if __name__ == "__main__":
    print("GraphATSScorer module loaded")

    # Quick test
    class MockGraph:
        def get_prerequisites(self, skill):
            mock = {
                "LLM": ["Deep Learning", "NLP"],
                "Deep Learning": ["Machine Learning"],
                "Machine Learning": ["Python", "SQL"],
                "RAG": ["LLM"],
                "NLP": ["Machine Learning"],
                "Python": [], "SQL": []
            }
            return mock.get(skill, [])

    graph = MockGraph()
    role_matrix = {
        "AI Engineer": [
            {"skill": "Python", "frequency": 95},
            {"skill": "Machine Learning", "frequency": 85},
            {"skill": "Deep Learning", "frequency": 75},
            {"skill": "LLM", "frequency": 80},
            {"skill": "RAG", "frequency": 60}
        ]
    }

    scorer = GraphATSScorer(graph, role_matrix)

    # Test với skill hiện tại
    skill_status = {
        "Python": "completed",
        "Machine Learning": "in_progress",
        "Deep Learning": "missing",
        "LLM": "missing",
        "RAG": "missing"
    }

    result = scorer.calculate_readiness(skill_status, "AI Engineer")
    print(f"Score: {result['score']}%")
    print(f"Bottlenecks: {result['bottlenecks']}")
