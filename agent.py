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
            
            # ReAct 에이전트 생성
            self.agent = create_react_agent(self.llm, tools)
            
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
            print(f"📝 사용자 메시지: {message}")
            
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
            for item in self.conversation_history:
                if item["role"] == "user":
                    messages.append(HumanMessage(content=item["content"]))
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


