"""
Integration Agent - 최종 커리큘럼 조립 및 완성
"""
from typing import Dict, Any
from datetime import datetime

from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class IntegrationAgent(BaseAgent):
    """모든 구성 요소를 통합하여 최종 커리큘럼을 생성하는 에이전트"""

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """최종 커리큘럼 통합 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.INTEGRATION, "🔧 최종 커리큘럼 조립 중...")

            # 최종 커리큘럼 구성
            final_curriculum = self._build_final_curriculum(state)

            # 상태 업데이트
            state["final_curriculum"] = final_curriculum
            state["completed_at"] = datetime.now()
            state["processing_time"] = (state["completed_at"] - state["started_at"]).total_seconds()

            self.safe_update_phase(state, ProcessingPhase.COMPLETED, "✅ 커리큘럼 생성 완료!")

            self.log_debug(f"Curriculum integration completed in {state['processing_time']:.2f} seconds")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Integration failed")

    def _build_final_curriculum(self, state: CurriculumState) -> Dict[str, Any]:
        """최종 커리큘럼 구성"""

        # 모듈에 리소스 정보 병합
        final_modules = []
        for module in state.get("detailed_modules", []):
            week_key = f"week_{module.get('week')}"
            module_resources = state.get("module_resources", {}).get(week_key, {})

            # 모듈에 리소스 추가
            enhanced_module = {
                **module,
                "resources": module_resources
            }
            final_modules.append(enhanced_module)

        # 최종 커리큘럼 구성
        curriculum = {
            "title": f"{state['topic']} Learning Path",
            "level": state["level"],
            "duration_weeks": state["duration_weeks"],
            "weekly_hours": state["weekly_hours"],
            "focus_areas": state["focus_areas"],
            "modules": final_modules,
            "overall_goal": state.get("overall_goal", f"Master {state['topic']}"),
            "basic_resources": (state.get("basic_resources", []))[:5],  # 상위 5개만
            "session_id": state["session_id"],
            "original_constraints": state["constraints"],
            "original_goal": state["goal"],
            "generated_at": datetime.now().isoformat(),
            "processing_time": state.get("processing_time", 0),
            "total_estimated_hours": sum(m.get("estimated_hours", 0) for m in final_modules)
        }

        return curriculum