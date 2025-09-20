"""
Module Structure Agent - 주차별 모듈 구조 생성
"""
from typing import List, Dict, Any

from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class ModuleStructureAgent(BaseAgent):
    """주차별 모듈 구조를 설계하는 에이전트"""

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """모듈 구조 설계 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.MODULE_STRUCTURE_DESIGN, "📋 모듈 구조 설계 중...")

            modules, overall_goal = await self._design_module_structure(
                topic=state["topic"],
                duration_weeks=state["duration_weeks"],
                analysis_text=state["learning_path_analysis"]
            )

            # 상태 업데이트
            state["module_structure"] = modules
            state["overall_goal"] = overall_goal

            self.log_debug(f"Module structure designed: {len(modules)} modules")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Module structure design failed")

    async def _design_module_structure(self, topic: str, duration_weeks: int, analysis_text: str) -> tuple[List[Dict[str, Any]], str]:
        """모듈 구조 설계"""

        system_prompt = """전체 커리큘럼 구조를 설계하는 전문가입니다. 논리적이고 체계적인 학습 흐름을 만들어주세요."""

        user_prompt = f"""앞선 분석을 바탕으로 {duration_weeks}주 커리큘럼의 전체 구조를 설계해주세요.

이전 분석 결과:
{analysis_text}

각 주차별로 다음 정보만 포함하여 JSON 형태로 생성해주세요:
- week: 주차 번호
- title: 주차 제목 (한국어)
- main_topic: 주요 학습 주제 (한국어)
- learning_goals: 이번 주차의 핵심 목표 2-3개 (한국어 리스트)
- difficulty_level: 난이도 (1-10)

JSON 형식:
{{
    "modules": [
        {{
            "week": 1,
            "title": "주차 제목",
            "main_topic": "주요 학습 주제",
            "learning_goals": ["목표1", "목표2"],
            "difficulty_level": 3
        }}
    ],
    "overall_goal": "전체 학습 목표"
}}"""

        response_text = await self.call_llm(system_prompt, user_prompt)

        try:
            structure_data = self.extract_json_from_text(response_text)
            modules = structure_data.get("modules", [])
            overall_goal = structure_data.get("overall_goal", f"Master {topic}")

            # 기본 검증
            if not modules:
                raise ValueError("No modules found in response")

            return modules, overall_goal

        except Exception as e:
            self.log_debug(f"JSON parsing failed, using fallback: {e}")
            return self._create_fallback_structure(topic, duration_weeks), f"Master {topic}"

    def _create_fallback_structure(self, topic: str, duration_weeks: int) -> List[Dict[str, Any]]:
        """JSON 파싱 실패 시 기본 구조 생성"""
        modules = []
        for week in range(1, duration_weeks + 1):
            modules.append({
                "week": week,
                "title": f"{topic} 학습 - {week}주차",
                "main_topic": f"{topic} 기본 개념 및 실습",
                "learning_goals": [
                    f"{topic} 기본 이해",
                    "실습을 통한 활용"
                ],
                "difficulty_level": min(week + 2, 10)
            })
        return modules