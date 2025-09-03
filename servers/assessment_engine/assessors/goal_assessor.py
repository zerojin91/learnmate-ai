"""
Goal Assessor

LLM 기반 학습 목표 파악 클래스
"""

import json
from typing import List, Dict, Optional, Callable
from langchain_openai import ChatOpenAI


class GoalAssessor:
    """LLM 기반 학습 목표 파악 클래스 - MCP용으로 변환"""
    
    def __init__(self, llm: ChatOpenAI):
        """
        GoalAssessor 초기화
        
        Args:
            llm: LangChain ChatOpenAI 인스턴스
        """
        self.llm = llm
        self.llm_generator = self._create_llm_generator()
        
        self.system_prompt = """당신은 학습 목표 파악 전문가입니다.
사용자의 학습 동기와 목표를 정확히 파악하여 맞춤형 학습 경로를 제안하는 것이 목표입니다.

## 주요 목표 카테고리:
- **HOBBY**: 취미, 지식 확장, 개인적 성장, 호기심 충족
- **CAREER_CHANGE**: 이직, 전직, 새로운 분야 진입, 커리어 전환
- **SKILL_UPGRADE**: 현재 업무 스킬 향상, 승진 준비, 업무 효율성 증대
- **CERTIFICATION**: 자격증, 시험 준비, 학위 취득
- **PROJECT**: 특정 프로젝트, 창업 준비, 사이드 프로젝트

## 응답 형식:
반드시 JSON 형식으로 응답하세요:

**취업/이직 목표인 경우:**
{"goal": "백엔드 개발자로 이직", "category": "CAREER_CHANGE", "detail": "현재 마케터에서 개발자로 전향", "confidence": 0.9}

**스킬 향상 목표인 경우:**
{"goal": "업무 자동화", "category": "SKILL_UPGRADE", "detail": "반복 업무를 파이썬으로 자동화", "confidence": 0.8}

**취미 목표인 경우:**
{"goal": "개인 관심사", "category": "HOBBY", "detail": "데이터 분석에 대한 호기심", "confidence": 0.7}

## 판단 기준:
- **confidence**: 목표 파악에 대한 확신도 (0.0~1.0)
- **detail**: 구체적인 목표 설명
- 사용자의 표현에서 동기와 목적을 정확히 파악하세요"""
    
    def _create_llm_generator(self) -> Callable:
        """LLM 호출을 위한 간단한 generator 함수 생성"""
        def llm_generator(prompt: str, system_prompt: str = None) -> str:
            if system_prompt:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            else:
                messages = [{"role": "user", "content": prompt}]
            
            response = self.llm.invoke(messages)
            return response.content
        
        return llm_generator

    def identify_goal(self, user_input: str, conversation_context: List[str] = None) -> dict:
        """사용자 입력에서 학습 목표를 식별합니다."""
        try:
            # 맥락 정보 구성
            context_info = ""
            if conversation_context:
                context_info = f"\\n이전 대화 맥락:\\n" + "\\n".join(f"- {ctx}" for ctx in conversation_context[-3:])
            
            response = self.llm_generator(
                prompt=f"사용자 입력: {user_input}{context_info}",
                system_prompt=self.system_prompt
            )
            
            return json.loads(response)
            
        except Exception as e:
            print(f"목표 식별 중 오류 발생: {e}")
            return {
                "goal": "",
                "category": "HOBBY",
                "detail": "",
                "confidence": 0.0
            }
    
    def generate_goal_confirmation_question(self, goal_result: dict, user_input: str) -> str:
        """파악한 목표에 대한 자연스러운 확인 질문을 생성합니다."""
        
        confirmation_system_prompt = f"""당신은 친근하고 자연스러운 학습 상담사입니다.
사용자의 학습 목표를 파악한 결과를 자연스럽게 확인받는 질문을 생성해주세요.

현재 상황:
- 사용자 입력: "{user_input}"
- 파악된 목표: "{goal_result.get('goal', '')}"
- 목표 카테고리: {goal_result.get('category', '')}
- 확신도: {goal_result.get('confidence', 0.0):.1f}

목표:
1. 파악한 학습 목표를 사용자에게 확인받기
2. "제가 이해한 바로는 ~을 위해 공부하고 싶으신 것 같은데, 맞나요?" 형태의 자연스러운 질문
3. 사용자가 편안하게 답변할 수 있도록 유도

응답 스타일:
- 친근하고 자연스러운 대화체
- "제가 이해한 바로는", "~을 위해서", "목표가 ~인 것 같은데" 등의 표현 활용
- 겸손하고 확인받는 톤

한 문장 또는 두 문장으로 확인 질문해주세요."""

        try:
            confirmation_question = self.llm_generator(
                prompt=f"위 상황에서 자연스러운 목표 확인 질문을 생성해주세요.",
                system_prompt=confirmation_system_prompt
            )
            return confirmation_question.strip()
            
        except Exception as e:
            print(f"목표 확인 질문 생성 중 오류 발생: {e}")
            # 기본 질문으로 폴백
            goal = goal_result.get('goal', '학습 목표')
            return f"제가 이해한 바로는 '{goal}'을 위해 공부하고 싶으신 것 같은데, 맞나요?"
    
    def is_goal_confirmed(self, user_response: str, goal: str) -> dict:
        """사용자 응답이 목표를 확인하는 긍정적 답변인지 판단합니다."""
        
        confirmation_check_prompt = f"""다음 사용자 응답이 제안된 학습 목표에 대해 긍정적으로 확인하는 답변인지 판단해주세요.

제안된 목표: "{goal}"
사용자 응답: "{user_response}"

판단 기준:
- 긍정적 확인: "맞아요", "네", "그렇습니다", "정확해요", "맞네요" 등
- 부분적 동의: "비슷해요", "거의 맞아요", "그런 느낌이에요" 등  
- 부정적: "아니에요", "다른 목적이에요", "그게 아니라" 등
- 수정 제안: "~가 아니라 ~이에요", "~보다는 ~을 위해서" 등

반드시 JSON 형식으로 응답하세요:
{{"confirmed": true/false, "confidence": 0.0-1.0, "reason": "판단 근거"}}"""

        try:
            response = self.llm_generator(
                prompt=confirmation_check_prompt,
                system_prompt="당신은 사용자 응답을 정확히 분석하는 전문가입니다."
            )
            
            result = json.loads(response)
            return result
            
        except Exception as e:
            print(f"목표 확인 판단 중 오류 발생: {e}")
            # 기본 키워드로 판단
            positive_keywords = ["네", "맞", "그렇", "정확", "좋", "예", "응"]
            negative_keywords = ["아니", "다른", "틀린", "잘못"]
            
            user_lower = user_response.lower()
            has_positive = any(word in user_lower for word in positive_keywords)
            has_negative = any(word in user_lower for word in negative_keywords)
            
            if has_positive and not has_negative:
                return {"confirmed": True, "confidence": 0.8, "reason": "긍정 키워드 감지"}
            elif has_negative:
                return {"confirmed": False, "confidence": 0.8, "reason": "부정 키워드 감지"}
            else:
                return {"confirmed": False, "confidence": 0.3, "reason": "명확하지 않은 답변"}