""""
LLM Narrative Layer - UX Intelligence Layer

Vai trò: KHÔNG tính toán gì, chỉ "giải thích hệ thống"

3 loại narrative:
1. Phase Narrative - giải thích từng phase khi user hover
2. Personalized Story - giải thích toàn bộ roadmap theo user (onboarding UX)
3. ATS Report Narrative - giải thích "why you are X% not Y%"

Quy tắc:
- Không hallucinated skills
- Phải theo đúng dữ liệu JSON đầu vào
- Output structured JSON
"""
from typing import Dict, List, Optional


class LLMNarrativeLayer:
    """
    Lớp narrative thuần túy - chỉ explain, không decide.
    """

    def __init__(self):
        """Khởi tạo narrative layer."""
        pass

    def generate_phase_narrative(
        self,
        phase_id: int,
        phase_title: str,
        skills: List[str],
        avg_depth: float,
        reason: str
    ) -> Dict:
        """
        Tạo narrative cho một phase (dùng khi user hover/click phase).

        Args:
            phase_id: ID của phase
            phase_title: Tiêu đề phase (ví dụ "Nền tảng cơ bản")
            skills: Danh sách kỹ năng trong phase
            avg_depth: Độ sâu trung bình (0-...)
            reason: Lý do grouping từ phase builder

        Returns:
            Dict với phase_id, narrative
        """
        # Tạo narrative dựa trên depth và số lượng skills
        if avg_depth < 1:
            base_narrative = f"Phase {phase_id} - {phase_title}: Đây là những kiến thức nền tảng, bạn sẽ làm quen với {len(skills)} kỹ năng cơ bản: {', '.join(skills)}. Hoàn thành phase này giúp bạn có nền tảng vững chắc để tiếp cận các chủ đề nâng cao hơn."
        elif avg_depth < 2:
            base_narrative = f"Phase {phase_id} - {phase_title}: Bạn sẽ xây dựng các kỹ năng cốt lõi bao gồm {', '.join(skills)}. Đây là những kỹ năng quan trọng, xuất hiện thường xuyên trong các yêu cầu tuyển dụng."
        elif avg_depth < 3:
            base_narrative = f"Phase {phase_id} - {phase_title}: Phát triển chuyên sâu với {len(skills)} kỹ năng: {', '.join(skills)}. Bạn sẽ áp dụng chúng vào các dự án thực tế."
        else:
            base_narrative = f"Phase {phase_id} - {phase_title}: Đây là các kỹ năng nâng cao: {', '.join(skills)}. Hoàn thành phase này giúp bạn sẵn sàng cho các vị trí senior hoặc chuyên sâu."

        return {
            "phase_id": phase_id,
            "narrative": base_narrative,
            "detail": {
                "skill_count": len(skills),
                "avg_depth": avg_depth,
                "reason": reason
            }
        }

    def generate_personalized_story(
        self,
        current_skills: List[str],
        missing_skills: List[str],
        partial_skills: List[str],
        stage: str,
        target_role: str,
        phases: List[Dict]
    ) -> Dict:
        """
        Tạo personalized story cho onboarding UX.

        Args:
            current_skills: Kỹ năng đã có
            missing_skills: Kỹ năng còn thiếu
            partial_skills: Kỹ năng đang học/dở
            stage: Career stage (Student/Fresher/Junior/Middle)
            target_role: Vai trò mục tiêu
            phases: Danh sách phases đã tạo

        Returns:
            Dict với summary, focus, advice
        """
        # Xác định điểm mạnh và điểm yếu
        strengths = current_skills[:5] if len(current_skills) > 5 else current_skills
        top_missing = missing_skills[:3] if len(missing_skills) > 3 else missing_skills

        # Tạo summary dựa trên stage
        if stage == "Student":
            stage_desc = "bạn đang là sinh viên"
        elif stage == "Fresher":
            stage_desc = "bạn mới ra trường"
        elif stage == "Junior":
            stage_desc = "bạn đang ở cấp độ Junior"
        else:
            stage_desc = "bạn đã có kinh nghiệm"

        summary = f"Chào bạn! {stage_desc}. Bạn đang nhắm đến vị trí {target_role}. "

        if strengths:
            summary += f"Điểm mạnh hiện tại của bạn: {', '.join(strengths)}. "
        else:
            summary += "Bạn đang bắt đầu từ đầu. "

        if partial_skills:
            summary += f"Bạn đang trong quá trình học {', '.join(partial_skills[:3])}. "

        summary += f"Còn thiếu {len(missing_skills)} kỹ năng quan trọng: {', '.join(top_missing)}."

        # Xác định focus
        focus = []
        if partial_skills:
            focus.append(f"Hoàn thành {', '.join(partial_skills[:2])} trước")
        if top_missing:
            focus.append(f"Tập trung vào {top_missing[0]} - đây là kỹ năng cốt lõi")

        # Lấy phase đầu tiên
        if phases:
            first_phase_skills = phases[0].get("skills", [])
            if first_phase_skills:
                focus.append(f"Bắt đầu với Phase 1: {', '.join(first_phase_skills[:3])}")

        # Lời khuyên
        advice = []
        if stage == "Student":
            advice.append("Tận dụng thời gian ở trường để xây dựng portfolio")
            advice.append("Tham gia các câu lạc bộ hoặc dự án open source")
        elif stage == "Fresher":
            advice.append("Tập trung xây dựng các dự án cá nhân để chứng minh năng lực")
            advice.append("Chuẩn bị cho phỏng vấn với các câu hỏi về kỹ năng cốt lõi")
        else:
            advice.append("Kết hợp học lý thuyết với thực hành qua dự án thực tế")
            advice.append("Cập nhật CV và LinkedIn sau mỗi phase")

        if "LLM" in top_missing or "RAG" in top_missing:
            advice.append("Nên ưu tiên học LLM và RAG vì đây là xu hướng thị trường")

        return {
            "summary": summary,
            "focus": focus[:4],
            "advice": advice[:4],
            "strengths": strengths,
            "top_missing": top_missing
        }

    def generate_ats_report_narrative(
        self,
        current_score: int,
        final_score: int,
        bottlenecks: List[str],
        penalties: List[Dict],
        phase_contributions: List[Dict],
        target_role: str
    ) -> Dict:
        """
        Tạo ATS report narrative - giải thích "why you are X% not Y%".

        Args:
            current_score: Điểm ATS hiện tại
            final_score: Điểm ATS dự kiến sau roadmap
            bottlenecks: Danh sách kỹ năng gây bottleneck
            penalties: Danh sách penalty do thiếu prerequisite
            phase_contributions: Đóng góp của từng phase
            target_role: Vai trò mục tiêu

        Returns:
            Dict với report, weaknesses, next_actions
        """
        # Xác định mức độ
        if current_score < 30:
            level = "còn rất nhiều khoảng cách"
        elif current_score < 60:
            level = "đang ở mức trung bình"
        elif current_score < 80:
            level = "khá tốt"
        else:
            level = "rất tốt"

        report = f"Bạn đạt {current_score}% mức độ phù hợp cho vị trí {target_role} - {level}. "

        if bottlenecks:
            report += f"Điểm nghẽn chính: {', '.join(bottlenecks[:3])}. "

        if penalties:
            total_penalty = sum(p.get("penalty", 0) for p in penalties)
            if total_penalty > 0:
                report += f"Bạn bị trừ {int(total_penalty * 100)}% do thiếu các kỹ năng nền tảng. "

        improvement_delta = final_score - current_score
        if improvement_delta > 0:
            report += f"Sau khi hoàn thành roadmap, bạn có thể đạt {final_score}% (tăng {improvement_delta}%)."
        else:
            report += f"Hoàn thành roadmap giúp bạn đạt {final_score}%."

        # Xác định weaknesses cụ thể
        weaknesses = bottlenecks.copy()
        for penalty in penalties:
            if penalty.get("skill") not in weaknesses:
                weaknesses.append(penalty.get("skill"))

        # Gợi ý hành động tiếp theo
        next_actions = []
        if bottlenecks:
            next_actions.append(f"Tập trung vào {bottlenecks[0]} - đây là kỹ năng quan trọng nhất còn thiếu")
        if phase_contributions:
            # Tìm phase có delta lớn nhất
            max_delta_phase = max(phase_contributions, key=lambda x: x.get("delta", 0))
            if max_delta_phase.get("delta", 0) > 0:
                next_actions.append(f"Hoàn thành Phase {max_delta_phase['phase_id']} để tăng {max_delta_phase['delta']}% ATS")
        if not next_actions:
            next_actions.append("Bắt đầu với kỹ năng có độ khó thấp nhất trước")

        return {
            "report": report,
            "weaknesses": weaknesses[:5],
            "next_actions": next_actions[:3],
            "current_score": current_score,
            "final_score": final_score,
            "improvement_delta": improvement_delta
        }

    def generate_full_narrative(
        self,
        roadmap_data: Dict,
        ats_data: Dict,
        user_status: Dict,
        target_role: str
    ) -> Dict:
        """
        Tạo toàn bộ narratives trong một lần gọi.

        Args:
            roadmap_data: Dict chứa phases, pruned_graph,...
            ats_data: Dict chứa current_score, final_score, bottlenecks,...
            user_status: Dict chứa completed, partial, missing, stage
            target_role: Vai trò mục tiêu

        Returns:
            Dict với phase_narratives, personalized_story, ats_report
        """
        phase_narratives = []
        phases = roadmap_data.get("phases", [])

        for phase in phases:
            phase_narrative = self.generate_phase_narrative(
                phase_id=phase.get("phase_id", 0),
                phase_title=phase.get("title", ""),
                skills=phase.get("skills", []),
                avg_depth=phase.get("avg_depth", 0),
                reason=phase.get("reason", "")
            )
            phase_narratives.append(phase_narrative)

        personalized_story = self.generate_personalized_story(
            current_skills=user_status.get("completed", []),
            missing_skills=user_status.get("missing", []),
            partial_skills=user_status.get("partial", []),
            stage=user_status.get("stage", "Fresher"),
            target_role=target_role,
            phases=phases
        )

        ats_report = self.generate_ats_report_narrative(
            current_score=ats_data.get("current_score", 0),
            final_score=ats_data.get("final_score", 0),
            bottlenecks=ats_data.get("bottlenecks", []),
            penalties=ats_data.get("penalties", []),
            phase_contributions=ats_data.get("phase_contributions", []),
            target_role=target_role
        )

        return {
            "phase_narratives": phase_narratives,
            "personalized_story": personalized_story,
            "ats_report": ats_report
        }


