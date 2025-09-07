"""
Topic Assessment MCP Server

사용자의 학습 주제만 파악하는 단순한 MCP 서버
"""

from mcp.server.fastmcp import FastMCP
from langchain_openai import ChatOpenAI
import json

# FastMCP 서버 생성
mcp = FastMCP(
    "TopicAssessment",
    instructions="사용자의 학습 주제를 파악하는 도구를 제공합니다."
)

# LLM 초기화
llm = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama", 
    model="midm-2.0:base",
    temperature=0.0,
    max_tokens=1024
)

# 글로벌 상태 관리
assessment_state = {
    "current_stage": "topic",  # topic -> goal -> time -> budget -> complete
    "topic": {"value": None, "confidence": 0.0, "confirmed": False},
    "goal": {"value": None, "confidence": 0.0, "confirmed": False}, 
    "time": {"value": None, "confidence": 0.0, "confirmed": False},
    "budget": {"value": None, "confidence": 0.0, "confirmed": False},
    "conversation_history": [],
    "stage_attempts": {"topic": 0, "goal": 0, "time": 0, "budget": 0}
}

print(f"🎯 Multi-Tool Assessment MCP 서버 초기화 완료")
print(f"🤖 사용 중인 LLM: {llm.model_name}")


def can_proceed_to_next_stage() -> bool:
    """다음 단계로 진행 가능한지 확인"""
    current_stage = assessment_state["current_stage"]
    
    if current_stage == "topic":
        return assessment_state["topic"]["confirmed"]
    elif current_stage == "goal":
        return assessment_state["goal"]["confirmed"]
    elif current_stage == "time":
        return assessment_state["time"]["confirmed"]
    elif current_stage == "budget":
        return assessment_state["budget"]["confirmed"]
    else:
        return False

def advance_to_next_stage():
    """다음 단계로 진행"""
    current = assessment_state["current_stage"]
    stage_order = ["topic", "goal", "time", "budget", "complete"]
    
    try:
        current_index = stage_order.index(current)
        if current_index < len(stage_order) - 1:
            assessment_state["current_stage"] = stage_order[current_index + 1]
            print(f"📈 단계 진행: {current} → {assessment_state['current_stage']}")
    except ValueError:
        pass

