"""
Validation Agent - 시간 제약 검증 및 조정
"""
from typing import Dict, Any

from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class ValidationAgent(BaseAgent):
    """생성된 커리큘럼의 시간을 검증하고 조정하는 에이전트"""

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """시간 제약 검증 및 조정 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.VALIDATION, "⚠️ 시간 제약 검증 중...")

            if not state["detailed_modules"]:
                raise ValueError("No detailed modules found for validation")

            # 시간 검증 및 조정
            validated_modules = self._validate_and_adjust_hours(
                state["detailed_modules"],
                state["weekly_hours"],
                state["duration_weeks"]
            )

            # 상태 업데이트
            state["detailed_modules"] = validated_modules

            total_hours = sum(m.get("estimated_hours", 0) for m in validated_modules)
            self.log_debug(f"Validation completed. Total hours: {total_hours}")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Validation failed")

    def _validate_and_adjust_hours(self, modules: list, weekly_hours: int, duration_weeks: int) -> list:
        """생성된 커리큘럼의 시간을 검증하고 사용자 제약에 맞게 조정"""
        max_total_hours = weekly_hours * duration_weeks

        if not modules:
            return modules

        # 1. 현재 총 시간 계산
        current_total = sum(module.get("estimated_hours", 0) for module in modules)

        self.log_debug(f"Time validation - Current: {current_total}h, Max: {max_total_hours}h")

        # 2. 초과시 비율적으로 조정
        if current_total > max_total_hours:
            adjustment_ratio = max_total_hours / current_total
            self.log_debug(f"Adjusting hours by ratio: {adjustment_ratio:.3f}")

            for module in modules:
                original_hours = module.get("estimated_hours", 0)
                adjusted_hours = max(1, round(original_hours * adjustment_ratio))
                module["estimated_hours"] = adjusted_hours

        # 3. 부족시 균등하게 증가
        elif current_total < max_total_hours * 0.8:  # 80% 미만인 경우
            additional_hours = max_total_hours - current_total
            hours_per_module = additional_hours // len(modules)
            remaining_hours = additional_hours % len(modules)

            for i, module in enumerate(modules):
                module["estimated_hours"] += hours_per_module
                if i < remaining_hours:
                    module["estimated_hours"] += 1

        # 4. 최종 검증
        final_total = sum(module.get("estimated_hours", 0) for module in modules)
        self.log_debug(f"Final total hours: {final_total}")

        return modules