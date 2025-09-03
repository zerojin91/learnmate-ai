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
    model="midm-2.0-base-q8",
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
                "get_system_info"
            ],
            "status": "running",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": f"시스템 정보 조회 오류: {str(e)}"}


if __name__ == "__main__":
    print("🚀 User Assessment MCP Server를 시작합니다...")
    print("💡 사용 가능한 도구들:")
    print("   - start_assessment: 평가 시작")
    print("   - get_system_info: 시스템 정보 확인")
    print()
    
    mcp.run(transport="stdio")