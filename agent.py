"""
MCP Agent 모듈 - agent.ipynb의 로직을 모듈화
"""

from typing import AsyncGenerator, Optional, List, Dict
import json

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from utils import astream_graph, trim_conversation_history, log_token_usage, apply_chat_template
from config import Config


class MultiMCPAgent:
    """여러 MCP 서버를 동시에 연결하는 에이전트"""
    
    def __init__(self, server_scripts: List[str]):
        self.server_scripts = server_scripts
        self.client = None
        self.agent = None
        self.initialized = False
        
        # 대화 기록 관리 - 기본 인사말 포함
        self.conversation_history: List[Dict[str, str]] = [
            {
                "role": "assistant", 
                "content": "안녕하세요! LearnAI의 학습 멘토입니다. 어떤 주제에 대해 배우고 싶으신지 알려주세요. 맞춤형 학습 계획을 함께 만들어보겠습니다!"
            }
        ]
        
        # LLM 설정
        self.llm = ChatOpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY,
            model=Config.LLM_MODEL,
            temperature=Config.LLM_TEMPERATURE,
            max_tokens=Config.LLM_MAX_TOKENS,
        )
    
    async def initialize(self):
        """여러 MCP 서버 동시 초기화 - 공식 방법 사용"""
        if self.initialized:
            return
            
        try:
            # MCP 서버 설정을 딕셔너리로 변환
            server_configs = {}
            for i, server_script in enumerate(self.server_scripts):
                server_name = f"server_{i}"
                server_configs[server_name] = {
                    "command": "python",
                    "args": [server_script],
                    "transport": "stdio"
                }
            
            print(f"서버 설정: {server_configs}")
            
            # MultiServerMCPClient 생성
            self.client = MultiServerMCPClient(server_configs)
            
            # 모든 도구 가져오기
            tools = await self.client.get_tools()
            print(f"로드된 도구들: {[tool.name for tool in tools]}")
            
            # LearnMate AI 시스템 프롬프트
            system_prompt = """당신은 LearnAI의 학습 멘토입니다. 모든 상황에서 학습과 교육에 초점을 맞춘 전문가로 행동하세요.

## 핵심 정체성
- 이름: LearnAI 학습 멘토
- 역할: 개인화된 학습 계획 수립 및 멘토링 전문가
- 목표: 모든 대화를 학습과 성장 기회로 전환

## 대화 원칙
1. **모든 인사와 일반 질문**에 대해서도 학습 멘토로서 응답
   - "안녕하세요! LearnAI의 학습 멘토입니다."로 시작
   - 항상 "어떤 주제에 대해 배우고 싶으신지 알려주세요"와 같이 학습으로 유도
   - "맞춤형 학습 계획을 함께 만들어보겠습니다"라는 제안 포함

2. **응답 스타일**:
   - 친근하고 격려하는 톤
   - 구체적이고 실용적인 조언
   - 학습 동기 부여에 집중

## 도구 사용 규칙
- <tool_call>{"name": "tool_name", "arguments": {"param":"value"}}</tool_call> 형식 사용
- 학습 의도가 감지되면 반드시 user_profiling 도구 먼저 호출

## 예시 응답들
- 일반 인사: "안녕하세요! LearnAI의 학습 멘토입니다. 어떤 주제를 배우고 싶으신가요? 맞춤형 학습 계획을 함께 만들어보겠습니다!"
- 비학습 질문도: "그 질문도 흥미롭네요! 그런데 제가 가장 잘 도와드릴 수 있는 분야는 학습 계획 수립입니다. 새로 배우고 싶은 기술이나 주제가 있으시다면 알려주세요!"

모든 상황에서 학습 멘토의 정체성을 유지하며, 사용자를 학습의 여정으로 안내하세요."""

            # 시스템 프롬프트를 LLM에 바인드
            llm_with_system = self.llm.bind(system=system_prompt)
            
            # ReAct 에이전트 생성 (Mi:dm 시스템 프롬프트 포함)
            self.agent = create_react_agent(llm_with_system, tools)
            
            self.initialized = True
            print(f"✅ MultiMCP Agent 초기화 완료 - {len(tools)}개 도구 로드됨!")
            
        except Exception as e:
            print(f"❌ MultiMCP Agent 초기화 실패: {e}")
            await self.cleanup()
            raise e
    
    async def cleanup(self):
        """리소스 정리"""
        try:
            if self.client:
                await self.client.close()
            self.initialized = False
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    async def chat(self, message: str) -> AsyncGenerator[dict, None]:
        """멀티턴 대화 처리 - 모든 서버의 도구 사용 가능"""
        if not self.initialized:
            await self.initialize()
        
        try:
            # 모든 메시지에 "(툴 사용해)" 강제 추가
            # modified_message = f"{message} (툴 사용해)"
            modified_message = f"{message}"
            print(f"🔧 메시지 수정: {modified_message}")
            
            # 사용자 메시지를 대화 기록에 추가 (원본 저장)
            self.conversation_history.append({"role": "user", "content": message})
            
            # 토큰 제한에 맞게 대화 기록 정리
            max_tokens = Config.get_effective_max_tokens()
            self.conversation_history = trim_conversation_history(self.conversation_history, max_tokens)
            
            # 토큰 사용량 로그
            log_token_usage(self.conversation_history)
            
            # 시스템 프롬프트 정의
            system_prompt_text = """당신은 LearnAI의 학습 멘토입니다. 모든 상황에서 학습과 교육에 초점을 맞춘 전문가로 행동하세요.

## 핵심 정체성
- 이름: LearnAI 학습 멘토
- 역할: 개인화된 학습 계획 수립 및 멘토링 전문가
- 목표: 모든 대화를 학습과 성장 기회로 전환

## 대화 원칙
1. **모든 인사와 일반 질문**에 대해서도 학습 멘토로서 응답
   - "안녕하세요! LearnAI의 학습 멘토입니다."로 시작
   - 항상 "어떤 주제에 대해 배우고 싶으신지 알려주세요"와 같이 학습으로 유도
   - "맞춤형 학습 계획을 함께 만들어보겠습니다"라는 제안 포함

2. **응답 스타일**:
   - 친근하고 격려하는 톤
   - 구체적이고 실용적인 조언
   - 학습 동기 부여에 집중

## 도구 사용 규칙
- <tool_call>{"name": "tool_name", "arguments": {"param":"value"}}</tool_call> 형식 사용
- 학습 의도가 감지되면 반드시 user_profiling 도구 먼저 호출"""

            # LangChain 메시지 형식으로 변환 (스트리밍을 위해)
            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
            
            messages = [SystemMessage(content=system_prompt_text)]
            
            # 대화 기록 추가
            for i, item in enumerate(self.conversation_history):
                if item["role"] == "user":
                    # 마지막 사용자 메시지만 "(툴 사용해)" 추가
                    content = modified_message if i == len(self.conversation_history) - 1 else item["content"]
                    messages.append(HumanMessage(content=content))
                elif item["role"] == "assistant":
                    messages.append(AIMessage(content=item["content"]))
            
            print(f"🔄 메시지 변환 완료 ({len(messages)}개 메시지)")
            
            # 직접 스트리밍 실행 (더 나은 스트리밍을 위해)
            print(f"\n🤖 AI 응답 시작:")
            response_content = ""
            
            async for chunk in self.agent.astream(
                {"messages": messages}, 
                stream_mode="messages"
            ):
                chunk_msg, metadata = chunk
                node = metadata.get("langgraph_node", "unknown")
                
                # 도구 호출 감지 및 로깅
                if hasattr(chunk_msg, 'tool_calls') and chunk_msg.tool_calls:
                    for tool_call in chunk_msg.tool_calls:
                        print(f"\n🔧 도구 호출: {tool_call.get('name', 'Unknown')} - {tool_call.get('args', {})}")
                
                # 메시지 내용 추출 및 전송
                if hasattr(chunk_msg, 'content'):
                    content = self._extract_content(chunk_msg.content)
                    if content:
                        response_content += content
                        # 터미널에 실시간 응답 출력
                        print(content, end="", flush=True)
                        yield {
                            "type": "message",
                            "content": content,
                            "node": node
                        }
            
            # AI 응답을 대화 기록에 추가
            if response_content:
                self.conversation_history.append({"role": "assistant", "content": response_content})
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


class MCPAgent:
    """단일 MCP 서버용 에이전트 클래스"""
    
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
        """MCP 에이전트 초기화"""
        if self.initialized:
            return
            
        try:
            # StdIO 서버 파라미터 설정
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
                # 응답 완료 로그
                print(f"\n\n✅ AI 응답 완료 ({len(response_content)} 글자)")
            else:
                print(f"\n\n⚠️ AI 응답 없음")
                        
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
