"""
User Assessment MCP Server

LangGraph 기반 5단계 학습 평가 시스템을 MCP 도구로 제공
"""

from mcp.server.fastmcp import FastMCP
from langchain_openai import ChatOpenAI
from datetime import datetime
import json
import asyncio

# Assessment Engine 모듈들 임포트
from assessment_engine.session_manager import SessionManager
from assessment_engine.assessors.topic_assessor import TopicAssessor
from assessment_engine.assessors.goal_assessor import GoalAssessor
from assessment_engine.assessors.time_assessor import TimeAssessor
from assessment_engine.assessors.budget_assessor import BudgetAssessor
from assessment_engine.assessors.level_assessor import LevelAssessor
from assessment_engine.database.kmooc_db import KMOOCDatabase
from assessment_engine.models.state import UserAssessment

# FastMCP 서버 생성
mcp = FastMCP(
    "UserAssessment",  # MCP 서버 이름
    instructions="AI 기반 개인화 학습 평가 시스템입니다. 사용자의 주제, 목표, 시간, 예산, 수준을 순차적으로 평가하여 맞춤형 KMOOC 강의를 추천합니다.",
    host="0.0.0.0",
    port=8006
)

# 전역 인스턴스들 초기화
llm = ChatOpenAI(
    base_url="http://localhost:11434/v1", 
    api_key="ollama",
    model="midm-2.0:base",
    temperature=0.0,
    max_tokens=8192
)

session_manager = SessionManager()
topic_assessor = TopicAssessor(llm)
goal_assessor = GoalAssessor(llm)
time_assessor = TimeAssessor(llm)
budget_assessor = BudgetAssessor(llm)
level_assessor = LevelAssessor(llm)
kmooc_db = KMOOCDatabase()

print(f"🚀 User Assessment MCP Server 초기화 완료")
print(f"📊 KMOOC 강의 수: {kmooc_db.get_total_courses_count()}개")
print(f"🔧 사용 중인 LLM: {llm.model_name}")


@mcp.tool()
async def start_assessment(user_input: str = "학습 평가를 시작합니다") -> dict:
    """
    새로운 학습 평가 세션을 시작합니다.
    
    Args:
        user_input: 사용자의 초기 입력 (선택적)
        
    Returns:
        dict: 세션 정보 및 첫 질문
    """
    try:
        # 새 세션 생성
        session_id = session_manager.create_session()
        session_manager.add_conversation(session_id, user_input)
        
        # 프로세스 설명 생성
        process_explanation = """안녕하세요! 🎯 맞춤형 학습 추천을 위해 간단한 평가를 진행하겠습니다.

📋 **진행 순서**:
1️⃣ **주제 파악**: 먼저 어떤 분야를 공부하고 싶으신지 알아보겠습니다
2️⃣ **목표 파악**: 학습 목적과 목표를 확인하겠습니다
3️⃣ **시간 파악**: 학습에 투자할 수 있는 시간을 파악하겠습니다
4️⃣ **예산 파악**: 학습 예산 범위를 알아보겠습니다
5️⃣ **수준 측정**: 현재 수준을 측정하겠습니다
6️⃣ **강의 추천**: 마지막으로 맞춤형 KMOOC 강의를 추천해드리겠습니다

편안하게 대화하듯 답변해주시면 됩니다! 😊

그럼 시작해볼까요? 어떤 주제를 공부하고 싶으신가요?"""

        return {
            "session_id": session_id,
            "stage": "topic",
            "message": process_explanation,
            "next_action": "assess_topic",
            "progress": session_manager.get_completion_progress(session_id)
        }
        
    except Exception as e:
        return {
            "error": f"세션 시작 실패: {str(e)}",
            "session_id": None
        }


