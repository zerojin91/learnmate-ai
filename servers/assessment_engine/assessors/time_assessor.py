"""
Time Assessor

LLM 기반 학습 시간 가용성 파악 클래스
"""

import json
from typing import List, Dict, Optional, Callable
from langchain_openai import ChatOpenAI


class TimeAssessor:
    """LLM 기반 학습 시간 가용성 파악 클래스 - MCP용으로 변환"""
    
    def __init__(self, llm: ChatOpenAI):
        """
        TimeAssessor 초기화
        
        Args:
            llm: LangChain ChatOpenAI 인스턴스
        """
        self.llm = llm
        self.llm_generator = self._create_llm_generator()
        
        self.system_prompt = """당신은 학습 시간 가용성 파악 전문가입니다.

사용자의 답변을 분석하여 다음 정보를 파악해주세요:

## 📅 분석해야 할 영역:
1. **주간 가능 시간**: 일주일에 몇 시간 정도 학습할 수 있는지
2. **시간대 선호**: 언제 주로 학습하고 싶어하는지 (평일저녁, 주말, 새벽 등)
3. **학습 기간**: 얼마나 오랫동안 학습할 계획인지
4. **일정 유연성**: 학습 일정이 얼마나 유연한지

## 🏷️ 시간 카테고리 분류:
- **INTENSIVE**: 주 20시간 이상 (하루 3시간 이상, 집중 학습)
- **REGULAR**: 주 10-20시간 (하루 1-3시간, 꾸준한 학습)
- **MODERATE**: 주 5-10시간 (주 2-3일, 적당한 학습)
- **MINIMAL**: 주 5시간 미만 (틈틈이, 가벼운 학습)

## 📋 응답 형식 (JSON):
```json
{
    "weekly_hours": 숫자,
    "category": "INTENSIVE|REGULAR|MODERATE|MINIMAL",
    "preferred_schedule": "설명",
    "duration": "예상 학습 기간",
    "flexibility": "HIGH|MEDIUM|LOW",
    "confidence": 0.0-1.0,
    "reasoning": "판단 근거"
}
```

## 💡 주의사항:
- 구체적 숫자가 없으면 패턴과 맥락으로 추정
- 직장인/학생 등 상황 고려
- 현실적 평가 우선 (과도한 계획 지양)
- 불확실할 땐 보수적 추정"""
    
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
    
    def identify_time_availability(self, user_input: str, conversation_context: List[str] = None) -> dict:
        """사용자 입력을 분석하여 시간 가용성을 파악합니다."""
        context = ""
        if conversation_context:
            context = f"이전 대화 맥락: {' | '.join(conversation_context[-3:])}\n\n"
        
        prompt = f"""{self.system_prompt}

{context}사용자 답변: "{user_input}"

위 답변을 분석하여 JSON 형태로 시간 가용성을 파악해주세요."""
        
        response = self.llm_generator(prompt)
        
        try:
            result = json.loads(response.strip())
            
            # 기본값 설정
            if 'weekly_hours' not in result:
                result['weekly_hours'] = 5
            if 'category' not in result:
                result['category'] = 'MODERATE'
            if 'confidence' not in result:
                result['confidence'] = 0.5
                
            return result
            
        except (json.JSONDecodeError, KeyError) as e:
            # JSON 파싱 실패시 기본값 반환
            return {
                "weekly_hours": 5,
                "category": "MODERATE", 
                "preferred_schedule": "주 2-3회",
                "duration": "3개월",
                "flexibility": "MEDIUM",
                "confidence": 0.3,
                "reasoning": f"답변 분석 어려움: {str(e)}"
            }
    
    def generate_time_confirmation_question(self, time_result: dict, user_input: str) -> str:
        """시간 가용성 확인 질문을 생성합니다."""
        weekly_hours = time_result.get('weekly_hours', 5)
        category = time_result.get('category', 'MODERATE')
        preferred_schedule = time_result.get('preferred_schedule', '일정')
        
        # 카테고리별 설명
        category_desc = {
            'INTENSIVE': '집중적으로 많은 시간을',
            'REGULAR': '꾸준히 정기적으로',
            'MODERATE': '적당한 페이스로',
            'MINIMAL': '틈틈이 가볍게'
        }
        
        prompt = f"""사용자가 "{user_input}"라고 답했습니다.

제가 파악한 시간 가용성:
- 주간 학습 시간: 약 {weekly_hours}시간
- 학습 방식: {category_desc.get(category, '적당히')} 
- 선호 일정: {preferred_schedule}

이 파악이 맞는지 자연스럽게 확인하는 질문을 만들어주세요.
"제가 생각하기에..." 형태로 시작해서 친근하게 물어보세요."""
        
        response = self.llm_generator(prompt)
        return response.strip()
    
    def is_time_confirmed(self, user_response: str, time_result: dict) -> dict:
        """사용자 답변이 시간 가용성을 확인하는지 분석합니다."""
        weekly_hours = time_result.get('weekly_hours', 5)
        category = time_result.get('category', 'MODERATE')
        
        prompt = f"""사용자가 시간 가용성에 대한 확인 질문에 "{user_response}"라고 답했습니다.

확인하려던 내용:
- 주간 {weekly_hours}시간 정도 학습
- {category} 방식으로 진행

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
            negative_keywords = ['아니', '틀렸', '다시', '수정', '바꾸', '변경']
            
            user_lower = user_response.lower()
            has_positive = any(keyword in user_lower for keyword in positive_keywords)
            has_negative = any(keyword in user_lower for keyword in negative_keywords)
            
            if has_positive and not has_negative:
                return {"confirmed": True, "confidence": 0.8, "reason": "긍정 키워드 감지"}
            elif has_negative:
                return {"confirmed": False, "confidence": 0.8, "reason": "부정 키워드 감지"}
            else:
                return {"confirmed": False, "confidence": 0.3, "reason": "명확하지 않은 답변"}