if __name__ == "__main__":
    print("LLMNarrativeLayer module loaded")

    # Quick test
    layer = LLMNarrativeLayer()

    # Test phase narrative
    phase_narr = layer.generate_phase_narrative(
        phase_id=1,
        phase_title="Nền tảng cơ bản",
        skills=["Python", "SQL"],
        avg_depth=0.5,
        reason="Kiến thức nền tảng"
    )
    print(f"Phase narrative: {phase_narr['narrative']}")
    print()

    # Test personalized story
    story = layer.generate_personalized_story(
        current_skills=["Python", "PyTorch"],
        missing_skills=["Machine Learning", "Deep Learning", "LLM", "RAG"],
        partial_skills=["SQL"],
        stage="Fresher",
        target_role="AI Engineer",
        phases=[{"phase_id": 1, "skills": ["Python", "SQL"]}]
    )
    print(f"Personalized story: {story['summary']}")
    print(f"Focus: {story['focus']}")
    print()

    # Test ATS report
    ats_report = layer.generate_ats_report_narrative(
        current_score=43,
        final_score=68,
        bottlenecks=["Deep Learning", "LLM"],
        penalties=[{"skill": "LLM", "penalty": 0.15}],
        phase_contributions=[{"phase_id": 1, "delta": 12}, {"phase_id": 2, "delta": 13}],
        target_role="AI Engineer"
    )
    print(f"ATS report: {ats_report['report']}")
    print(f"Next actions: {ats_report['next_actions']}")
