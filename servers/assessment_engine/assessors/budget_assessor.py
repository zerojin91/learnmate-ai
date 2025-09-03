"""
Budget Assessor

LLM 기반 학습 예산 범위 파악 클래스
"""

import json
from typing import List, Dict, Optional, Callable
from langchain_openai import ChatOpenAI


class BudgetAssessor:
    """LLM 기반 학습 예산 범위 파악 클래스 - MCP용으로 변환"""
    
    def __init__(self, llm: ChatOpenAI):
        """
        BudgetAssessor 초기화
        
        Args:
            llm: LangChain ChatOpenAI 인스턴스
        """
        self.llm = llm
        self.llm_generator = self._create_llm_generator()
        
        self.system_prompt = """당신은 학습 예산 범위 파악 전문가입니다.

사용자의 답변을 분석하여 다음 정보를 파악해주세요:

## 💰 분석해야 할 영역:
1. **월 예산 범위**: 한 달에 얼마나 학습비용을 쓸 수 있는지
2. **우선순위**: 무료 vs 유료, 품질 vs 비용 중요도
3. **지불 방식**: 월정액 vs 일시불 vs 강의별 결제 선호
4. **예산 유연성**: 예산이 얼마나 조정 가능한지

## 🏷️ 예산 카테고리 분류:
- **FREE_ONLY**: 무료만 가능 (0원, 무료 강의만)
- **BUDGET**: 최소 예산 (월 1-3만원, 저렴한 유료 강의)
- **STANDARD**: 일반 예산 (월 3-10만원, 일반적인 온라인 강의)
- **PREMIUM**: 충분한 예산 (월 10만원 이상, 프리미엄 강의/과정)

## 📋 응답 형식 (JSON):
```json
{
    "category": "FREE_ONLY|BUDGET|STANDARD|PREMIUM",
    "max_monthly_budget": 숫자,
    "preference": "free_priority|cost_effective|quality_focus|premium_focus",
    "payment_preference": "monthly|onetime|per_course",
    "flexibility": "HIGH|MEDIUM|LOW",
    "confidence": 0.0-1.0,
    "reasoning": "판단 근거"
}
```

## 💡 주의사항:
- 직접적인 금액 언급이 없으면 맥락으로 추정
- 학생/취업준비생은 보수적으로, 직장인은 현실적으로
- "비싸면 안돼" = BUDGET, "돈은 상관없어" = PREMIUM
- 무료 선호 표현시 FREE_ONLY 우선 고려
- 불확실할 땐 STANDARD로 추정"""
    
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
    
    def identify_budget_range(self, user_input: str, conversation_context: List[str] = None) -> dict:
        """사용자 입력을 분석하여 예산 범위를 파악합니다."""
        context = ""
        if conversation_context:
            context = f"이전 대화 맥락: {' | '.join(conversation_context[-3:])}\n\n"
        
        prompt = f"""{self.system_prompt}

{context}사용자 답변: "{user_input}"

위 답변을 분석하여 JSON 형태로 예산 범위를 파악해주세요."""
        
        response = self.llm_generator(prompt)
        
        try:
            result = json.loads(response.strip())
            
            # 기본값 설정
            if 'category' not in result:
                result['category'] = 'STANDARD'
            if 'max_monthly_budget' not in result:
                budget_defaults = {
                    'FREE_ONLY': 0,
                    'BUDGET': 20000,
                    'STANDARD': 50000,
                    'PREMIUM': 150000
                }
                result['max_monthly_budget'] = budget_defaults.get(result['category'], 50000)
            if 'confidence' not in result:
                result['confidence'] = 0.5
                
            return result
            
        except (json.JSONDecodeError, KeyError) as e:
            # JSON 파싱 실패시 기본값 반환
            return {
                "category": "STANDARD",
                "max_monthly_budget": 50000,
                "preference": "cost_effective", 
                "payment_preference": "monthly",
                "flexibility": "MEDIUM",
                "confidence": 0.3,
                "reasoning": f"답변 분석 어려움: {str(e)}"
            }
    
    def generate_budget_confirmation_question(self, budget_result: dict, user_input: str) -> str:
        """예산 범위 확인 질문을 생성합니다."""
        category = budget_result.get('category', 'STANDARD')
        max_budget = budget_result.get('max_monthly_budget', 50000)
        preference = budget_result.get('preference', 'cost_effective')
        
        # 카테고리별 설명
        category_desc = {
            'FREE_ONLY': '무료 강의만',
            'BUDGET': '저렴한 유료 강의도',
            'STANDARD': '적당한 가격대의 강의',
            'PREMIUM': '고품질 프리미엄 강의'
        }
        
        prompt = f"""사용자가 "{user_input}"라고 답했습니다.

제가 파악한 예산 범위:
- 카테고리: {category_desc.get(category, '적당한 수준')}
- 월 최대 예산: 약 {max_budget:,}원
- 선호도: {preference}

이 파악이 맞는지 자연스럽게 확인하는 질문을 만들어주세요.
"제가 생각하기에..." 형태로 시작해서 친근하게 물어보세요."""
        
        response = self.llm_generator(prompt)
        return response.strip()
    
    def is_budget_confirmed(self, user_response: str, budget_result: dict) -> dict:
        """사용자 답변이 예산 범위를 확인하는지 분석합니다."""
        category = budget_result.get('category', 'STANDARD')
        max_budget = budget_result.get('max_monthly_budget', 50000)
        
        prompt = f"""사용자가 예산 범위에 대한 확인 질문에 "{user_response}"라고 답했습니다.

확인하려던 내용:
- {category} 범위의 강의
- 월 최대 {max_budget:,}원 정도

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
            negative_keywords = ['아니', '틀렸', '다시', '수정', '바꾸', '변경', '너무']
            
            user_lower = user_response.lower()
            has_positive = any(keyword in user_lower for keyword in positive_keywords)
            has_negative = any(keyword in user_lower for keyword in negative_keywords)
            
            if has_positive and not has_negative:
                return {"confirmed": True, "confidence": 0.8, "reason": "긍정 키워드 감지"}
            elif has_negative:
                return {"confirmed": False, "confidence": 0.8, "reason": "부정 키워드 감지"}
            else:
                return {"confirmed": False, "confidence": 0.3, "reason": "명확하지 않은 답변"}