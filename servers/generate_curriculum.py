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

    def get_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        try:
            # Search for the file in the directory and subdirectories
            for root, _, files in os.walk(self.sessions_dir):
                for filename in files:
                    if filename == f"{session_id}.json":
                        session_path = os.path.join(root, filename)
                        with open(session_path, 'r', encoding='utf-8') as f:
                            return json.load(f)
        except Exception as e:
            print(f"DEBUG: Error loading session {session_id}: {e}", file=sys.stderr)
        return None

    def get_completed_sessions(self) -> List[Dict[str, Any]]:
        sessions = []
        try:
            if os.path.exists(self.sessions_dir):
                for root, _, files in os.walk(self.sessions_dir):
                    for filename in files:
                        if filename.endswith('.json'):
                            session_path = os.path.join(root, filename)
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

    session_data = session_loader.get_session_by_id(session_id)

    if not session_data:
        return {"error": f"Session {session_id} not found"}

    print(f"DEBUG: Starting LangGraph curriculum generation for {session_id}", file=sys.stderr)
    print(f"DEBUG: Session data - topic: {session_data.get('topic')}, constraints: {session_data.get('constraints')}, goal: {session_data.get('goal')}", file=sys.stderr)

    try:
        # LangGraph 워크플로우로 커리큘럼 생성
        curriculum = await workflow.generate_curriculum(
            session_id=session_id,
            topic=session_data["topic"],
            constraints=session_data["constraints"],
            goal=session_data["goal"],
            user_message=user_message
        )

        print(f"DEBUG: LangGraph workflow completed", file=sys.stderr)
        print(f"DEBUG: Generated curriculum type: {type(curriculum)}", file=sys.stderr)

        # fallback 커리큘럼인지 확인
        if curriculum.get("fallback"):
            print(f"WARNING: Fallback curriculum was generated", file=sys.stderr)
        else:
            print(f"SUCCESS: Complete curriculum generated with graph_curriculum: {'graph_curriculum' in curriculum}", file=sys.stderr)

        # 강의자료 자동 생성 (graph_curriculum이 있는 경우에만)
        lecture_generation_success = True
        if "graph_curriculum" in curriculum and "modules" in curriculum and not curriculum.get("fallback"):
            print(f"DEBUG: Generating lecture notes for {session_id}", file=sys.stderr)
            try:
                # 병렬로 모든 모듈의 강의자료 생성
                lecture_notes = await _generate_lecture_notes_concurrent(curriculum["modules"], curriculum["graph_curriculum"], llm)
                
                # 생성된 강의자료 검증
                successful_notes = 0
                for i, module in enumerate(curriculum["modules"]):
                    if i < len(lecture_notes) and lecture_notes[i] and not ("오류가 발생했습니다" in lecture_notes[i]):
                        # 유효한 강의자료인지 검증 (최소 길이 확인)
                        if len(lecture_notes[i].strip()) > 50:
                            module["lecture_note"] = lecture_notes[i]
                            successful_notes += 1
                        else:
                            print(f"WARNING: Generated lecture note too short for week {module.get('week', i+1)}", file=sys.stderr)
                            lecture_generation_success = False
                    else:
                        print(f"WARNING: Failed to generate lecture note for week {module.get('week', i+1)}", file=sys.stderr)
                        lecture_generation_success = False
                
                if successful_notes == len(curriculum["modules"]):
                    print(f"SUCCESS: All {successful_notes} lecture notes generated successfully", file=sys.stderr)
                    curriculum["lecture_notes_complete"] = True
                else:
                    print(f"WARNING: Only {successful_notes}/{len(curriculum['modules'])} lecture notes generated", file=sys.stderr)
                    curriculum["lecture_notes_complete"] = False
                    lecture_generation_success = False
                    
            except Exception as e:
                print(f"ERROR: Lecture note generation failed: {e}", file=sys.stderr)
                import traceback
                print(f"ERROR: Lecture note stacktrace: {traceback.format_exc()}", file=sys.stderr)
                curriculum["lecture_notes_complete"] = False
                lecture_generation_success = False

        # 데이터베이스 저장
        curriculum_id = db.save_curriculum(session_id, curriculum)
        curriculum["curriculum_id"] = curriculum_id

        # 세션 파일 업데이트
        session_loader.update_session_with_curriculum(session_id, curriculum)

        # 강의자료 생성 상태를 포함한 결과 반환
        result = curriculum.copy()
        result["generation_status"] = {
            "curriculum_complete": True,
            "lecture_notes_complete": curriculum.get("lecture_notes_complete", False),
            "overall_success": lecture_generation_success and not curriculum.get("fallback", False)
        }

        return result

    except Exception as e:
        print(f"ERROR: LangGraph curriculum generation failed: {e}", file=sys.stderr)
        import traceback
        print(f"ERROR: Stacktrace: {traceback.format_exc()}", file=sys.stderr)
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