@mcp.tool()
def assess_topic(user_message: str) -> dict:
    """
    사용자 메시지에서 학습 주제만 파악합니다.
    
    Args:
        user_message: 사용자가 입력한 메시지
        
    Returns:
        dict: 주제 파악 결과
    """
    print(f"📚 주제 파악 요청: {user_message}")
    assessment_state["stage_attempts"]["topic"] += 1
    
    try:
        # 주제 파악 전용 프롬프트 - TOPIC에만 집중
        system_prompt = """당신은 학습 주제만 파악하는 전문가입니다.

🎯 **현재 단계: TOPIC (무엇을 배우고 싶은가?)**

사용자 메시지에서 구체적인 학습 주제를 찾아주세요.
목적, 시간, 예산은 다음 단계에서 다룹니다. 지금은 TOPIC에만 집중하세요.

## 주제 파악 기준:
- 구체적: "파이썬", "웹개발", "머신러닝", "이미지 분류" (좋음) 
- 모호함: "프로그래밍", "컴퓨터", "공부", "개발" (더 구체화 필요)
- 확신도: 0.0-1.0 (얼마나 확실한가)
- **강제 규칙**: confidence >= 0.8이면 **반드시** next_action = "need_user_confirmation"

## ✅ 올바른 질문 (TOPIC 세분화):
- "어떤 프로그래밍 언어에 관심이 있으신가요?"
- "구체적으로 어떤 분야를 공부하고 싶으신가요?"
- "웹개발, 앱개발, 데이터분석 중 어떤 것인가요?"

## ❌ 잘못된 질문 (다른 단계):
- "왜 배우고 싶으신가요?" (GOAL 단계)
- "언제까지 배우실 건가요?" (TIME 단계)
- "예산은 얼마인가요?" (BUDGET 단계)

## 응답 예시:

입력: "개발자가 되고 싶어"
출력: {
  "category": "topic",
  "value": "개발",
  "confidence": 0.6,
  "confirmed": false,
  "friendly_response": "개발에 관심이 있으시는군요!",
  "follow_up_question": "구체적으로 어떤 개발 분야인가요? (웹개발, 앱개발, 게임개발, 데이터분석 등)",
  "next_action": "need_clarification"
}

입력: "웹개발자가 되고 싶어"
출력: {
  "category": "topic",
  "value": "웹개발",
  "confidence": 0.9,
  "confirmed": false,
  "friendly_response": "웹개발자가 되고 싶으시는군요! 멋진 목표입니다.",
  "follow_up_question": "주제를 '웹개발'로 확정하고 다음 단계(학습 목적)로 넘어가시겠습니까? 맞으면 '네' 또는 '확정', 더 구체화하시려면 추가 설명해 주세요.",
  "next_action": "need_user_confirmation"
}

입력: "이미지 분류 배우고 싶어"
출력: {
  "category": "topic", 
  "value": "이미지 분류",
  "confidence": 0.9,
  "confirmed": false,
  "friendly_response": "이미지 분류에 관심이 있으시는군요! AI 분야의 핵심 기술입니다.",
  "follow_up_question": "주제를 '이미지 분류'로 확정하고 다음 단계(학습 목적)로 넘어가시겠습니까? 맞으면 '네' 또는 '확정', 더 구체화하시려면 추가 설명해 주세요.",
  "next_action": "need_user_confirmation"
}

## ⚠️ 절대 규칙:
1. confidence >= 0.8이면 **무조건** next_action = "need_user_confirmation"
2. confidence >= 0.8이면 follow_up_question은 **반드시** 확정 질문
3. 더 이상 세분화 질문 금지

반드시 위 JSON 형식으로만 응답하세요."""

        # LLM 호출
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"사용자 메시지: {user_message}"}
        ])
        
        # JSON 응답 파싱
        try:
            result = json.loads(response.content)
            
            # 상태 업데이트 (자동 확정 제거)
            if "value" in result and result["value"]:
                assessment_state["topic"]["value"] = result["value"]
                assessment_state["topic"]["confidence"] = result.get("confidence", 0.0)
                
                # confirmed는 사용자 명시적 확인 후에만 설정
                # 자동 확정 및 단계 진행 제거
                print(f"📝 주제 파악됨: {result['value']} (확신도: {result.get('confidence', 0.0):.1f})")
            
            # 대화 기록 저장
            assessment_state["conversation_history"].append({
                "stage": "topic",
                "user_message": user_message,
                "result": result
            })
            
            print(f"✅ 주제 파악 완료: {result}")
            return result
            
        except json.JSONDecodeError:
            print(f"❌ JSON 파싱 실패. 원본 응답: {response.content}")
            # 단순한 fallback 응답
            return {
                "category": "topic",
                "value": None,
                "confidence": 0.1,
                "confirmed": False,
                "friendly_response": "학습 상담을 시작해보겠습니다.",
                "follow_up_question": "어떤 분야를 공부하고 싶으신지 구체적으로 알려주세요.",
                "next_action": "need_clarification"
            }
            
    except Exception as e:
        print(f"❌ 주제 파악 중 오류: {str(e)}")
        return {
            "category": "topic",
            "value": None,
            "confidence": 0.0,
            "confirmed": False,
            "friendly_response": "죄송합니다. 다시 말씀해 주시겠어요?",
            "follow_up_question": "어떤 것을 배우고 싶으신가요?",
            "next_action": "need_clarification"
        }


