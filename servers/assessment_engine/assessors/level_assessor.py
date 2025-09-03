"""
Level Assessor

LLM 기반 학습 수준 측정 클래스 - 리팩토링된 버전
"""

import json
from typing import List, Dict, Optional, Callable
from langchain_openai import ChatOpenAI


class LevelAssessor:
    """LLM 기반 학습 수준 측정 클래스 - MCP용으로 변환 (리팩토링된 버전)"""
    
    def __init__(self, llm: ChatOpenAI):
        """
        LevelAssessor 초기화
        
        Args:
            llm: LangChain ChatOpenAI 인스턴스
        """
        self.llm = llm
        self.llm_generator = self._create_llm_generator()
        
        self.system_prompt = """당신은 학습 수준 측정 전문가입니다. 
사용자의 답변을 종합적으로 분석하여 해당 주제에 대한 현재 학습 수준을 정확히 파악해주세요.

## 📊 분석해야 할 영역:
1. **이론적 지식**: 기본 개념, 용어, 원리에 대한 이해도
2. **실무 경험**: 실제 프로젝트, 업무, 실습 경험
3. **문제 해결 능력**: 복잡한 문제에 대한 접근 방식
4. **학습 의지**: 더 깊이 배우고자 하는 의욕과 목표

## 🏷️ 수준 카테고리 분류:
- **초급 (BEGINNER)**: 기본 개념을 모르거나 경험이 전혀 없음
- **중급 (INTERMEDIATE)**: 기본 개념 이해, 간단한 실습/프로젝트 경험
- **고급 (ADVANCED)**: 심화 개념 이해, 복잡한 프로젝트나 실무 경험

## 📋 응답 형식 (JSON):
```json
{
    "level": "BEGINNER|INTERMEDIATE|ADVANCED",
    "confidence": 0.0-1.0,
    "theoretical_knowledge": "상세 평가",
    "practical_experience": "경험 수준 평가", 
    "problem_solving": "문제해결 능력 평가",
    "learning_readiness": "학습 준비도 평가",
    "reasoning": "종합 판단 근거"
}
```

## 💡 평가 원칙:
- 사용자가 명시적으로 "모른다"고 하면 BEGINNER
- 기본 용어나 개념을 설명할 수 있으면 INTERMEDIATE
- 심화 내용이나 실무 경험이 있으면 ADVANCED  
- 애매할 때는 보수적으로 한 단계 낮게 평가"""
    
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
    
    def identify_level(self, topic: str, user_input: str, conversation_context: List[str] = None) -> dict:
        """사용자 입력을 분석하여 해당 주제의 학습 수준을 파악합니다."""
        context = ""
        if conversation_context:
            context = f"이전 대화 맥락: {' | '.join(conversation_context[-3:])}\n\n"
        
        prompt = f"""{self.system_prompt}

{context}주제: {topic}
사용자 답변: "{user_input}"

위 답변을 분석하여 '{topic}'에 대한 사용자의 현재 학습 수준을 JSON 형태로 파악해주세요."""
        
        response = self.llm_generator(prompt)
        
        try:
            result = json.loads(response.strip())
            
            # 기본값 설정
            if 'level' not in result:
                result['level'] = 'BEGINNER'
            if 'confidence' not in result:
                result['confidence'] = 0.5
                
            return result
            
        except (json.JSONDecodeError, KeyError) as e:
            # JSON 파싱 실패시 기본값 반환
            return {
                "level": "BEGINNER",
                "confidence": 0.3,
                "theoretical_knowledge": "평가 불가",
                "practical_experience": "정보 부족", 
                "problem_solving": "평가 불가",
                "learning_readiness": "관심 있음",
                "reasoning": f"답변 분석 어려움: {str(e)}"
            }
    
    def generate_level_confirmation_question(self, level_result: dict, topic: str, user_input: str) -> str:
        """수준 측정 확인 질문을 생성합니다."""
        level = level_result.get('level', 'BEGINNER')
        theoretical = level_result.get('theoretical_knowledge', '')
        practical = level_result.get('practical_experience', '')
        
        # 수준별 설명
        level_desc = {
            'BEGINNER': '기초부터 차근차근',
            'INTERMEDIATE': '기본기를 다지면서 실무 위주로', 
            'ADVANCED': '심화 내용과 고급 기법 중심으로'
        }
        
        prompt = f"""사용자가 "{user_input}"라고 답했습니다.

제가 파악한 {topic} 수준:
- 현재 수준: {level}
- 이론적 지식: {theoretical}
- 실무 경험: {practical}
- 추천 학습 방향: {level_desc.get(level, '적절한 수준에서')}

이 파악이 맞는지 자연스럽게 확인하는 질문을 만들어주세요.
"제가 생각하기에..." 형태로 시작해서 친근하게 물어보세요."""
        
        response = self.llm_generator(prompt)
        return response.strip()
    
    def is_level_confirmed(self, user_response: str, level_result: dict) -> dict:
        """사용자 답변이 수준 측정을 확인하는지 분석합니다."""
        level = level_result.get('level', 'BEGINNER')
        
        prompt = f"""사용자가 수준 측정에 대한 확인 질문에 "{user_response}"라고 답했습니다.

확인하려던 내용:
- 측정된 수준: {level}

이 답변이 확인(동의)인지 아니면 수정 요청인지 판단해주세요.

JSON 형식으로 답해주세요:
{{"confirmed": true/false, "confidence": 0.0-1.0, "reason": "판단근거"}}"""
        
        response = self.llm_generator(prompt)
        
        try:
            result = json.loads(response.strip())
            return result
        except:
            # 간단한 키워드 기반 분석
            positive_keywords = ['맞', '네', '그렇', '좋', '동의', '확인', 'ㅇㅇ', 'ㅇㅋ']
            negative_keywords = ['아니', '틀렸', '다시', '수정', '바꾸', '변경', '더', '덜']
            
            user_lower = user_response.lower()
            has_positive = any(keyword in user_lower for keyword in positive_keywords)
            has_negative = any(keyword in user_lower for keyword in negative_keywords)
            
            if has_positive and not has_negative:
                return {"confirmed": True, "confidence": 0.8, "reason": "긍정 키워드 감지"}
            elif has_negative:
                return {"confirmed": False, "confidence": 0.8, "reason": "부정 키워드 감지"}
            else:
                return {"confirmed": False, "confidence": 0.3, "reason": "명확하지 않은 답변"}