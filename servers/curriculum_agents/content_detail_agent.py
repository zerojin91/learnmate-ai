"""
Content Detail Agent - 각 모듈의 상세 내용 생성 (병렬 처리 가능)
"""
from typing import List, Dict, Any
import asyncio

from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class ContentDetailAgent(BaseAgent):
    """각 모듈의 상세 내용을 생성하는 에이전트"""

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """모듈 상세 내용 생성 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.CONTENT_DETAIL_GENERATION, "📝 모듈 상세 내용 생성 중...")

            modules = state["module_structure"]
            if not modules:
                raise ValueError("No module structure found")

            # 병렬로 모든 모듈 처리
            detailed_modules = await self._generate_all_module_details(modules)

            # 상태 업데이트
            state["detailed_modules"] = detailed_modules

            self.log_debug(f"Generated detailed content for {len(detailed_modules)} modules")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Content detail generation failed")

    async def _generate_all_module_details(self, modules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """모든 모듈의 상세 내용을 병렬로 생성"""

        # 병렬 처리를 위한 태스크 생성
        tasks = []
        for i, module in enumerate(modules):
            previous_modules = modules[:i] if i > 0 else []
            task = self._generate_module_detail(module, previous_modules)
            tasks.append(task)

        # 병렬 실행
        detailed_modules = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 처리 (예외 발생한 모듈은 원본 사용)
        final_modules = []
        for i, result in enumerate(detailed_modules):
            if isinstance(result, Exception):
                self.log_debug(f"Module {i+1} detail generation failed: {result}, using original")
                final_modules.append(modules[i])
            else:
                final_modules.append(result)

        return final_modules

    async def _generate_module_detail(self, module: Dict[str, Any], previous_modules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """개별 모듈의 상세 내용 생성"""
        try:
            system_prompt = """각 모듈의 상세 내용을 설계하는 전문가입니다. 실용적이고 구체적인 학습 내용을 만들어주세요."""

            previous_titles = [m.get('title', f"{m.get('week')}주차") for m in previous_modules[-2:]] if previous_modules else []

            user_prompt = f"""다음 모듈의 상세 내용을 생성해주세요:

모듈 정보:
- 주차: {module.get('week')}주차
- 제목: {module.get('title')}
- 주요 주제: {module.get('main_topic')}
- 학습 목표: {module.get('learning_goals')}

이전 모듈들: {previous_titles if previous_titles else '없음'}

다음 내용을 포함한 상세 모듈을 JSON으로 생성해주세요:
{{
    "week": {module.get('week')},
    "title": "{module.get('title')}",
    "description": "모듈에 대한 상세한 설명 (한국어)",
    "objectives": ["구체적인 학습목표1", "학습목표2", "학습목표3"],
    "learning_outcomes": ["내가 배울 수 있는 것1", "내가 배울 수 있는 것2"],
    "key_concepts": ["핵심개념1", "핵심개념2", "핵심개념3"],
    "estimated_hours": 예상학습시간(숫자)
}}"""

            response_text = await self.call_llm(system_prompt, user_prompt)
            detailed_module = self.extract_json_from_text(response_text)

            # 기본 검증
            if not detailed_module.get("week"):
                detailed_module["week"] = module.get("week")
            if not detailed_module.get("title"):
                detailed_module["title"] = module.get("title")

            return detailed_module

        except Exception as e:
            self.log_debug(f"Failed to generate detail for module {module.get('week')}: {e}")
            # 실패 시 원본 모듈에 기본 정보 추가
            return {
                **module,
                "description": f"{module.get('title')} 모듈의 상세 학습 내용",
                "objectives": module.get('learning_goals', []),
                "learning_outcomes": ["기본 개념 이해", "실습 능력 향상"],
                "key_concepts": [module.get('main_topic', '핵심 개념')],
                "estimated_hours": 8
            }