@mcp.tool()
def assess_goal(user_message: str) -> dict:
    """
    사용자 메시지에서 학습 목적을 파악합니다.
    
    Args:
        user_message: 사용자가 입력한 메시지
        
    Returns:
        dict: 목적 파악 결과
    """
    print(f"🎯 목적 파악 요청: {user_message}")
    assessment_state["stage_attempts"]["goal"] += 1
    
    # 주제가 확정되지 않았으면 거부
    if not assessment_state["topic"]["confirmed"]:
        return {
            "category": "goal",
            "value": None,
            "confidence": 0.0,
            "confirmed": False,
            "friendly_response": "먼저 학습 주제를 확정해야 합니다.",
            "follow_up_question": "어떤 것을 공부하고 싶으신가요?",
            "next_action": "need_topic_first"
        }
    
    try:
        confirmed_topic = assessment_state["topic"]["value"]
        
        # 목적 파악 전용 프롬프트 - GOAL에만 집중
        system_prompt = f"""당신은 학습 목적만 파악하는 전문가입니다.

🎯 **현재 단계: GOAL (왜 배우고 싶은가?)**

주제는 이미 '{confirmed_topic}'로 확정되었습니다.
이제 WHY(왜 배우려는가)만 파악하면 됩니다.
시간, 예산은 다음 단계에서 다룹니다. 지금은 GOAL에만 집중하세요.

## 목적 파악 기준:
- 구체적: "취업", "이직", "업무개선", "자격증", "창업", "부업" (좋음)
- 모호함: "그냥", "재미있어서", "필요할 것 같아서", "도움될 것 같아서" (더 구체화 필요)
- 확신도: 0.0-1.0 (얼마나 확실한가)
- 확정: confidence >= 0.7이면 confirmed = true

## ✅ 올바른 질문 (GOAL 구체화):
- "구체적으로 어떤 목적으로 활용하고 싶으신가요?"
- "취업, 이직, 업무개선 중 어떤 목표인가요?"
- "왜 {confirmed_topic}을 배우고 싶으신가요?"

## ❌ 잘못된 질문 (다른 단계):
- "어떤 분야의 {confirmed_topic}인가요?" (TOPIC 단계, 이미 확정됨)
- "언제까지 배우실 건가요?" (TIME 단계)
- "예산은 얼마인가요?" (BUDGET 단계)

## 응답 예시:

입력: "취업하고 싶어"
출력: {{
  "category": "goal",
  "value": "취업",
  "confidence": 0.9,
  "confirmed": false,
  "friendly_response": "{confirmed_topic}을 통해 취업을 목표로 하고 계시는군요! 좋은 선택입니다.",
  "follow_up_question": "목적을 '취업'으로 확정하고 다음 단계(학습 시간)로 넘어가시겠습니까? 맞으면 '네' 또는 '확정', 더 구체화하시려면 추가 설명해 주세요.",
  "next_action": "need_user_confirmation"
}}

입력: "이직을 위해서요"
출력: {{
  "category": "goal",
  "value": "이직",
  "confidence": 0.9,
  "confirmed": false,
  "friendly_response": "이직을 위해 {confirmed_topic}을 배우려고 하시는군요! 멋진 계획입니다.",
  "follow_up_question": "목적을 '이직'으로 확정하고 다음 단계(학습 시간)로 넘어가시겠습니까? 맞으면 '네' 또는 '확정', 더 구체화하시려면 추가 설명해 주세요.",
  "next_action": "need_user_confirmation"
}}

입력: "그냥 배워보고 싶어서요"
출력: {{
  "category": "goal",
  "value": "개인적 관심",
  "confidence": 0.4,
  "confirmed": false,
  "friendly_response": "{confirmed_topic}에 관심을 가지고 계시는군요.",
  "follow_up_question": "구체적으로 어떤 용도로 활용하고 싶으신가요? (취업, 이직, 업무개선, 창업, 자격증, 부업 등)",
  "next_action": "need_clarification"
}}

## ⚠️ 절대 규칙:
1. confidence >= 0.8이면 **무조건** next_action = "need_user_confirmation"
2. confidence >= 0.8이면 follow_up_question은 **반드시** 확정 질문 ("목적을 'X'로 확정하고...")
3. **금지**: "구체적으로", "어떤 분야", "마케팅/금융/IT" 등 세분화 질문 절대 금지
4. "취업", "이직", "부업", "자격증" 같은 답변도 충분히 구체적임

반드시 위 JSON 형식으로만 응답하세요."""

        # LLM 호출
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"사용자 메시지: {user_message}"}
        ])
        
        # JSON 응답 파싱
        try:
            result = json.loads(response.content)
            
            # 상태 업데이트 (자동 확정 제거)
            if "value" in result and result["value"]:
                assessment_state["goal"]["value"] = result["value"]
                assessment_state["goal"]["confidence"] = result.get("confidence", 0.0)
                
                # confirmed는 사용자 명시적 확인 후에만 설정
                print(f"📝 목적 파악됨: {result['value']} (확신도: {result.get('confidence', 0.0):.1f})")
            
            # 대화 기록 저장
            assessment_state["conversation_history"].append({
                "stage": "goal",
                "user_message": user_message,
                "result": result
            })
            
            print(f"✅ 목적 파악 완료: {result}")
            return result
            
        except json.JSONDecodeError:
            print(f"❌ JSON 파싱 실패. 원본 응답: {response.content}")
            return {
                "category": "goal",
                "value": None,
                "confidence": 0.1,
                "confirmed": False,
                "friendly_response": f"{confirmed_topic}를 배우시려는 이유를 알려주세요.",
                "follow_up_question": "구체적으로 어떤 목적으로 활용하고 싶으신가요?",
                "next_action": "need_clarification"
            }
            
    except Exception as e:
        print(f"❌ 목적 파악 중 오류: {str(e)}")
        return {
            "category": "goal",
            "value": None,
            "confidence": 0.0,
            "confirmed": False,
            "friendly_response": "죄송합니다. 다시 말씀해 주시겠어요?",
            "follow_up_question": "어떤 목적으로 공부하고 싶으신가요?",
            "next_action": "need_clarification"
        }


