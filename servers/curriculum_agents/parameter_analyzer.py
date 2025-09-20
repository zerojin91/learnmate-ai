"""
Parameter Analyzer Agent - 세션 데이터에서 학습 파라미터 추출
"""
from typing import Dict, Any
import re
import json

from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class ParameterAnalyzerAgent(BaseAgent):
    """세션 데이터를 분석하여 학습 파라미터를 추출하는 에이전트"""

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """파라미터 분석 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.PARAMETER_ANALYSIS, "📊 학습 파라미터 분석 중...")

            # LLM을 사용하여 파라미터 추출
            params = await self._extract_parameters_with_llm(
                state["constraints"],
                state["goal"]
            )

            # 사용자 메시지에서 기간 정보 추출 및 오버라이드
            if state.get("user_message"):
                message_duration = self._extract_duration_from_message(state["user_message"])
                if message_duration is not None:
                    params["duration_weeks"] = message_duration
                    self.log_debug(f"Duration overridden to {message_duration} weeks from user message")

            # 상태 업데이트
            state["level"] = params.get("level", "beginner")
            state["duration_weeks"] = params.get("duration_weeks", 4)
            state["focus_areas"] = params.get("focus_areas", [])
            state["weekly_hours"] = params.get("weekly_hours", 10)

            self.log_debug(f"Extracted parameters: level={state['level']}, duration={state['duration_weeks']}, focus={state['focus_areas']}")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Parameter extraction failed")

    async def _extract_parameters_with_llm(self, constraints: str, goal: str, max_retries: int = 3) -> Dict[str, Any]:
        """LLM을 사용하여 제약 조건과 목표에서 학습 파라미터 추출"""

        system_prompt = """당신은 학습 요구사항을 분석하는 전문가입니다.
주어진 제약조건과 학습목표를 분석하여 구조화된 학습 파라미터를 추출해주세요."""

        user_prompt = f"""다음 정보를 분석하여 학습 파라미터를 추출해주세요:

제약조건: {constraints}
학습목표: {goal}

다음 JSON 형식으로 응답해주세요:
{{
    "level": "beginner|intermediate|advanced",
    "duration_weeks": 학습기간(주 단위, 1-24),
    "focus_areas": ["중점분야1", "중점분야2", "중점분야3"],
    "weekly_hours": 주당학습시간(1-40)
}}

