from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from agent import MCPAgent

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
    print(f"=== Chat request received: {request.message} ===")
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    try:
        response = ""
        async for chunk in agent_instance.chat_stream(request.message):
            if chunk.get("type") == "message":
                response += chunk.get("content", "")
        
        return {"response": response}
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)