@mcp.tool()
def assess_time(user_message: str) -> dict:
    """
    사용자 메시지에서 학습 시간 계획을 파악합니다.
    
    Args:
        user_message: 사용자가 입력한 메시지
        
    Returns:
        dict: 시간 계획 파악 결과
    """
    print(f"⏰ 시간 파악 요청: {user_message}")
    assessment_state["stage_attempts"]["time"] += 1
    
    # 목적이 확정되지 않았으면 거부
    if not assessment_state["goal"]["confirmed"]:
        return {
            "category": "time",
            "value": None,
            "confidence": 0.0,
            "confirmed": False,
            "friendly_response": "먼저 학습 목적을 확정해야 합니다.",
            "follow_up_question": "어떤 목적으로 공부하고 싶으신가요?",
            "next_action": "need_goal_first"
        }
    
    try:
        confirmed_topic = assessment_state["topic"]["value"]
        confirmed_goal = assessment_state["goal"]["value"]
        
        # 시간 계획 파악 전용 프롬프트 - TIME에만 집중
        system_prompt = f"""당신은 학습 시간 계획만 파악하는 전문가입니다.

🎯 **현재 단계: TIME (언제, 얼마나 공부할 것인가?)**

주제는 '{confirmed_topic}', 목적은 '{confirmed_goal}'로 이미 확정되었습니다.
이제 WHEN/HOW MUCH(언제, 얼마나 공부할 것인가)만 파악하면 됩니다.
예산은 다음 단계에서 다룹니다. 지금은 TIME에만 집중하세요.

## 시간 파악 기준:
- 구체적: "하루 2시간", "주 3회", "주말 4시간", "6개월 완주" (좋음)
- 모호함: "시간 있을 때", "여유되면", "틈틈이", "바쁘면 못해" (더 구체화 필요)
- 확신도: 0.0-1.0 (얼마나 확실한가)
- 확정: confidence >= 0.6이면 confirmed = true

## ✅ 올바른 질문 (TIME 구체화):
- "하루에 대략 얼마나 시간을 낼 수 있으신가요?"
- "평일과 주말 중 언제가 더 여유가 있으신가요?"
- "언제까지 목표를 달성하고 싶으신가요?"

## ❌ 잘못된 질문 (다른 단계):
- "왜 {confirmed_topic}을 배우려고 하시나요?" (GOAL 단계, 이미 확정됨)
- "어떤 분야에 관심이 있으신가요?" (TOPIC 단계, 이미 확정됨)
- "예산은 어떻게 되나요?" (BUDGET 단계)

## 응답 예시:

입력: "하루에 2시간씩 투자할 수 있어요"
출력: {{
  "category": "time",
  "value": "하루 2시간",
  "confidence": 0.9,
  "confirmed": false,
  "friendly_response": "하루 2시간씩 투자하시는군요! 꾸준한 학습이 가능하겠네요.",
  "follow_up_question": "시간을 '하루 2시간'으로 확정하고 다음 단계(학습 예산)로 넘어가시겠습니까? 맞으면 '네' 또는 '확정', 더 구체화하시려면 추가 설명해 주세요.",
  "next_action": "need_user_confirmation"
}}

입력: "시간이 있을 때 해야겠어요"
출력: {{
  "category": "time",
  "value": "불정기적",
  "confidence": 0.3,
  "confirmed": false,
  "friendly_response": "시간 계획을 좀 더 구체적으로 세우시면 효과적일 것 같아요.",
  "follow_up_question": "평일이나 주말 중 언제가 더 여유가 있으신가요? 대략 하루에 1시간이라도 낼 수 있을까요?",
  "next_action": "need_clarification"
}}

## ⚠️ 절대 규칙:
1. confidence >= 0.8이면 **무조건** next_action = "need_user_confirmation"
2. confidence >= 0.8이면 follow_up_question은 **반드시** 확정 질문
3. 더 이상 세분화 질문 금지

반드시 위 JSON 형식으로만 응답하세요."""

        # LLM 호출
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"사용자 메시지: {user_message}"}
        ])
        
        # JSON 응답 파싱
        try:
            result = json.loads(response.content)
            
            # 상태 업데이트 (자동 확정 제거)
            if "value" in result and result["value"]:
                assessment_state["time"]["value"] = result["value"]
                assessment_state["time"]["confidence"] = result.get("confidence", 0.0)
                
                # confirmed는 사용자 명시적 확인 후에만 설정
                print(f"📝 시간 파악됨: {result['value']} (확신도: {result.get('confidence', 0.0):.1f})")
            
            # 대화 기록 저장
            assessment_state["conversation_history"].append({
                "stage": "time",
                "user_message": user_message,
                "result": result
            })
            
            print(f"✅ 시간 파악 완료: {result}")
            return result
            
        except json.JSONDecodeError:
            print(f"❌ JSON 파싱 실패. 원본 응답: {response.content}")
            return {
                "category": "time",
                "value": None,
                "confidence": 0.1,
                "confirmed": False,
                "friendly_response": "학습에 투자할 시간을 계획해보겠습니다.",
                "follow_up_question": "하루에 대략 얼마나 시간을 낼 수 있으신가요?",
                "next_action": "need_clarification"
            }
            
    except Exception as e:
        print(f"❌ 시간 파악 중 오류: {str(e)}")
        return {
            "category": "time",
            "value": None,
            "confidence": 0.0,
            "confirmed": False,
            "friendly_response": "죄송합니다. 다시 말씀해 주시겠어요?",
            "follow_up_question": "학습 시간을 어떻게 계획하고 싶으신가요?",
            "next_action": "need_clarification"
        }


