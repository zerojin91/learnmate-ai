"""
LangGraph 기반 커리큘럼 생성 서버 (v2)
기존 generate_curriculum.py를 LangGraph Agent 시스템으로 완전히 리팩토링
"""
from mcp.server.fastmcp import FastMCP
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
import sys
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from enum import Enum

# 프로젝트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# 새로운 Agent 시스템 import
from servers.curriculum_agents.workflow import create_curriculum_workflow
from servers.curriculum_agents.state import ProcessingPhase


# 기존 호환성을 위한 클래스들 유지
class LevelEnum(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class SessionParameters(BaseModel):
    level: LevelEnum = Field(default=LevelEnum.BEGINNER, description="학습 수준")
    duration_weeks: int = Field(default=4, description="학습 기간 (주 단위, 1-24 사이)", ge=1, le=24)
    focus_areas: List[str] = Field(default=[], description="중점 학습 영역")
    weekly_hours: int = Field(default=10, description="주당 학습 가능 시간 (시간 단위, 1-40 사이)", ge=1, le=40)


class ExtractionRequest(BaseModel):
    constraints: str = Field(description="학습 제약 조건")
    goal: str = Field(description="학습 목표")


# 기존 클래스들 (CurriculumDB, SessionLoader) 유지하되 간소화
class CurriculumDB:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.db_file = os.path.join(data_dir, "curriculums.json")
        self.data = self._load_data()

    def _load_data(self):
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"DEBUG: Error loading curriculum DB: {e}", file=sys.stderr)
        return {}

    def _save_data(self):
        try:
            with open(self.db_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"DEBUG: Error saving curriculum DB: {e}", file=sys.stderr)

    def save_curriculum(self, user_id: str, curriculum: Dict):
        if user_id not in self.data:
            self.data[user_id] = []

        curriculum_id = len(self.data[user_id])
        curriculum["id"] = curriculum_id
        self.data[user_id].append(curriculum)
        self._save_data()
        return curriculum_id

    def get_curriculum(self, user_id: str, curriculum_id: int) -> Optional[Dict]:
        user_curriculums = self.data.get(user_id, [])
        if 0 <= curriculum_id < len(user_curriculums):
            return user_curriculums[curriculum_id]
        return None


class SessionLoader:
    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = sessions_dir

    def get_completed_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        try:
            if os.path.exists(self.sessions_dir):
                for filename in os.listdir(self.sessions_dir):
                    if filename.endswith('.json'):
                        session_path = os.path.join(self.sessions_dir, filename)
                        with open(session_path, 'r', encoding='utf-8') as f:
                            session_data = json.load(f)
                            # status=='completed' 또는 completed==True 모두 지원
                            if (session_data.get('status') == 'completed' or
                                session_data.get('completed') == True):
                                sessions.append(session_data)
        except Exception as e:
            print(f"DEBUG: Error loading sessions: {e}", file=sys.stderr)
        return sessions

    def update_session_with_curriculum(self, session_id: str, curriculum: Dict[str, Any]) -> bool:
        try:
            session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
            if os.path.exists(session_file):
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)

                session_data['curriculum'] = {
                    'id': curriculum.get('curriculum_id'),
                    'title': curriculum.get('title'),
                    'generated_at': curriculum.get('generated_at')
                }

                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(session_data, f, ensure_ascii=False, indent=2)
                return True
        except Exception as e:
            print(f"DEBUG: Error updating session with curriculum: {e}", file=sys.stderr)
        return False


# MCP 서버 설정
mcp = FastMCP(
    "CurriculumGenerator",
    instructions="Generate personalized learning curriculums using LangGraph agents",
    host="0.0.0.0",
    port=8006,  # 기존 포트 사용
)

# LLM 및 워크플로우 초기화
def initialize_system():
    try:
        llm = ChatOpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY,
            model=Config.LLM_MODEL,
            temperature=0.7,
            max_tokens=Config.LLM_MAX_TOKENS,
            model_kwargs={"max_completion_tokens": None}
        )

        workflow = create_curriculum_workflow(llm)
        return llm, workflow, True
    except Exception as e:
        print(f"ERROR: System initialization failed: {e}", file=sys.stderr)
        return None, None, False


llm, workflow, system_available = initialize_system()
db = CurriculumDB()
session_loader = SessionLoader()


def extract_duration_from_message(message: str) -> Optional[int]:
    """기존 함수 유지"""
    import re
    if not message:
        return None

    duration_patterns = [
        r'(\d+)\s*주',
        r'(\d+)\s*week',
        r'(\d+)\s*달',
        r'(\d+)\s*month'
    ]

    for pattern in duration_patterns:
        match = re.search(pattern, message.lower())
        if match:
            duration = int(match.group(1))
            if 'month' in pattern or '달' in pattern:
                duration *= 4

            if 1 <= duration <= 24:
                return duration
    return None


