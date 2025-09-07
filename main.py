from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import json
from contextlib import asynccontextmanager

from agent import MultiMCPAgent
from config import Config
from utils import random_uuid

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

class ChatRequest(BaseModel):
    message: str
    session_id: str = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, response: Response):
    """메인 페이지 - 채팅 UI (세션 생성 및 저장)"""
    # 쿠키에서 세션 ID 확인 또는 새로 생성
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = random_uuid()[:8]
        response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=86400*30)  # 30일
        print(f"🆕 새 사용자 세션 생성: {session_id}")
        
        # 세션 파일 즉시 생성
        from servers.user_assessment import save_session
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
    else:
        print(f"🔄 기존 세션 복원: {session_id}")
    
    # agent_instance에 세션 ID 설정
    if agent_instance:
        agent_instance.current_session_id = session_id
        
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(chat_request: Request):
    """채팅 API - SSE 스트리밍"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    # 요청 바디 파싱
    body = await chat_request.json()
    message = body.get("message", "")
    
    # 쿠키에서 세션 ID 가져오기
    session_id = chat_request.cookies.get("session_id")
    if session_id:
        agent_instance.current_session_id = session_id
        print(f"📋 쿠키에서 세션 ID 가져옴: {session_id}")
    else:
        print("⚠️ 세션 ID가 없습니다. 새로고침 필요")
    
    # 사용자 메시지 로깅
    print(f"\n👤 사용자: {message}")
    print("-" * 50)
    
    async def generate():
        try:
            async for chunk in agent_instance.chat(message):
                print(f"🔄 청크 수신: {chunk}")
                if chunk.get("type") == "message":
                    content = chunk.get("content", "")
                    print(f"📝 메시지 컨텐츠: '{content}' (길이: {len(content)})")
                    if content:
                        # Assessment 정보가 포함된 경우 프로필 정보도 전송
                        response_data = {'content': content}
                        
                        # agent.py에서 전송된 프로필 정보 확인
                        if chunk.get("profile"):
                            response_data['profile'] = chunk.get("profile")
                            print(f"🎯 에이전트에서 전송된 프로필 데이터: {chunk.get('profile')}")
                        
                        # 항상 세션에서 프로필 정보를 확인하고 전송
                        try:
                            # 세션 파일에서 실제 프로필 정보 가져오기
                            from servers.user_assessment import load_session
                            print(f"💡 프로필 체크 시작 - 세션ID: {session_id}")
                            if session_id:
                                session_data = load_session(session_id)
                                print(f"📂 세션 데이터 로드됨: {session_data}")
                                if session_data:
                                    profile_info = {
                                        'topic': session_data.get('topic', ''),
                                        'constraints': session_data.get('constraints', ''),
                                        'goal': session_data.get('goal', '')
                                    }
                                    # 빈 값이 아닌 것만 전송
                                    filtered_profile = {k: v for k, v in profile_info.items() if v}
                                    print(f"🔍 프로필 정보 - 전체: {profile_info}, 필터링됨: {filtered_profile}")
                                    if filtered_profile:
                                        response_data['profile'] = filtered_profile
                                        print(f"✅ 프로필 전송: {filtered_profile}")
                                    else:
                                        print(f"📝 프로필 정보 없음 (모든 값이 빈 문자열)")
                                else:
                                    print(f"❌ 세션 데이터가 None임")
                            else:
                                print(f"❌ 세션 ID가 없음")
                        except Exception as e:
                            print(f"프로필 정보 로드 오류: {e}")
                            import traceback
                            traceback.print_exc()
                        
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
async def clear_chat():
    """대화 기록 초기화"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    agent_instance.clear_conversation()
    return {"message": "대화 기록이 초기화되었습니다."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT, access_log=False)