@mcp.tool()
def assess_budget(user_message: str) -> dict:
    """
    사용자 메시지에서 학습 예산을 파악합니다.
    
    Args:
        user_message: 사용자가 입력한 메시지
        
    Returns:
        dict: 예산 파악 결과
    """
    print(f"💰 예산 파악 요청: {user_message}")
    assessment_state["stage_attempts"]["budget"] += 1
    
    # 시간이 확정되지 않았으면 거부
    if not assessment_state["time"]["confirmed"]:
        return {
            "category": "budget",
            "value": None,
            "confidence": 0.0,
            "confirmed": False,
            "friendly_response": "먼저 학습 시간 계획을 확정해야 합니다.",
            "follow_up_question": "학습 시간을 어떻게 계획하고 싶으신가요?",
            "next_action": "need_time_first"
        }
    
    try:
        confirmed_topic = assessment_state["topic"]["value"]
        confirmed_goal = assessment_state["goal"]["value"]
        confirmed_time = assessment_state["time"]["value"]
        
        # 예산 파악 전용 프롬프트 - BUDGET에만 집중
        system_prompt = f"""당신은 학습 예산만 파악하는 전문가입니다.

🎯 **현재 단계: BUDGET (얼마나 투자할 것인가?)**

주제는 '{confirmed_topic}', 목적은 '{confirmed_goal}', 시간은 '{confirmed_time}'로 이미 확정되었습니다.
이제 HOW MUCH(얼마나 투자할 것인가)만 파악하면 모든 평가가 완료됩니다.
지금은 BUDGET에만 집중하세요.

## 예산 파악 기준:
- 구체적: "월 10만원", "총 50만원", "무료만", "월 3만원 이하" (좋음)
- 모호함: "적당히", "너무 비싸지 않게", "여유되는 대로", "돈 없어" (더 구체화 필요)
- 확신도: 0.0-1.0 (얼마나 확실한가)
- 확정: confidence >= 0.6이면 confirmed = true

## ✅ 올바른 질문 (BUDGET 구체화):
- "대략 월 얼마 정도 투자 가능하신가요?"
- "무료 자료를 선호하시나요, 유료도 괜찮으신가요?"
- "학습 전체 예산이 어느 정도 되시나요?"

## ❌ 잘못된 질문 (다른 단계):
- "왜 {confirmed_topic}을 배우려고 하시나요?" (GOAL 단계, 이미 확정됨)
- "언제까지 공부하실 건가요?" (TIME 단계, 이미 확정됨)
- "어떤 분야에 관심 있으신가요?" (TOPIC 단계, 이미 확정됨)

## 응답 예시:

입력: "월 10만원까지는 투자할 수 있어요"
출력: {{
  "category": "budget",
  "value": "월 10만원",
  "confidence": 0.9,
  "confirmed": false,
  "friendly_response": "월 10만원 예산으로 계획하시는군요! 충분한 투자입니다.",
  "follow_up_question": "예산을 '월 10만원'으로 확정하고 평가를 완료하겠습니다. 맞으면 '네' 또는 '확정', 수정하시려면 추가 설명해 주세요.",
  "next_action": "need_user_confirmation"
}}

입력: "무료로만 공부하고 싶어요"
출력: {{
  "category": "budget",
  "value": "무료",
  "confidence": 0.9,
  "confirmed": false,
  "friendly_response": "무료 자료로 학습하시는군요! 훌륭한 무료 자료들이 많이 있습니다.",
  "follow_up_question": "예산을 '무료'로 확정하고 평가를 완료하겠습니다. 맞으면 '네' 또는 '확정', 수정하시려면 추가 설명해 주세요.",
  "next_action": "need_user_confirmation"
}}

입력: "너무 비싸지만 않으면 돼요"
출력: {{
  "category": "budget",
  "value": "예산 제한적",
  "confidence": 0.4,
  "confirmed": false,
  "friendly_response": "예산을 고려해서 효율적인 학습 방법을 찾아보겠습니다.",
  "follow_up_question": "대략 월 얼마 정도까지 투자 가능하신가요? (예: 무료만, 월 3만원, 월 5만원, 월 10만원)",
  "next_action": "need_clarification"
}}

## ⚠️ 절대 규칙:
1. confidence >= 0.8이면 **무조건** next_action = "need_user_confirmation"
2. confidence >= 0.8이면 follow_up_question은 **반드시** 확정 질문
3. 더 이상 세분화 질문 금지

반드시 위 JSON 형식으로만 응답하세요."""

        # LLM 호출
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"사용자 메시지: {user_message}"}
        ])
        
        # JSON 응답 파싱
        try:
            result = json.loads(response.content)
            
            # 상태 업데이트 (자동 확정 제거)
            if "value" in result and result["value"]:
                assessment_state["budget"]["value"] = result["value"]
                assessment_state["budget"]["confidence"] = result.get("confidence", 0.0)
                
                # confirmed는 사용자 명시적 확인 후에만 설정
                print(f"📝 예산 파악됨: {result['value']} (확신도: {result.get('confidence', 0.0):.1f})")
            
            # 대화 기록 저장
            assessment_state["conversation_history"].append({
                "stage": "budget",
                "user_message": user_message,
                "result": result
            })
            
            print(f"✅ 예산 파악 완료: {result}")
            return result
            
        except json.JSONDecodeError:
            print(f"❌ JSON 파싱 실패. 원본 응답: {response.content}")
            return {
                "category": "budget",
                "value": None,
                "confidence": 0.1,
                "confirmed": False,
                "friendly_response": "학습 예산을 계획해보겠습니다.",
                "follow_up_question": "대략 어느 정도 투자 가능하신가요?",
                "next_action": "need_clarification"
            }
            
    except Exception as e:
        print(f"❌ 예산 파악 중 오류: {str(e)}")
        return {
            "category": "budget",
            "value": None,
            "confidence": 0.0,
            "confirmed": False,
            "friendly_response": "죄송합니다. 다시 말씀해 주시겠어요?",
            "follow_up_question": "학습 예산은 어떻게 생각하고 계신가요?",
            "next_action": "need_clarification"
        }


