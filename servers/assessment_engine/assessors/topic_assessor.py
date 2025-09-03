"""
Topic Assessor

LLM 기반 학습 주제 식별 및 Topic Evolution System
"""

import json
from typing import List, Dict, Optional, Callable
from langchain_openai import ChatOpenAI


class TopicAssessor:
    """LLM 기반 학습 주제 파악 클래스 - MCP용으로 변환"""
    
    def __init__(self, llm: ChatOpenAI):
        """
        TopicAssessor 초기화
        
        Args:
            llm: LangChain ChatOpenAI 인스턴스
        """
        self.llm = llm
        self.llm_generator = self._create_llm_generator()
        
        self.system_prompt = """당신은 학습 상담 전문가입니다. 사용자가 학습하고 싶어하는 주제를 정확히 파악해주세요.

## 목표:
사용자 입력에서 구체적이고 명확한 학습 주제를 식별하고, 추가 명료화가 필요한지 판단

## 판단 기준:
1. **구체성**: "프로그래밍"보다는 "파이썬 프로그래밍"이 더 구체적
2. **명확성**: 여러 해석이 가능한 경우 명료화 필요
3. **학습 가능성**: 실제 강의나 교육과정으로 존재할 수 있는 주제

## 출력 형식:
반드시 JSON 형식으로 응답하세요:
{
  "topic": "파악된 구체적인 학습 주제 (한글)",
  "confidence": 0.8,
  "needs_clarification": false,
  "reasoning": "판단 근거"
}

## needs_clarification 기준:
- confidence < 0.6이거나 너무 일반적인 주제일 때 true
- **topic**: 구체적이고 명확한 한글 용어 사용"""
    
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
    
    def identify_topic(self, user_input: str) -> dict:
        """사용자 입력에서 학습 주제를 식별합니다."""
        try:
            response = self.llm_generator(
                prompt=f"사용자 입력: {user_input}",
                system_prompt=self.system_prompt
            )
            
            # JSON 응답 파싱 시도
            return json.loads(response)
            
        except Exception as e:
            print(f"주제 식별 중 오류 발생: {e}")
            return {
                "topic": "",
                "confidence": 0.0,
                "needs_clarification": True
            }
    
    def generate_clarification_question(self, topic_result: dict, user_input: str) -> str:
        """상황에 맞는 자연스러운 명료화 질문을 생성합니다."""
        
        clarification_system_prompt = f"""당신은 친근하고 도움이 되는 학습 상담사입니다. 
사용자가 학습하고 싶어하는 주제를 더 구체적으로 파악하기 위해 자연스러운 질문을 생성해주세요.

현재 상황:
- 사용자 입력: "{user_input}"
- 파악된 주제: "{topic_result.get('topic', '불명확')}"
- 확신도: {topic_result.get('confidence', 0.0):.1f}

목표:
1. 사용자가 답변하기 쉽도록 친근하게 질문
2. 구체적인 예시나 선택지 제공
3. 부담스럽지 않게 추가 정보 유도

응답 스타일:
- 친근하고 자연스러운 대화체
- 격려하는 톤
- 구체적인 예시 포함

한 문장 또는 두 문장으로 질문해주세요."""

        try:
            clarification_question = self.llm_generator(
                prompt=f"위 상황에서 적절한 명료화 질문을 생성해주세요.",
                system_prompt=clarification_system_prompt
            )
            return clarification_question.strip()
            
        except Exception as e:
            print(f"명료화 질문 생성 중 오류 발생: {e}")
            # 기본 질문으로 폴백
            return f"좀 더 구체적으로 어떤 분야를 학습하고 싶으신가요? 예를 들어, 프로그래밍이라면 파이썬, 자바, 웹개발 등이 있습니다."
    
    def generate_topic_confirmation_question(self, topic_result: dict, user_input: str) -> str:
        """파악한 주제에 대한 자연스러운 확인 질문을 생성합니다."""
        
        confirmation_system_prompt = f"""당신은 친근하고 자연스러운 학습 상담사입니다.
사용자의 입력을 분석한 결과를 자연스럽게 확인받는 질문을 생성해주세요.

현재 상황:
- 사용자 입력: "{user_input}"
- 파악된 주제: "{topic_result.get('topic', '')}"
- 확신도: {topic_result.get('confidence', 0.0):.1f}

목표:
1. 파악한 주제를 사용자에게 확인받기
2. "제가 생각하기에 ~인 것 같은데, 어떻게 생각하시나요?" 형태의 자연스러운 질문
3. 사용자가 편안하게 답변할 수 있도록 유도

응답 스타일:
- 친근하고 자연스러운 대화체
- "제가 생각하기에", "~인 것 같은데", "어떻게 생각하시나요?" 등의 표현 활용
- 겸손하고 확인받는 톤

한 문장 또는 두 문장으로 확인 질문해주세요."""

        try:
            confirmation_question = self.llm_generator(
                prompt=f"위 상황에서 자연스러운 주제 확인 질문을 생성해주세요.",
                system_prompt=confirmation_system_prompt
            )
            return confirmation_question.strip()
            
        except Exception as e:
            print(f"확인 질문 생성 중 오류 발생: {e}")
            # 기본 질문으로 폴백
            topic = topic_result.get('topic', '학습 주제')
            return f"제가 생각하기에 지금 말씀하신 것은 '{topic}'에 관심이 있으신 것 같은데, 맞나요?"
    
    def analyze_topic_evolution(self, current_topic: str, new_user_input: str, conversation_context: List[str]) -> dict:
        """대화 맥락을 고려하여 주제 진화를 분석합니다."""
        
        # 전체 대화 맥락을 문자열로 구성
        context_text = "\\n".join([f"- {ctx}" for ctx in conversation_context[-3:]])  # 최근 3개 맥락만 사용
        
        evolution_analysis_prompt = f"""당신은 대화 맥락을 분석하여 사용자의 학습 주제가 어떻게 진화하고 있는지 판단하는 전문가입니다.

대화 맥락:
{context_text}

현재 파악된 주제: "{current_topic}"
새로운 사용자 입력: "{new_user_input}"

## 주제 진화 유형 분석 기준:
1. **REFINEMENT** (구체화): 기존 주제를 더 구체적으로 표현
   - 예: "프로그래밍" → "파이썬 프로그래밍"
   - 예: "웹개발" → "React 웹개발"

2. **SPECIFICATION** (세분화): 기존 주제 내에서 특정 영역으로 좁힘  
   - 예: "파이썬" → "파이썬 데이터 분석"
   - 예: "엑셀" → "엑셀 함수"

3. **LATERAL_SHIFT** (관련 분야 이동): 관련 있지만 다른 분야로 이동
   - 예: "파이썬" → "자바스크립트" 
   - 예: "엑셀" → "파워포인트"

4. **RADICAL_CHANGE** (완전 변경): 완전히 다른 분야로 변경
   - 예: "프로그래밍" → "요리"
   - 예: "엑셀" → "영어회화"

5. **CLARIFICATION** (명료화): 기존 주제에 대한 추가 설명이나 확장
   - 예: "엑셀" + "전반적인 내용을 배우고 싶다" → 엑셀 전반 기능

## 자연스러운 진화 판단:
- **자연스러운 진화**: REFINEMENT, SPECIFICATION, CLARIFICATION
- **확인이 필요한 진화**: LATERAL_SHIFT, RADICAL_CHANGE

반드시 JSON 형식으로 응답하세요:
{{
    "evolution_type": "REFINEMENT|SPECIFICATION|LATERAL_SHIFT|RADICAL_CHANGE|CLARIFICATION",
    "new_topic": "진화된 새로운 주제",
    "is_natural_evolution": true/false,
    "confidence": 0.0-1.0,
    "reasoning": "판단 근거"
}}"""

        try:
            response = self.llm_generator(
                prompt=evolution_analysis_prompt,
                system_prompt="당신은 대화 맥락을 정확히 분석하는 주제 진화 분석 전문가입니다."
            )
            
            return json.loads(response)
            
        except Exception as e:
            print(f"주제 진화 분석 중 오류 발생: {e}")
            return {
                "evolution_type": "CLARIFICATION",
                "new_topic": current_topic,
                "is_natural_evolution": True,
                "confidence": 0.3,
                "reasoning": "분석 오류로 기본값 사용"
            }

    def generate_evolution_confirmation(self, old_topic: str, new_topic: str, evolution_type: str, user_input: str) -> str:
        """진화 유형에 따른 자연스러운 확인 질문을 생성합니다."""
        
        evolution_confirmation_prompt = f"""당신은 사용자의 학습 의도를 자연스럽게 확인하는 친근한 상담사입니다.

상황:
- 이전 주제: "{old_topic}"
- 새로운 주제: "{new_topic}"
- 진화 유형: {evolution_type}
- 사용자 입력: "{user_input}"

진화 유형별 응답 가이드:
1. **REFINEMENT/SPECIFICATION/CLARIFICATION**: 자연스러운 구체화로 받아들이고 확인
   - "아, {old_topic} 중에서도 특히 {new_topic}에 관심이 있으시군요!"
   - "제가 이해한 바로는 {new_topic}를 학습하고 싶으신 것 같은데, 맞나요?"

2. **LATERAL_SHIFT**: 관련 분야 변경에 대한 확인  
   - "아, {old_topic}에서 {new_topic}로 바꾸고 싶으신 건가요?"
   - "{old_topic} 대신 {new_topic}를 배우고 싶으신 건지 확인해보고 싶습니다."

3. **RADICAL_CHANGE**: 급격한 변경에 대한 재확인
   - "잠깐, {old_topic}에서 {new_topic}로 완전히 바꾸고 싶으신 건가요?"
   - "처음에 말씀하신 {old_topic}와 다르게 {new_topic}를 원하시는 건가요?"

응답 스타일:
- 친근하고 자연스러운 대화체
- 사용자의 의도를 존중하는 톤
- 명확한 확인을 요청하되 부담스럽지 않게

한 문장 또는 두 문장으로 자연스러운 확인 질문을 생성해주세요."""

        try:
            confirmation_question = self.llm_generator(
                prompt=evolution_confirmation_prompt,
                system_prompt="당신은 사용자의 의도를 자연스럽게 확인하는 친근한 상담사입니다."
            )
            return confirmation_question.strip()
            
        except Exception as e:
            print(f"진화 확인 질문 생성 중 오류 발생: {e}")
            # 진화 유형에 따른 기본 질문
            if evolution_type in ["REFINEMENT", "SPECIFICATION", "CLARIFICATION"]:
                return f"제가 이해한 바로는 '{new_topic}'를 학습하고 싶으신 것 같은데, 맞나요?"
            elif evolution_type == "LATERAL_SHIFT":
                return f"아, '{old_topic}'에서 '{new_topic}'로 바꾸고 싶으신 건가요?"
            else:  # RADICAL_CHANGE
                return f"잠깐, '{old_topic}'에서 '{new_topic}'로 완전히 바꾸고 싶으신 건가요?"

    def is_topic_confirmed(self, user_response: str, topic: str) -> dict:
        """사용자 응답이 주제를 확인하는 긍정적 답변인지 판단합니다."""
        
        confirmation_check_prompt = f"""다음 사용자 응답이 제안된 주제에 대해 긍정적으로 확인하는 답변인지 판단해주세요.

제안된 주제: "{topic}"
사용자 응답: "{user_response}"

판단 기준:
- 긍정적 확인: "맞아요", "네", "그렇습니다", "정확해요", "맞네요" 등
- 부분적 동의: "비슷해요", "거의 맞아요" 등  
- 부정적: "아니에요", "다른 걸", "그게 아니라" 등
- 수정 제안: "~가 아니라 ~예요" 등

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
            print(f"주제 확인 판단 중 오류 발생: {e}")
            # 기본 키워드로 판단
            positive_keywords = ["네", "맞", "그렇", "정확", "좋", "예", "응"]
            negative_keywords = ["아니", "다른", "틀린", "잘못"]
            
            user_lower = user_response.lower()
            has_positive = any(word in user_lower for word in positive_keywords)
            has_negative = any(word in user_lower for word in negative_keywords)
            
            if has_positive and not has_negative:
                return {"confirmed": True, "confidence": 0.7, "reason": "긍정적 키워드 감지"}
            elif has_negative:
                return {"confirmed": False, "confidence": 0.8, "reason": "부정적 키워드 감지"}
            else:
                return {"confirmed": False, "confidence": 0.3, "reason": "명확하지 않은 응답"}