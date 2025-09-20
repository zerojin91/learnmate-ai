from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import os
import time
from contextlib import asynccontextmanager

from agent import MultiMCPAgent
from config import Config
from utils import random_uuid
from servers.user_assessment import save_session

# 전역 에이전트 (여러 서버 동시 사용)
agent_instance: MultiMCPAgent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global agent_instance
    try:
        print("🚀 Starting multi-MCP agent...")
        
        # 일시적으로 user_assessment 서버만 사용 (테스트용)
        servers = [
            "servers/user_assessment.py",
            "servers/generate_curriculum.py",  # 임시 비활성화
            # "servers/evaluate_user.py"         # 임시 비활성화
        ]
        
        print(f"📋 서버 리스트: {servers}")
        agent_instance = MultiMCPAgent(servers)
        print("🔄 에이전트 인스턴스 생성 완료, 초기화 시작...")
        
        await agent_instance.initialize()
        print("✅ Multi-MCP Agent ready!")
        
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()
    
    yield
    
    # Shutdown
    if agent_instance:
        await agent_instance.cleanup()

app = FastAPI(title="MCP Chat Agent", lifespan=lifespan)

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 정적 파일 설정
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str
    session_id: str = None

def create_initial_session(session_id: str) -> dict:
    """새로운 세션 초기 데이터 생성 및 저장"""
    initial_session_data = {
        "messages": [],
        "topic": "",
        "constraints": "",
        "goal": "",
        "current_agent": "response",
        "session_id": session_id,
        "completed": False
    }
    save_session(session_id, initial_session_data)
    print(f"💾 세션 파일 저장 완료: {session_id}")
    return initial_session_data

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, response: Response):
    """메인 페이지 - 채팅 UI (세션 생성 및 저장)"""
    # 쿠키에서 세션 ID 확인 또는 새로 생성
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = random_uuid()[:8]
        # 쿠키 설정 개선: SameSite와 Secure 옵션 추가
        response.set_cookie(
            key="session_id", 
            value=session_id, 
            httponly=False,  # JavaScript에서 접근 가능하도록 변경
            max_age=86400*30,  # 30일
            samesite="lax",    # CSRF 보호
            path="/"           # 모든 경로에서 접근 가능
        )
        print(f"🆕 새 사용자 세션 생성: {session_id}")

        # 세션 파일 즉시 생성
        create_initial_session(session_id)
    else:
        print(f"🔄 기존 세션 복원: {session_id}")
    
    # agent_instance에 세션 ID 설정
    if agent_instance:
        agent_instance.current_session_id = session_id
        
    import time
    timestamp = str(int(time.time()))
    return templates.TemplateResponse("index.html", {"request": request, "session_id": session_id, "timestamp": timestamp})