@mcp.tool()
async def list_session_topics() -> Dict[str, Any]:
    """List all completed sessions available for curriculum generation"""
    sessions = session_loader.get_completed_sessions()
    return {
        "message": f"Found {len(sessions)} completed sessions",
        "sessions": [
            {
                "session_id": s["session_id"],
                "topic": s["topic"],
                "goal": s["goal"],
                "constraints": s["constraints"]
            }
            for s in sessions
        ],
        "all_sessions": sessions
    }


@mcp.tool()
async def generate_curriculum_from_session(session_id: str, user_message: str = "") -> Dict[str, Any]:
    """Generate curriculum from a specific session using LangGraph agents"""

    if not system_available:
        return {"error": "LangGraph system not available"}

    sessions = session_loader.get_completed_sessions()
    session_data = None

    for session in sessions:
        if session["session_id"] == session_id:
            session_data = session
            break

    if not session_data:
        return {"error": f"Session {session_id} not found"}

    print(f"DEBUG: Starting LangGraph curriculum generation for {session_id}", file=sys.stderr)

    try:
        # LangGraph 워크플로우로 커리큘럼 생성
        curriculum = await workflow.generate_curriculum(
            session_id=session_id,
            topic=session_data["topic"],
            constraints=session_data["constraints"],
            goal=session_data["goal"],
            user_message=user_message
        )

        print(f"DEBUG: LangGraph workflow completed successfully", file=sys.stderr)

        # 데이터베이스 저장
        curriculum_id = db.save_curriculum(session_id, curriculum)
        curriculum["curriculum_id"] = curriculum_id

        # 세션 파일 업데이트
        session_loader.update_session_with_curriculum(session_id, curriculum)

        return curriculum

    except Exception as e:
        print(f"ERROR: LangGraph curriculum generation failed: {e}", file=sys.stderr)
        return {"error": f"Curriculum generation failed: {str(e)}"}


@mcp.tool()
async def generate_curriculums_from_all_sessions() -> Dict[str, Any]:
    """Generate curriculums for all completed sessions using LangGraph"""

    if not system_available:
        return {"error": "LangGraph system not available"}

    sessions = session_loader.get_completed_sessions()

    if not sessions:
        return {
            "message": "No completed sessions found",
            "sessions_processed": 0,
            "curriculums_generated": 0
        }

    successful = []
    failed = []

    for session in sessions:
        session_id = session["session_id"]

        try:
            # 이미 존재하는지 확인
            existing = db.get_curriculum(session_id, 0)
            if existing:
                continue

            result = await generate_curriculum_from_session(session_id)

            if "error" in result:
                failed.append({"session_id": session_id, "error": result["error"]})
            else:
                successful.append(session_id)

        except Exception as e:
            failed.append({"session_id": session_id, "error": str(e)})

    return {
        "message": f"Processed {len(sessions)} sessions",
        "sessions_processed": len(sessions),
        "curriculums_generated": len(successful),
        "successful": successful,
        "failed": failed
    }


@mcp.tool()
async def get_curriculum(user_id: str, curriculum_id: int = 0) -> Dict[str, Any]:
    """Get a specific curriculum"""
    curriculum = db.get_curriculum(user_id, curriculum_id)
    if curriculum:
        return curriculum
    else:
        return {"error": f"Curriculum not found for user {user_id}, id {curriculum_id}"}


@mcp.tool()
async def search_learning_resources(topic: str, num_results: int = 10) -> Dict[str, Any]:
    """Search for learning resources on a topic (legacy compatibility)"""
    try:
        # 리소스 수집 에이전트 직접 호출
        from servers.curriculum_agents.resource_collector import ResourceCollectorAgent
        resource_agent = ResourceCollectorAgent(llm)

        resources = await resource_agent._search_basic_resources(topic, num_results)

        return {
            "topic": topic,
            "resources": resources,
            "count": len(resources)
        }
    except Exception as e:
        return {"error": f"Resource search failed: {str(e)}"}


@mcp.tool()
async def get_curriculum_progress(session_id: str) -> Dict[str, Any]:
    """Get real-time progress of curriculum generation"""
    try:
        progress_file = f"data/progress/{session_id}.json"

        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            return progress_data
        else:
            return {"error": "No progress data found", "session_id": session_id}

    except Exception as e:
        return {"error": f"Failed to get progress: {str(e)}"}


if __name__ == "__main__":
    print("🚀 Starting LangGraph-based Curriculum Generator")
    print(f"🤖 System available: {system_available}")
    if system_available:
        print("🎯 All LangGraph agents loaded successfully")
    else:
        print("❌ System initialization failed - running in fallback mode")

    mcp.run()