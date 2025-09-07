from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import json
from contextlib import asynccontextmanager

from agent import MultiMCPAgent
from config import Config

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

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """메인 페이지 - 채팅 UI"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(request: ChatRequest):
    """채팅 API - SSE 스트리밍"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    # 사용자 메시지 로깅
    print(f"\n👤 사용자: {request.message}")
    print("-" * 50)
    
    async def generate():
        try:
            async for chunk in agent_instance.chat(request.message):
                if chunk.get("type") == "message":
                    content = chunk.get("content", "")
                    if content:
                        yield f"data: {json.dumps({'content': content})}\n\n"
            
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