@mcp.tool()
def confirm_and_proceed(category: str, user_response: str) -> dict:
    """
    사용자의 확인 응답을 처리하고 다음 단계로 진행합니다.
    
    Args:
        category: 확인하려는 카테고리 (topic, goal, time, budget)
        user_response: 사용자의 확인 응답
        
    Returns:
        dict: 확인 처리 결과
    """
    print(f"✅ {category} 확인 요청: {user_response}")
    
    # 긍정적 응답 키워드
    positive_keywords = ["네", "예", "확정", "맞아", "맞습니다", "좋아", "좋습니다", "넘어가", "다음"]
    # 부정적 응답 키워드  
    negative_keywords = ["아니", "아니야", "아니요", "틀렸", "다시", "수정", "바꿔"]
    
    user_lower = user_response.lower().strip()
    
    # 긍정적 응답 - 확정하고 다음 단계로
    if any(keyword in user_lower for keyword in positive_keywords):
        assessment_state[category]["confirmed"] = True
        current_value = assessment_state[category]["value"]
        print(f"✅ {category} 확정: {current_value}")
        
        # 다음 단계로 진행
        if can_proceed_to_next_stage():
            advance_to_next_stage()
            
        return {
            "status": "confirmed",
            "category": category,
            "confirmed_value": current_value,
            "message": f"{category}이(가) '{current_value}'로 확정되었습니다.",
            "next_stage": assessment_state["current_stage"]
        }
    
    # 부정적 응답 - 재입력 요청
    elif any(keyword in user_lower for keyword in negative_keywords):
        return {
            "status": "rejected",
            "category": category,
            "message": f"{category} 정보를 다시 입력해 주세요.",
            "action": "retry_current_category"
        }
    
    # 추가 정보 제공 - 더 구체화
    else:
        return {
            "status": "more_info",
            "category": category,
            "additional_info": user_response,
            "message": "추가 정보를 반영해서 다시 분석하겠습니다.",
            "action": "reanalyze_with_more_info"
        }