@app.post("/chat")
async def chat(chat_request: Request):
    """채팅 API - SSE 스트리밍"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    # 요청 바디 파싱
    body = await chat_request.json()
    message = body.get("message", "")
    
    # 세션 ID 가져오기 - 여러 방법 시도
    session_id = None
    
    # 1. 쿠키에서 확인
    session_id = chat_request.cookies.get("session_id")
    if session_id:
        print(f"📋 쿠키에서 세션 ID 가져옴: {session_id}")
    else:
        # 2. 헤더에서 확인
        session_from_header = chat_request.headers.get("X-Session-ID")
        if session_from_header:
            session_id = session_from_header
            print(f"📋 헤더에서 세션 ID 가져옴: {session_id}")
        else:
            # 3. 바디에서 확인
            session_from_body = body.get("session_id")
            if session_from_body:
                session_id = session_from_body
                print(f"📋 바디에서 세션 ID 가져옴: {session_id}")
    
    if not session_id:
        print("⚠️ 세션 ID를 찾을 수 없습니다.")
        print(f"🍪 쿠키: {dict(chat_request.cookies)}")
        print(f"📄 바디: {body}")
    
    # 사용자 메시지 로깅
    print(f"\n👤 사용자: {message}")
    print("-" * 50)
    
    async def generate():
        # 세션 ID 미리 설정
        if session_id:
            agent_instance.current_session_id = session_id
            print(f"🔗 에이전트에 세션 ID 설정: {session_id}")
        
        try:
            async for chunk in agent_instance.chat(message):
                if chunk.get("type") == "message":
                    content = chunk.get("content", "")
                    if content:
                        response_data = {'content': content}
                        
                        # agent.py에서 전달된 프로필 정보 사용
                        if chunk.get("profile"):
                            response_data['profile'] = chunk.get("profile")
                        
                        yield f"data: {json.dumps(response_data)}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            print(f"\n🤖 응답 완료")
            print("=" * 50)
            
        except Exception as e:
            print(f"❌ 오류: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.post("/clear-chat")
async def clear_chat(request: Request, response: Response):
    """대화 기록 초기화"""
    if not agent_instance:
        return {"error": "Agent not initialized"}

    # 기존 세션 ID 가져오기
    old_session_id = request.cookies.get("session_id")

    # 새로운 세션 ID 생성
    new_session_id = random_uuid()[:8]

    # 기존 세션 파일 삭제 (있다면)
    if old_session_id:
        old_session_file = f"sessions/{old_session_id}.json"
        try:
            if os.path.exists(old_session_file):
                os.remove(old_session_file)
                print(f"🗑️ 기존 세션 파일 삭제: {old_session_file}")
        except Exception as e:
            print(f"⚠️ 세션 파일 삭제 실패: {e}")

    # 에이전트 대화 기록 초기화
    agent_instance.clear_conversation()

    # 새로운 세션 ID를 에이전트에 설정
    agent_instance.current_session_id = new_session_id

    # 새로운 세션 파일 생성
    create_initial_session(new_session_id)

    # 새로운 세션 쿠키 설정
    response.set_cookie(
        key="session_id",
        value=new_session_id,
        max_age=86400,  # 24시간
        httponly=False,  # JavaScript에서 접근 가능하도록 설정
        samesite="lax",
        path="/"  # 모든 경로에서 접근 가능
    )

    print(f"🔄 세션 초기화: {old_session_id} → {new_session_id}")

    return {
        "message": "대화 기록이 초기화되었습니다.",
        "new_session_id": new_session_id
    }

@app.get("/session-debug")
async def session_debug(request: Request):
    """세션 디버그 정보"""
    session_id = request.cookies.get("session_id")
    return {
        "cookies": dict(request.cookies),
        "session_id": session_id,
        "user_agent": request.headers.get("User-Agent", ""),
        "has_session_cookie": "session_id" in request.cookies
    }


@app.get("/api/curriculum/{session_id}")
async def get_curriculum(session_id: str):
    """세션의 생성된 커리큘럼 데이터 조회"""
    if not agent_instance:
        return {"error": "Agent not initialized"}

    try:
        # MCP 도구를 사용하여 커리큘럼 데이터 조회
        tools = await agent_instance.client.get_tools()
        get_curriculum_tool = next((tool for tool in tools if tool.name == "get_curriculum"), None)

        if not get_curriculum_tool:
            return {"error": "get_curriculum 도구를 찾을 수 없습니다"}

        # 커리큘럼 데이터 조회
        result = await get_curriculum_tool.ainvoke({"user_id": session_id})

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return {"error": "커리큘럼 데이터 파싱 실패"}

        return result

    except Exception as e:
        print(f"❌ 커리큘럼 조회 오류: {e}")
        return {"error": f"커리큘럼 조회 중 오류가 발생했습니다: {str(e)}"}

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """세션 데이터 조회"""
    try:
        session_file = f"sessions/{session_id}.json"
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            return session_data
        else:
            return {"error": "세션을 찾을 수 없습니다"}
    except Exception as e:
        print(f"❌ 세션 조회 오류: {e}")
        return {"error": f"세션 조회 중 오류가 발생했습니다: {str(e)}"}

@app.get("/api/progress/{session_id}")
async def get_curriculum_progress(session_id: str):
    """커리큘럼 생성 진행 상황 조회"""
    try:
        progress_file = f"data/progress/{session_id}.json"

        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            return progress_data
        else:
            return {
                "error": "진행 상황 데이터를 찾을 수 없습니다",
                "session_id": session_id,
                "phase_info": {
                    "step": 0,
                    "total": 5,
                    "name": "대기 중",
                    "description": "커리큘럼 생성을 시작하지 않았습니다"
                }
            }
    except Exception as e:
        print(f"❌ 진행 상황 조회 오류: {e}")
        return {
            "error": f"진행 상황 조회 중 오류가 발생했습니다: {str(e)}",
            "session_id": session_id
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT, access_log=False)
