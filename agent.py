"""
MCP Agent 모듈 - agent.ipynb의 로직을 모듈화
"""

from typing import AsyncGenerator, Optional, List, Dict
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from utils import astream_graph, trim_conversation_history, log_token_usage
from config import Config


class MCPAgent:
    """MCP 에이전트 클래스 - 대화 기록 관리 포함"""
    
    def __init__(self, server_script: str = "servers/user_assessment.py"):
        self.server_script = server_script
        self.agent = None
        self.session = None
        self.stdio_client = None
        self.read = None
        self.write = None
        self.initialized = False
        
        # 대화 기록 관리
        self.conversation_history: List[Dict[str, str]] = []
        
        # LLM 설정 - Config에서 가져오기
        self.llm = ChatOpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY,
            model=Config.LLM_MODEL,
            temperature=Config.LLM_TEMPERATURE,
            max_tokens=Config.LLM_MAX_TOKENS,
        )
    
    async def initialize(self):
        """MCP 에이전트 초기화 - 원래 코드와 동일한 방식"""
        if self.initialized:
            return
            
        try:
            # StdIO 서버 파라미터 설정 (원래 코드와 동일)
            server_params = StdioServerParameters(
                command="python",
                args=[self.server_script],
            )
            
            # StdIO 클라이언트를 사용하여 서버와 통신
            self.stdio_client = stdio_client(server_params)
            self.read, self.write = await self.stdio_client.__aenter__()
            
            # 클라이언트 세션 생성
            self.session = ClientSession(self.read, self.write)
            await self.session.__aenter__()
            
            # 연결 초기화
            await self.session.initialize()
            
            # MCP 도구 로드
            tools = await load_mcp_tools(self.session)
            print(f"Loaded MCP tools count: {len(tools)}")
            print("Tools:", [tool.name for tool in tools])
            
            # 에이전트 생성
            self.agent = create_react_agent(self.llm, tools)
            self.initialized = True
            print(f"MCP Agent initialized successfully with {self.server_script}!")
            
        except Exception as e:
            print(f"Failed to initialize MCP Agent: {e}")
            raise e
    
    async def cleanup(self):
        """리소스 정리"""
        try:
            if self.session:
                await self.session.__aexit__(None, None, None)
            if self.stdio_client:
                await self.stdio_client.__aexit__(None, None, None)
            self.initialized = False
        except Exception as e:
            print(f"Cleanup error: {e}")

    async def chat_with_astream_graph(self, message: str):
        """utils.py의 astream_graph를 직접 사용 (원래 코드와 동일)"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # 원래 코드와 동일하게 astream_graph 사용
            await astream_graph(self.agent, {"messages": message})
        except Exception as e:
            print(f"에러가 발생했습니다: {str(e)}")

    async def chat_stream(self, message: str) -> AsyncGenerator[dict, None]:
        """스트리밍 채팅 응답 - 웹 API용 (이전 버전 호환성)"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # 에이전트 스트리밍 실행
            async for chunk in self.agent.astream(
                {"messages": message}, 
                stream_mode="messages"
            ):
                chunk_msg, metadata = chunk
                node = metadata.get("langgraph_node", "unknown")
                
                # 메시지 내용 추출 및 전송
                if hasattr(chunk_msg, 'content'):
                    content = self._extract_content(chunk_msg.content)
                    if content:
                        yield {
                            "type": "message",
                            "content": content,
                            "node": node
                        }
                        
        except Exception as e:
            yield {
                "type": "error",
                "content": f"에러가 발생했습니다: {str(e)}"
            }

    async def chat(self, message: str) -> AsyncGenerator[dict, None]:
        """멀티턴 대화 처리 - 토큰 관리 포함"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # 사용자 메시지를 대화 기록에 추가
            self.conversation_history.append({"role": "user", "content": message})
            
            # 토큰 제한에 맞게 대화 기록 정리
            max_tokens = Config.get_effective_max_tokens()
            self.conversation_history = trim_conversation_history(self.conversation_history, max_tokens)
            
            # 토큰 사용량 로그
            log_token_usage(self.conversation_history)
            
            # 대화 기록을 LangChain 메시지 형태로 변환
            from langchain_core.messages import HumanMessage, AIMessage
            
            messages = []
            for item in self.conversation_history:
                if item["role"] == "user":
                    messages.append(HumanMessage(content=item["content"]))
                elif item["role"] == "assistant":
                    messages.append(AIMessage(content=item["content"]))
            
            # 에이전트 스트리밍 실행
            response_content = ""
            async for chunk in self.agent.astream(
                {"messages": messages}, 
                stream_mode="messages"
            ):
                chunk_msg, metadata = chunk
                node = metadata.get("langgraph_node", "unknown")
                
                # 메시지 내용 추출 및 전송
                if hasattr(chunk_msg, 'content'):
                    content = self._extract_content(chunk_msg.content)
                    if content:
                        response_content += content
                        yield {
                            "type": "message",
                            "content": content,
                            "node": node
                        }
            
            # AI 응답을 대화 기록에 추가
            if response_content:
                self.conversation_history.append({"role": "assistant", "content": response_content})
                # 응답 추가 후 다시 토큰 제한 확인
                self.conversation_history = trim_conversation_history(self.conversation_history, max_tokens)
                        
        except Exception as e:
            yield {
                "type": "error",
                "content": f"에러가 발생했습니다: {str(e)}"
            }

    def clear_conversation(self):
        """대화 기록 초기화"""
        self.conversation_history = []
        print("💬 대화 기록이 초기화되었습니다.")
    
    def _extract_content(self, content) -> Optional[str]:
        """메시지 내용 추출 헬퍼 함수"""
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and "text" in item:
                    return item["text"]
        return None

    async def switch_server(self, new_server_script: str):
        """서버 동적 전환 - 핵심 기능!"""
        if self.initialized:
            await self.cleanup()
        
        self.server_script = new_server_script
        await self.initialize()
        print(f"Switched to server: {new_server_script}")


# 사용 가능한 서버들 정의
AVAILABLE_SERVERS = {
    "weather": "servers/user_assessment.py",
    "curriculum": "servers/generate_curriculum.py", 
    "evaluation": "servers/evaluate_user.py"
}

async def create_agent(server_type: str = "weather") -> MCPAgent:
    """서버 타입으로 에이전트 생성"""
    if server_type not in AVAILABLE_SERVERS:
        raise ValueError(f"Unknown server type: {server_type}. Available: {list(AVAILABLE_SERVERS.keys())}")
    
    server_script = AVAILABLE_SERVERS[server_type]
    agent = MCPAgent(server_script)
    await agent.initialize()
    return agent