@mcp.tool()
async def generate_lecture_notes(user_id: str, curriculum_id: int = 0, week: Optional[int] = None) -> Dict[str, Any]:
    """Generate lecture notes for a specific week using graph_curriculum content"""
    
    if not system_available:
        return {"error": "LangGraph system not available"}

    # 커리큘럼 가져오기
    curriculum = db.get_curriculum(user_id, curriculum_id)
    if not curriculum:
        return {"error": f"Curriculum not found for user {user_id}, id {curriculum_id}"}

    # graph_curriculum이 없으면 에러
    if "graph_curriculum" not in curriculum:
        return {"error": "Graph curriculum not found. Please generate curriculum with LangGraph first."}

    graph_curriculum = curriculum["graph_curriculum"]
    modules = curriculum.get("modules", [])

    try:
        # 특정 주차가 지정된 경우
        if week is not None:
            target_module = next((m for m in modules if m["week"] == week), None)
            if not target_module:
                return {"error": f"Week {week} not found in curriculum"}
            
            lecture_note = await _generate_single_lecture_note(target_module, graph_curriculum, llm)
            
            # 커리큘럼에 강의자료 추가
            for module in curriculum["modules"]:
                if module["week"] == week:
                    module["lecture_note"] = lecture_note
                    break
            
            # 데이터베이스 업데이트
            db.save_curriculum(user_id, curriculum)
            
            return {
                "message": f"Generated lecture note for week {week}",
                "week": week,
                "lecture_note": lecture_note
            }
        
        # 모든 주차에 대해 강의자료 생성
        else:
            generated_count = 0
            
            for module in curriculum["modules"]:
                # 이미 강의자료가 있으면 스킵
                if "lecture_note" in module:
                    continue
                
                lecture_note = await _generate_single_lecture_note(module, graph_curriculum, llm)
                module["lecture_note"] = lecture_note
                generated_count += 1
            
            # 데이터베이스 업데이트
            db.save_curriculum(user_id, curriculum)
            
            return {
                "message": f"Generated lecture notes for {generated_count} weeks",
                "total_weeks": len(modules),
                "generated_count": generated_count
            }

    except Exception as e:
        print(f"ERROR: Lecture note generation failed: {e}", file=sys.stderr)
        import traceback
        print(f"ERROR: Stacktrace: {traceback.format_exc()}", file=sys.stderr)
        return {"error": f"Lecture note generation failed: {str(e)}"}


def _extract_relevant_content(graph_curriculum: Dict) -> Dict[str, List[Dict]]:
    """Extract and index content from graph_curriculum for faster lookup"""
    content_index = {}
    
    for _, step_data in graph_curriculum.items():
        step_title = step_data.get("title", "").lower()
        skills = step_data.get("skills", {})
        
        for skill_name, skill_data in skills.items():
            documents = skill_data.get("documents", {})
            for _, doc_data in documents.items():
                content = doc_data.get("content", "")
                if content:
                    # 키워드로 인덱싱
                    keywords = [step_title, skill_name.lower()] + step_title.split()
                    for keyword in keywords:
                        if keyword not in content_index:
                            content_index[keyword] = []
                        content_index[keyword].append({
                            "source": f"{step_data.get('title', '')} - {skill_name}",
                            "content": content[:1500]  # 길이 제한으로 프롬프트 최적화
                        })
    
    return content_index


async def _generate_lecture_notes_concurrent(modules: List[Dict], graph_curriculum: Dict, llm) -> List[str]:
    """Generate lecture notes for multiple modules concurrently"""
    import asyncio
    
    # 콘텐츠 인덱싱 (한 번만 수행)
    content_index = _extract_relevant_content(graph_curriculum)
    
    # 병렬로 강의자료 생성
    tasks = [
        _generate_single_lecture_note_optimized(module, content_index, llm)
        for module in modules
    ]
    
    return await asyncio.gather(*tasks)


async def _generate_single_lecture_note_optimized(module: Dict, content_index: Dict, llm) -> str:
    """Generate lecture note for a single module using pre-indexed content"""
    
    week = module["week"]
    title = module["title"]
    description = module.get("description", "")
    objectives = module.get("objectives", [])
    key_concepts = module.get("key_concepts", [])
    
    # 관련 콘텐츠를 인덱스에서 빠르게 검색
    relevant_contents = []
    for concept in key_concepts:
        concept_lower = concept.lower()
        for keyword in [concept_lower] + concept_lower.split():
            if keyword in content_index:
                relevant_contents.extend(content_index[keyword][:2])  # 각 키워드당 최대 2개
                
    # 중복 제거 및 제한
    unique_contents = []
    seen_sources = set()
    for content in relevant_contents[:4]:  # 최대 4개로 제한
        if content["source"] not in seen_sources:
            unique_contents.append(content)
            seen_sources.add(content["source"])
    
    # 간소화된 프롬프트로 성능 향상
    reference_text = "\n\n".join([f"**{content['source']}**\n{content['content'][:800]}" 
                                  for content in unique_contents[:2]])
    
    prompt = f"""주차: {week}주차 - {title}

학습목표: {', '.join(objectives[:2])}
핵심개념: {', '.join(key_concepts[:3])}

참고자료:
{reference_text}

다음 구조로 간단명료한 강의자료를 작성하세요:

# {week}주차: {title}

## 학습 개요
{description[:100]}...의 목적과 중요성

## 핵심 개념
- 개념 1: 설명
- 개념 2: 설명

## 실습 예제
구체적이고 실용적인 예제 1개

## 정리
핵심 내용 요약 (3줄 이내)

초보자도 이해하기 쉽게 친근한 톤으로 작성하세요."""

    try:
        response = await llm.ainvoke(prompt)
        return response.content
    except Exception as e:
        return f"# {week}주차: {title}\n\n강의자료 생성 중 오류가 발생했습니다: {str(e)}"


async def _generate_single_lecture_note(module: Dict, graph_curriculum: Dict, llm) -> str:
    """Generate lecture note for a single module using graph_curriculum content (legacy)"""
    content_index = _extract_relevant_content(graph_curriculum)
    return await _generate_single_lecture_note_optimized(module, content_index, llm)


if __name__ == "__main__":
    print("🚀 Starting LangGraph-based Curriculum Generator")
    print(f"🤖 System available: {system_available}")
    if system_available:
        print("🎯 All LangGraph agents loaded successfully")
    else:
        print("❌ System initialization failed - running in fallback mode")

    mcp.run()