분석 기준:
- level: 언급된 경험수준이나 배경지식으로 판단
- duration_weeks: 언급된 기간이나 목표의 복잡도로 판단
- focus_areas: 구체적으로 언급된 관심분야나 목표에서 추출
- weekly_hours: 언급된 시간이나 일반적인 학습 강도로 판단"""

        for attempt in range(max_retries):
            try:
                response_text = await self.call_llm(system_prompt, user_prompt)
                params = self.extract_json_from_text(response_text)

                # 유효성 검증
                if self._validate_parameters(params):
                    return params
                else:
                    self.log_debug(f"Invalid parameters on attempt {attempt + 1}: {params}")

            except Exception as e:
                self.log_debug(f"Parameter extraction attempt {attempt + 1} failed: {e}")

                if attempt == max_retries - 1:
                    # 최종 실패 시 fallback 사용
                    return self._parse_constraints_fallback(constraints, goal)

        return self._parse_constraints_fallback(constraints, goal)

    def _validate_parameters(self, params: Dict[str, Any]) -> bool:
        """추출된 파라미터 유효성 검증"""
        required_keys = ["level", "duration_weeks", "focus_areas", "weekly_hours"]

        if not all(key in params for key in required_keys):
            return False

        if params["level"] not in ["beginner", "intermediate", "advanced"]:
            return False

        if not isinstance(params["duration_weeks"], int) or not (1 <= params["duration_weeks"] <= 24):
            return False

        if not isinstance(params["focus_areas"], list):
            return False

        if not isinstance(params["weekly_hours"], int) or not (1 <= params["weekly_hours"] <= 40):
            return False

        return True

    def _parse_constraints_fallback(self, constraints: str, goal: str) -> Dict[str, Any]:
        """LLM 실패 시 규칙 기반 파라미터 추출"""
        self.log_debug("Using fallback parameter extraction")

        combined_text = f"{constraints} {goal}".lower()

        # 레벨 감지
        level = "beginner"
        if any(word in combined_text for word in ["고급", "advanced", "전문", "깊이", "심화"]):
            level = "advanced"
        elif any(word in combined_text for word in ["중급", "intermediate", "경험", "기본적인 지식"]):
            level = "intermediate"

        # 기간 감지
        duration_weeks = 4
        week_patterns = [
            r'(\d+)주',
            r'(\d+)\s*week',
            r'(\d+)\s*달',
            r'(\d+)\s*month'
        ]

        for pattern in week_patterns:
            match = re.search(pattern, combined_text)
            if match:
                weeks = int(match.group(1))
                if 'month' in pattern or '달' in pattern:
                    weeks *= 4
                if 1 <= weeks <= 24:
                    duration_weeks = weeks
                    break

        # 시간 감지
        weekly_hours = 10
        hour_patterns = [
            r'(\d+)\s*시간',
            r'(\d+)\s*hour',
            r'주당\s*(\d+)',
            r'weekly\s*(\d+)'
        ]

        for pattern in hour_patterns:
            match = re.search(pattern, combined_text)
            if match:
                hours = int(match.group(1))
                if 1 <= hours <= 40:
                    weekly_hours = hours
                    break

        # 포커스 영역 추출
        focus_areas = []
        tech_keywords = [
            "python", "자바스크립트", "react", "django", "flask", "데이터", "ai", "머신러닝",
            "웹개발", "앱개발", "데이터베이스", "api", "프론트엔드", "백엔드", "풀스택"
        ]

        for keyword in tech_keywords:
            if keyword in combined_text:
                focus_areas.append(keyword)

        if not focus_areas:
            focus_areas = ["기초 개념", "실습"]

        return {
            "level": level,
            "duration_weeks": duration_weeks,
            "focus_areas": focus_areas[:3],  # 최대 3개
            "weekly_hours": weekly_hours
        }

    def _extract_duration_from_message(self, message: str) -> int:
        """사용자 메시지에서 기간 정보 추출"""
        if not message:
            return None

        message_lower = message.lower()

        # 기간 키워드 매핑 (주 단위) - 기존 시스템과 동일
        duration_patterns = {
            "1주": 1, "1week": 1, "일주일": 1,
            "2주": 2, "2week": 2, "이주": 2,
            "1개월": 4, "1month": 4, "한달": 4, "4주": 4,
            "2개월": 8, "2month": 8, "두달": 8, "8주": 8,
            "3개월": 12, "3month": 12, "세달": 12, "12주": 12,
            "4개월": 16, "4month": 16, "16주": 16,
            "5개월": 20, "5month": 20, "20주": 20,
            "6개월": 24, "6month": 24, "반년": 24, "24주": 24,
            "9개월": 36, "9month": 36,
            "1년": 52, "12개월": 52, "1year": 52, "52주": 52
        }

        # 메시지에서 기간 키워드 찾기
        for keyword, weeks in duration_patterns.items():
            if keyword in message_lower:
                return weeks

        # 숫자 패턴 매칭 (fallback)
        duration_regex_patterns = [
            r'(\d+)\s*주',
            r'(\d+)\s*week',
            r'(\d+)\s*달',
            r'(\d+)\s*month'
        ]

        for pattern in duration_regex_patterns:
            match = re.search(pattern, message_lower)
            if match:
                duration = int(match.group(1))
                if 'month' in pattern or '달' in pattern:
                    duration *= 4  # 월을 주로 변환

                if 1 <= duration <= 52:
                    return duration

        return None