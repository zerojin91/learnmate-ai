"""
Base Agent 클래스 정의
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
import sys
import json
import re
from datetime import datetime

from .state import CurriculumState, ProcessingPhase, update_phase, add_error


class BaseAgent(ABC):
    """모든 커리큘럼 생성 에이전트의 기본 클래스"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.agent_name = self.__class__.__name__

    @abstractmethod
    async def execute(self, state: CurriculumState) -> CurriculumState:
        """에이전트의 주요 실행 로직"""
        pass

    def log_debug(self, message: str):
        """디버그 로그 출력"""
        print(f"DEBUG [{self.agent_name}]: {message}", file=sys.stderr, flush=True)

    def log_progress(self, phase: str, message: str):
        """진행 상태 로그"""
        print(f"PROGRESS [{phase}]: {message}", file=sys.stderr, flush=True)

    async def call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """LLM 호출 헬퍼"""
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = await self.llm.agenerate([messages])
            return response.generations[0][0].text if response.generations else ""
        except Exception as e:
            self.log_debug(f"LLM call failed: {e}")
            raise

    def extract_json_from_text(self, text: str) -> Dict[str, Any]:
        """텍스트에서 JSON 추출"""
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError as e:
                self.log_debug(f"JSON parsing failed: {e}")
                raise
        else:
            raise ValueError("No JSON found in text")

    def safe_update_phase(self, state: CurriculumState, new_phase: ProcessingPhase, message: str = ""):
        """안전한 상태 업데이트"""
        try:
            update_phase(state, new_phase, message)
            self.log_progress(new_phase.value, message)
        except Exception as e:
            self.log_debug(f"Phase update failed: {e}")
            add_error(state, f"Phase update failed: {e}")

    def handle_error(self, state: CurriculumState, error: Exception, context: str = ""):
        """에러 처리"""
        error_msg = f"{context}: {str(error)}" if context else str(error)
        self.log_debug(f"Error in {self.agent_name}: {error_msg}")
        add_error(state, error_msg)
        return state