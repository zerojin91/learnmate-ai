from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agent import MCPAgent
from config import Config

app = FastAPI(title="MCP Chat Agent")

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 전역 에이전트
agent_instance: MCPAgent = None

class ChatRequest(BaseModel):
    message: str

@app.on_event("startup")
async def startup():
    global agent_instance
    print("Starting agent...")
    agent_instance = MCPAgent("servers/user_assessment.py")
    await agent_instance.initialize()
    print("Agent ready!")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """메인 페이지 - 채팅 UI"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(request: ChatRequest):
    """채팅 API - 에이전트가 대화 기록 관리"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    try:
        response = ""
        async for chunk in agent_instance.chat(request.message):
            if chunk.get("type") == "message":
                response += chunk.get("content", "")
        
        return {"response": response}
        
    except Exception as e:
        return {"error": str(e)}

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