@mcp.tool()
def get_assessment_status() -> dict:
    """
    현재 평가 진행 상황을 조회합니다.
    
    Returns:
        dict: 현재 상태 정보
    """
    print("📊 상태 조회 요청")
    
    # 진행률 계산
    confirmed_count = sum(1 for item in ["topic", "goal", "time", "budget"] 
                         if assessment_state[item]["confirmed"])
    overall_progress = confirmed_count / 4.0
    
    # 확정된 항목들
    confirmed_items = {}
    pending_items = []
    
    for category in ["topic", "goal", "time", "budget"]:
        if assessment_state[category]["confirmed"]:
            confirmed_items[category] = {
                "value": assessment_state[category]["value"],
                "confidence": assessment_state[category]["confidence"]
            }
        else:
            pending_items.append(category)
    
    return {
        "current_stage": assessment_state["current_stage"],
        "overall_progress": overall_progress,
        "confirmed_items": confirmed_items,
        "pending_items": pending_items,
        "ready_for_next_stage": can_proceed_to_next_stage(),
        "conversation_history": assessment_state["conversation_history"],
        "stage_attempts": assessment_state["stage_attempts"]
    }


@mcp.tool()
def reset_assessment() -> dict:
    """
    평가 상태를 초기화합니다.
    
    Returns:
        dict: 초기화 결과
    """
    print("🔄 상태 초기화 요청")
    
    global assessment_state
    assessment_state = {
        "current_stage": "topic",
        "topic": {"value": None, "confidence": 0.0, "confirmed": False},
        "goal": {"value": None, "confidence": 0.0, "confirmed": False}, 
        "time": {"value": None, "confidence": 0.0, "confirmed": False},
        "budget": {"value": None, "confidence": 0.0, "confirmed": False},
        "conversation_history": [],
        "stage_attempts": {"topic": 0, "goal": 0, "time": 0, "budget": 0}
    }
    
    return {
        "status": "reset_complete",
        "message": "평가 상태가 초기화되었습니다.",
        "current_stage": "topic"
    }