@mcp.tool()
async def get_system_info() -> dict:
    """
    시스템 정보와 통계를 확인합니다.
    
    Returns:
        dict: 시스템 정보
    """
    try:
        return {
            "server_name": "User Assessment MCP Server",
            "version": "1.0.0",
            "llm_model": llm.model_name,
            "kmooc_courses_count": kmooc_db.get_total_courses_count(),
            "active_sessions_count": session_manager.get_active_sessions_count(),
            "assessment_stages": ["topic", "goal", "time", "budget", "level"],
            "available_tools": [
                "start_assessment",
                "assess_user", 
                "get_system_info"
            ],
            "status": "running",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": f"시스템 정보 조회 오류: {str(e)}"}


@mcp.tool()
async def assess_user(user_input: str, session_id: str = None) -> dict:
    """
    사용자 입력을 받아 현재 상태에 따라 적절한 평가를 진행합니다.
    
    Args:
        user_input: 사용자 입력
        session_id: 세션 ID (선택적)
        
    Returns:
        dict: 평가 결과 및 다음 단계 안내
    """
    print(f"사용자 평가를 시작합니다!!")
    try:
        # 세션 ID가 없으면 새로 생성
        if not session_id:
            session_id = session_manager.create_session()
            session_manager.add_conversation(session_id, user_input)
            
            return {
                "session_id": session_id,
                "message": "새 세션이 시작되었습니다. 먼저 start_assessment 도구를 사용해서 평가를 시작해주세요.",
                "next_action": "start_assessment"
            }
        
        # 세션 확인
        session = session_manager.get_session(session_id)
        if not session:
            return {
                "error": f"세션 {session_id}을 찾을 수 없습니다. 새로 시작해주세요.",
                "next_action": "start_assessment"
            }
        
        # 대화 기록 추가
        session_manager.add_conversation(session_id, user_input)
        
        # 현재 단계 확인
        current_stage = session_manager.get_current_stage(session_id)
        conversation_history = [msg["message"] for msg in session_manager.get_conversation_history(session_id, 5)]
        
        result = {}
        
        if current_stage == "topic":
            # 주제 평가
            topic_result = topic_assessor.identify_topic(user_input)
            
            if topic_result.get("needs_clarification", False) or topic_result.get("confidence", 0) < 0.6:
                # 명료화 필요
                clarification_question = topic_assessor.generate_clarification_question(topic_result, user_input)
                result = {
                    "session_id": session_id,
                    "stage": "topic",
                    "status": "clarification_needed",
                    "message": clarification_question,
                    "assessment_result": topic_result,
                    "next_action": "continue_topic_assessment"
                }
            else:
                # 주제 확인
                confirmation_question = topic_assessor.generate_topic_confirmation_question(topic_result, user_input)
                session_manager.update_assessment_data(session_id, "topic", topic_result)
                result = {
                    "session_id": session_id,
                    "stage": "topic",
                    "status": "confirmation_needed", 
                    "message": confirmation_question,
                    "assessment_result": topic_result,
                    "next_action": "confirm_topic_or_proceed"
                }
        
        elif current_stage == "goal":
            # 목표 평가
            goal_result = goal_assessor.identify_goal(user_input, conversation_history)
            
            if goal_result.get("confidence", 0) < 0.6:
                # 목표 명료화 필요
                result = {
                    "session_id": session_id,
                    "stage": "goal",
                    "status": "clarification_needed",
                    "message": "학습 목표를 좀 더 구체적으로 말씀해주세요. 예를 들어, 취업, 스킬 향상, 취미, 자격증 취득 등이 있습니다.",
                    "assessment_result": goal_result,
                    "next_action": "continue_goal_assessment"
                }
            else:
                confirmation_question = goal_assessor.generate_goal_confirmation_question(goal_result, user_input)
                session_manager.update_assessment_data(session_id, "goal", goal_result)
                result = {
                    "session_id": session_id,
                    "stage": "goal", 
                    "status": "confirmation_needed",
                    "message": confirmation_question,
                    "assessment_result": goal_result,
                    "next_action": "confirm_goal_or_proceed"
                }
        
        elif current_stage == "time":
            # 시간 평가
            time_result = time_assessor.identify_time_availability(user_input, conversation_history)
            
            if time_result.get("confidence", 0) < 0.6:
                result = {
                    "session_id": session_id,
                    "stage": "time",
                    "status": "clarification_needed",
                    "message": "학습에 투자할 수 있는 시간을 좀 더 구체적으로 알려주세요. 예를 들어, 평일 저녁 2시간, 주말 4시간 등으로 말씀해주시면 됩니다.",
                    "assessment_result": time_result,
                    "next_action": "continue_time_assessment"
                }
            else:
                confirmation_question = time_assessor.generate_time_confirmation_question(time_result, user_input)
                session_manager.update_assessment_data(session_id, "time", time_result)
                result = {
                    "session_id": session_id,
                    "stage": "time",
                    "status": "confirmation_needed", 
                    "message": confirmation_question,
                    "assessment_result": time_result,
                    "next_action": "confirm_time_or_proceed"
                }
        
        elif current_stage == "budget":
            # 예산 평가
            budget_result = budget_assessor.identify_budget_range(user_input, conversation_history)
            
            if budget_result.get("confidence", 0) < 0.6:
                result = {
                    "session_id": session_id,
                    "stage": "budget",
                    "status": "clarification_needed",
                    "message": "학습 예산 범위를 좀 더 구체적으로 알려주세요. 무료만 원하시는지, 월 얼마 정도까지 투자 가능하신지 말씀해주세요.",
                    "assessment_result": budget_result,
                    "next_action": "continue_budget_assessment"
                }
            else:
                confirmation_question = budget_assessor.generate_budget_confirmation_question(budget_result, user_input)
                session_manager.update_assessment_data(session_id, "budget", budget_result)
                result = {
                    "session_id": session_id,
                    "stage": "budget",
                    "status": "confirmation_needed",
                    "message": confirmation_question,
                    "assessment_result": budget_result,
                    "next_action": "confirm_budget_or_proceed"
                }
        
        elif current_stage == "level":
            # 수준 측정
            assessment_data = session_manager.get_assessment_data(session_id)
            topic = assessment_data.get("topic", {}).get("topic", "학습 주제")
            
            level_result = level_assessor.identify_level(topic, user_input, conversation_history)
            
            if level_result.get("confidence", 0) < 0.6:
                result = {
                    "session_id": session_id,
                    "stage": "level",
                    "status": "clarification_needed",
                    "message": f"{topic}에 대한 현재 수준을 좀 더 구체적으로 알려주세요. 완전 처음인지, 기본적인 것은 알고 있는지, 어느 정도 경험이 있는지 말씀해주세요.",
                    "assessment_result": level_result,
                    "next_action": "continue_level_assessment"
                }
            else:
                confirmation_question = level_assessor.generate_level_confirmation_question(level_result, topic, user_input)
                session_manager.update_assessment_data(session_id, "level", level_result)
                session_manager.update_stage(session_id, "completed")
                
                result = {
                    "session_id": session_id,
                    "stage": "level",
                    "status": "assessment_completed",
                    "message": f"{confirmation_question}\n\n🎉 평가가 완료되었습니다! 모든 정보가 수집되었습니다.",
                    "assessment_result": level_result,
                    "next_action": "assessment_complete",
                    "final_assessment": session_manager.get_assessment_data(session_id)
                }
        
        else:
            result = {
                "session_id": session_id,
                "stage": current_stage,
                "message": "평가가 이미 완료되었습니다.",
                "next_action": "assessment_complete",
                "assessment_data": session_manager.get_assessment_data(session_id)
            }
        
        # 진행률 추가
        result["progress"] = session_manager.get_completion_progress(session_id)
        
        return result
        
    except Exception as e:
        return {
            "error": f"평가 처리 중 오류 발생: {str(e)}",
            "session_id": session_id,
            "next_action": "retry_or_restart"
        }


@mcp.tool()
async def confirm_and_proceed(session_id: str, confirmed: bool = True) -> dict:
    """
    현재 단계 확인 후 다음 단계로 진행합니다.
    
    Args:
        session_id: 세션 ID
        confirmed: 확인 여부 (True면 다음 단계로, False면 재평가)
        
    Returns:
        dict: 다음 단계 정보
    """
    try:
        session = session_manager.get_session(session_id)
        if not session:
            return {"error": "세션을 찾을 수 없습니다."}
        
        current_stage = session_manager.get_current_stage(session_id)
        
        if confirmed:
            # 다음 단계로 이동
            next_stage = session_manager.next_stage(session_id)
            
            if next_stage == "goal":
                message = "좋습니다! 이제 학습 목표에 대해 알아보겠습니다. 어떤 목적으로 공부하고 싶으신가요? (예: 취업, 업무 스킬 향상, 취미, 자격증 취득 등)"
            elif next_stage == "time":
                message = "목표를 확인했습니다. 이제 학습 시간에 대해 알아보겠습니다. 일주일에 몇 시간 정도 학습할 수 있으신가요?"
            elif next_stage == "budget":
                message = "시간 계획을 확인했습니다. 학습 예산은 어떻게 생각하고 계시나요? 무료 강의만 원하시는지, 유료도 괜찮으신지 알려주세요."
            elif next_stage == "level":
                assessment_data = session_manager.get_assessment_data(session_id)
                topic = assessment_data.get("topic", {}).get("topic", "해당 주제")
                message = f"예산을 확인했습니다. 마지막으로 {topic}에 대한 현재 수준을 알려주세요. 완전 처음이신가요, 아니면 어느 정도 아시나요?"
            elif next_stage == "completed":
                message = "🎉 모든 평가가 완료되었습니다!"
            else:
                message = f"다음 단계({next_stage})로 이동했습니다."
            
            return {
                "session_id": session_id,
                "stage": next_stage,
                "message": message,
                "progress": session_manager.get_completion_progress(session_id)
            }
        else:
            # 현재 단계 재진행
            stage_questions = {
                "topic": "어떤 주제를 공부하고 싶으신지 다시 말씀해주세요.",
                "goal": "학습 목표를 다시 말씀해주세요.", 
                "time": "학습 시간 계획을 다시 알려주세요.",
                "budget": "학습 예산에 대해 다시 말씀해주세요.",
                "level": "현재 수준에 대해 다시 설명해주세요."
            }
            
            return {
                "session_id": session_id,
                "stage": current_stage,
                "message": stage_questions.get(current_stage, "다시 말씀해주세요."),
                "progress": session_manager.get_completion_progress(session_id)
            }
            
    except Exception as e:
        return {"error": f"확인 처리 중 오류: {str(e)}"}


if __name__ == "__main__":
    print("🚀 User Assessment MCP Server를 시작합니다...")
    print("💡 사용 가능한 도구들:")
    print("   - start_assessment: 평가 시작")
    print("   - assess_user: 사용자 평가 진행")
    print("   - confirm_and_proceed: 단계 확인 및 진행")
    print("   - get_system_info: 시스템 정보 확인")
    print()
    
    mcp.run(transport="stdio")