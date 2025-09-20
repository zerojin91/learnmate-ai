"""
Learning Path Planner Agent - 전체 학습 경로 분석 및 설계
"""
from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class LearningPathPlannerAgent(BaseAgent):
    """전체 학습 경로를 분석하고 설계하는 에이전트"""

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """학습 경로 계획 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.LEARNING_PATH_PLANNING, "🧠 학습 경로 분석 중...")

            focus_text = ', '.join(state["focus_areas"]) if state["focus_areas"] else 'General coverage'

            analysis_text = await self._analyze_learning_path(
                topic=state["topic"],
                level=state["level"],
                duration_weeks=state["duration_weeks"],
                focus_areas=focus_text
            )

            # 상태 업데이트
            state["learning_path_analysis"] = analysis_text

            self.log_debug(f"Learning path analysis completed: {len(analysis_text)} characters")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Learning path planning failed")

    async def _analyze_learning_path(self, topic: str, level: str, duration_weeks: int, focus_areas: str) -> str:
        """학습 경로 분석"""

        system_prompt = """당신은 전문 교육 설계자입니다. 학습자의 요구에 맞는 최적의 학습 경로를 분석하고 설계해주세요."""

        user_prompt = f"""다음 학습 요구사항을 분석하여 체계적인 학습 계획을 수립해주세요:

학습 주제: {topic}
학습 레벨: {level}
학습 기간: {duration_weeks}주
포커스 영역: {focus_areas}

먼저 다음을 분석해주세요:
1. 이 주제의 핵심 학습 영역은 무엇인가?
2. {level} 수준에서 시작하여 어떤 순서로 학습해야 하는가?
3. {focus_areas}를 고려할 때 중점을 둬야 할 부분은?
4. {duration_weeks}주 동안 현실적으로 달성 가능한 목표는?

분석 결과를 자세히 설명하고, 전체 학습 로드맵을 제시해주세요."""

        analysis_text = await self.call_llm(system_prompt, user_prompt)
        return analysis_text