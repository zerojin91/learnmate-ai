"""
MCP Agent 모듈 - Stateful Multi-Agent System과 연동
"""

from typing import AsyncGenerator, Optional, List, Dict
import json
import re

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from utils import astream_graph, trim_conversation_history, log_token_usage, apply_chat_template
from config import Config

class MultiMCPAgent:
    """여러 MCP 서버를 동시에 연결하는 에이전트 with Stateful Assessment"""
    
    def __init__(self, server_scripts: List[str]):
        self.server_scripts = server_scripts
        self.client = None
        self.agent = None
        self.initialized = False
        
        # 세션 상태 관리
        self.current_session_id = None
        self.assessment_in_progress = False
        
        # 대화 기록 관리 - 기본 인사말 포함
        self.conversation_history: List[Dict[str, str]] = [
            {
                "role": "assistant", 
                "content": "안녕하세요! LearnAI 입니다. 어떤 주제에 대해 배우고 싶으신지 알려주시면 맞춤형 학습 계획을 함께 만들어보겠습니다!"
            }
        ]
        self.max_tokens = Config.LLM_MAX_TOKENS

        # LLM 설정
        self.llm = ChatOpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY,
            model=Config.LLM_MODEL,
            temperature=Config.LLM_TEMPERATURE,
            max_tokens=self.max_tokens,
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
                # MultiServerMCPClient는 close 메서드가 없으므로 제거
                pass
            self.initialized = False
        except Exception as e:
            print(f"Cleanup error: {e}")
    
    def _extract_session_id(self, response_content: str) -> Optional[str]:
        """응답에서 세션 ID 추출"""
        session_match = re.search(r'Session:\s*([a-zA-Z0-9-]+)', response_content)
        if session_match:
            return session_match.group(1)
        return None
    
    def _should_use_assessment_tool(self, message: str) -> bool:
        """Assessment 도구를 사용해야 하는지 판단"""
        learning_keywords = [
            "배우고 싶어", "공부하고 싶어", "학습", "익히고", "시작하고 싶어",
            "배우기", "공부", "익히기", "시작하기", "가르쳐", "알고 싶어"
        ]
        
        # 이미 assessment가 진행 중이라면 계속 사용
        if self.assessment_in_progress:
            return True
            
        # 새로운 학습 의도가 감지되면 사용
        return any(keyword in message for keyword in learning_keywords)
    
    async def chat(self, message: str) -> AsyncGenerator[dict, None]:
        """멀티턴 대화 처리 - Stateful Assessment 지원"""
        if not self.initialized:
            await self.initialize()
        
        try:
            print(f"📝 사용자 메시지: {message}")
            
            # 사용자 메시지를 대화 기록에 추가 (원본 저장)
            self.conversation_history.append({"role": "user", "content": message})
            
            # 토큰 제한에 맞게 대화 기록 정리
            self.conversation_history = trim_conversation_history(self.conversation_history, self.max_tokens)
            
            # 토큰 사용량 로그
            log_token_usage(self.conversation_history)
            
            # Assessment 도구 사용 여부 결정
            should_assess = self._should_use_assessment_tool(message)
            
            if should_assess:
                # Assessment 도구 직접 호출 (Stateful)
                async for chunk in self._handle_assessment_flow(message):
                    yield chunk
            else:
                # 일반 멘토링 대화 처리
                async for chunk in self._handle_general_conversation(message):
                    yield chunk
                        
        except Exception as e:
            yield {
                "type": "error",
                "content": f"에러가 발생했습니다: {str(e)}"
            }
    
    async def _handle_assessment_flow(self, message: str) -> AsyncGenerator[dict, None]:
        """Assessment 플로우 처리"""
        print(f"📊 Assessment 플로우 시작 (Session: {self.current_session_id})")
        
        try:
            # user_profiling 도구 직접 호출
            tools = await self.client.get_tools()
            user_profiling_tool = None
            
            for tool in tools:
                if tool.name == "user_profiling":
                    user_profiling_tool = tool
                    break
            
            if not user_profiling_tool:
                yield {
                    "type": "error", 
                    "content": "Assessment 도구를 찾을 수 없습니다."
                }
                return
            
            # 도구 호출 인자 구성 - 항상 세션 ID 포함
            tool_args = {
                "user_message": message,
                "session_id": self.current_session_id
            }
            
            print(f"🔧 도구 호출: user_profiling - {tool_args}")
            
            # 도구 실행
            result = await user_profiling_tool.ainvoke(tool_args)
            
            # 세션 ID 추출 및 상태 업데이트
            extracted_session_id = self._extract_session_id(result)
            if extracted_session_id:
                self.current_session_id = extracted_session_id
            
            # Assessment 상태 업데이트
            if "Complete" in result:
                self.assessment_in_progress = False
                print("✅ Assessment 완료!")
            else:
                self.assessment_in_progress = True
                print("🔄 Assessment 진행 중...")
            
            # 응답 스트리밍
            if result:
                print(result, end="", flush=True)
                self.conversation_history.append({"role": "assistant", "content": result})
                
                # 세션에서 프로필 정보 가져오기
                profile_data = None
                try:
                    from servers.user_assessment import load_session
                    if self.current_session_id:
                        session_data = load_session(self.current_session_id)
                        if session_data:
                            profile_info = {
                                'topic': session_data.get('topic', ''),
                                'constraints': session_data.get('constraints', ''),
                                'goal': session_data.get('goal', '')
                            }
                            # 빈 값이 아닌 것만 포함
                            profile_data = {k: v for k, v in profile_info.items() if v}
                            print(f"📊 Assessment에서 프로필 전송: {profile_data}")
                except Exception as e:
                    print(f"프로필 로드 오류: {e}")
                
                response_chunk = {
                    "type": "message",
                    "content": result,
                    "node": "assessment_tool"
                }
                
                # 프로필 정보가 있으면 추가
                if profile_data:
                    response_chunk["profile"] = profile_data
                
                yield response_chunk
            
        except Exception as e:
            print(f"❌ Assessment 플로우 오류: {e}")
            yield {
                "type": "error",
                "content": f"Assessment 중 오류가 발생했습니다: {str(e)}"
            }
    
    async def _handle_general_conversation(self, message: str) -> AsyncGenerator[dict, None]:
        """일반 멘토링 대화 처리"""
        print(f"🏠 일반 멘토링 대화 시작")
        
        try:
            # 시스템 프롬프트 정의
            system_prompt_text = """당신은 LearnAI의 학습 멘토입니다.

## 핵심 정체성
- 이름: LearnAI 학습 멘토
- 역할: 개인화된 학습 계획 수립 및 멘토링 전문가
- 목표: 사용자의 학습과 성장을 지원

## 대화 원칙
1. **친근하고 격려하는 톤**으로 응답하세요
2. **구체적이고 실용적인 조언**을 제공하세요
3. **학습 동기 부여**에 집중하세요
4. 필요시 다른 도구들을 활용하세요

## 응답 스타일
- 따뜻하고 지지적인 어조
- 단계별 구체적 가이드라인 
- 실현 가능한 목표 설정 도움"""

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
            
            # 직접 스트리밍 실행
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
                self.conversation_history = trim_conversation_history(self.conversation_history, self.max_tokens)
                
        except Exception as e:
            print(f"❌ 일반 대화 처리 오류: {e}")
            yield {
                "type": "error",
                "content": f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            }
    
    def clear_conversation(self):
        """대화 기록 초기화"""
        self.conversation_history = []
        self.current_session_id = None
        self.assessment_in_progress = False
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


# 기존 호환성을 위한 별칭
MultiAgentSystem = MultiMCPAgent