if __name__ == "__main__":
    import sys
    
    print("🚀 Multi-Tool Assessment MCP Server를 시작합니다...")
    print("💡 제공하는 도구:")
    print("   - assess_topic: 학습 주제 파악")
    print("   - assess_goal: 학습 목적 파악")
    print("   - assess_time: 학습 시간 계획 파악")
    print("   - assess_budget: 학습 예산 파악")
    print("   - get_assessment_status: 현재 평가 상태 조회")
    print("   - reset_assessment: 평가 상태 초기화")
    print()
    
    # 실행 모드 선택
    if len(sys.argv) > 1 and sys.argv[1] == "--tcp":
        # TCP 모드 (별도 터미널에서 로그 확인 가능)
        print("🌐 TCP 모드로 서버 시작 (포트 8007)")
        print("📋 이 터미널에서 실시간 로그를 확인할 수 있습니다.")
        print("🔗 클라이언트는 다른 터미널에서 실행해주세요.")
        print("-" * 60)
        try:
            # FastMCP의 TCP 모드 사용법 확인
            mcp.run(host="localhost", port=8007)
        except TypeError:
            # 만약 host/port 파라미터가 지원되지 않으면 기본값 사용
            print("⚠️  TCP 모드가 지원되지 않습니다. HTTP 서버로 시작합니다.")
            mcp.run()
    else:
        # STDIO 모드 (기본)
        print("📡 STDIO 모드로 서버 시작")
        print("💡 HTTP 서버로도 실행 가능합니다:")
        print("   python topic_mcp_server.py --tcp")
        print("-" * 60)
        mcp.run(transport="stdio")