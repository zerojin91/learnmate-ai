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
            "servers/mentor_chat.py",          # 멘토 채팅 서버 추가
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
        
    return templates.TemplateResponse("index.html", {"request": request, "session_id": session_id})

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
async def clear_chat():
    """대화 기록 초기화"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    agent_instance.clear_conversation()
    return {"message": "대화 기록이 초기화되었습니다."}

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

class MentorRecommendationRequest(BaseModel):
    message: str
    session_id: str

@app.post("/api/mentor_chat/analyze_and_recommend_personas")
async def analyze_and_recommend_personas(request: MentorRecommendationRequest):
    """멘토 페르소나 분석 및 추천 API"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    try:
        # MCP 도구 호출 - agent.py의 방식 사용
        tools = await agent_instance.client.get_tools()
        recommend_tool = next((tool for tool in tools if tool.name == "analyze_and_recommend_personas"), None)
        
        if not recommend_tool:
            raise Exception("analyze_and_recommend_personas 도구를 찾을 수 없습니다")
        
        tool_args = {
            "message": request.message,
            "session_id": request.session_id
        }
        
        result = await recommend_tool.ainvoke(tool_args)
        
        # 결과가 문자열이면 JSON으로 파싱 시도
        if isinstance(result, str):
            try:
                # JSON 내용 정리 (공백 및 오타 문제 해결)
                clean_result = result.strip()
                
                # 공백이 포함된 키들 정리
                clean_result = clean_result.replace('"recommended_ personas"', '"recommended_personas"')
                clean_result = clean_result.replace('" recommended_personas"', '"recommended_personas"')
                clean_result = clean_result.replace('" id"', '"id"')
                clean_result = clean_result.replace('" name"', '"name"')
                clean_result = clean_result.replace('" reason"', '"reason"')
                clean_result = clean_result.replace('" reasoning"', '"reasoning"')
                clean_result = clean_result.replace('" description"', '"description"')
                clean_result = clean_result.replace('" explanation"', '"explanation"')
                
                # 다양한 키 이름 통합 (reason 계열)
                clean_result = clean_result.replace('"reasoning":', '"reason":')
                clean_result = clean_result.replace('"explanation":', '"reason":')
                clean_result = clean_result.replace('"rationale":', '"reason":')
                clean_result = clean_result.replace('"justification":', '"reason":')
                
                result = json.loads(clean_result)
                
                # 결과 후처리: 각 페르소나의 reason 필드 정규화
                if isinstance(result, dict) and 'recommended_personas' in result:
                    for persona in result['recommended_personas']:
                        # reason 필드가 없으면 대체 필드에서 찾기
                        if 'reason' not in persona:
                            for alt_key in ['reasoning', 'explanation', 'rationale', 'justification', 'description']:
                                if alt_key in persona:
                                    persona['reason'] = persona[alt_key]
                                    break
                            else:
                                # 모든 대체 필드가 없으면 기본값 설정
                                persona['reason'] = f"{persona.get('name', '해당 분야')} 전문가로 추천되었습니다."
                
            except json.JSONDecodeError:
                # JSON 파싱 실패시 기본 구조로 래핑
                result = {"error": "응답 파싱 실패", "raw_result": result}
        
        return result
        
    except Exception as e:
        print(f"❌ 멘토 추천 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"멘토 추천 중 오류가 발생했습니다: {str(e)}"}

class PersonaSelectionRequest(BaseModel):
    persona_id: str
    session_id: str

class ExpertMentoringRequest(BaseModel):
    message: str
    session_id: str

@app.post("/api/mentor_chat/select_persona")
async def api_select_persona(request: PersonaSelectionRequest):
    """페르소나 선택 API"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    try:
        # MCP 도구 호출 - select_persona
        tools = await agent_instance.client.get_tools()
        select_tool = next((tool for tool in tools if tool.name == "select_persona"), None)
        
        if not select_tool:
            raise Exception("select_persona 도구를 찾을 수 없습니다")
        
        tool_args = {
            "persona_id": request.persona_id,
            "session_id": request.session_id
        }
        
        result = await select_tool.ainvoke(tool_args)
        
        # 결과가 문자열이면 JSON으로 파싱 시도
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = {"message": result}
        
        return result
        
    except Exception as e:
        print(f"❌ 페르소나 선택 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"페르소나 선택 중 오류가 발생했습니다: {str(e)}"}

@app.post("/api/mentor_chat/expert_mentoring")
async def expert_mentoring(request: ExpertMentoringRequest):
    """전문가 멘토링 API"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    try:
        # MCP 도구 호출 - expert_mentoring
        tools = await agent_instance.client.get_tools()
        mentoring_tool = next((tool for tool in tools if tool.name == "expert_mentoring"), None)
        
        if not mentoring_tool:
            raise Exception("expert_mentoring 도구를 찾을 수 없습니다")
        
        tool_args = {
            "message": request.message,
            "session_id": request.session_id
        }
        
        result = await mentoring_tool.ainvoke(tool_args)
        
        # 결과가 문자열이면 JSON으로 파싱 시도
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                result = {"response": result}
        
        return result
        
    except Exception as e:
        print(f"❌ 전문가 멘토링 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"전문가 멘토링 중 오류가 발생했습니다: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT, access_log=False)
