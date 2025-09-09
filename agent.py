"""
MCP Agent 모듈 - Stateful Multi-Agent System과 연동
"""

from typing import AsyncGenerator, Optional, List, Dict
import json
import re
from pydantic import BaseModel, Field
from enum import Enum

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from utils import astream_graph, trim_conversation_history, log_token_usage, apply_chat_template
from config import Config

class ActionType(str, Enum):
    """사용자 메시지에 대한 액션 유형"""
    GENERAL_CHAT = "general_chat"           # 일반 대화
    USER_PROFILING = "user_profiling"       # 학습 프로필 수집 필요
    GENERATE_CURRICULUM = "generate_curriculum"  # 커리큘럼 생성

class ActionClassification(BaseModel):
    """액션 분류 결과"""
    action: ActionType = Field(description="수행할 액션 타입")
    
class MultiMCPAgent:
    """여러 MCP 서버를 동시에 연결하는 에이전트 with Stateful Assessment"""
    
    def __init__(self, server_scripts: List[str]):
        self.server_scripts = server_scripts
        self.client = None
        self.agent = None
        self.initialized = False
        
        # 세션 상태 관리
        self.current_session_id = None
        
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
            model_kwargs={"max_completion_tokens": None}  # Friendli.ai에서 지원하지 않는 파라미터 제거
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
            
            # MCP 방식: ReAct 에이전트가 필요한 도구를 자동으로 선택
            async for chunk in self._handle_unified_conversation(message):
                yield chunk
                        
        except Exception as e:
            yield {
                "type": "error",
                "content": f"에러가 발생했습니다: {str(e)}"
            }
    
    
    async def _classify_user_intent(self, message: str) -> ActionClassification:
        """사용자 메시지를 분류하여 적절한 액션 결정"""
        classification_prompt = f"""사용자 메시지를 다음 3가지 액션 중 하나로 분류하세요:

1. **general_chat**: 일반적인 인사, 안부, 감사 등 학습과 무관한 대화
2. **user_profiling**: 학습 관련 요청이지만 사용자 프로필이 필요한 경우
3. **generate_curriculum**: 이미 학습 프로필이 있고 커리큘럼/계획 생성을 요청하는 경우

사용자 메시지: "{message}"

## 분류 기준:
- "안녕", "고마워", "잘가" 등 → general_chat
- "~배우고 싶어", "~공부하고 싶어", "~가르쳐줘" 등 → user_profiling  
- "커리큘럼 만들어줘", "학습계획 세워줘", "로드맵 보여줘" 등 → generate_curriculum

정확한 액션만 선택하세요."""

        try:
            classifier_model = self.llm.with_structured_output(ActionClassification)
            result = classifier_model.invoke(classification_prompt)
            print(f"🔍 의도 분류 결과: {result.action}")
            return result
        except Exception as e:
            print(f"❌ 의도 분류 오류: {e}")
            # 기본값으로 일반 대화 선택
            return ActionClassification(action=ActionType.GENERAL_CHAT)

    async def _handle_user_profiling(self, message: str) -> AsyncGenerator[dict, None]:
        """user_profiling 도구를 사용한 프로필 수집"""
        print(f"📊 사용자 프로필링 시작")
        
        try:
            # user_profiling 도구 찾기
            tools = await self.client.get_tools()
            user_profiling_tool = next((tool for tool in tools if tool.name == "user_profiling"), None)
            
            if not user_profiling_tool:
                yield {"type": "error", "content": "사용자 프로필링 도구를 찾을 수 없습니다."}
                return
            
            # 도구 실행
            tool_args = {"user_message": message, "session_id": self.current_session_id}
            print(f"🔧 user_profiling 호출: {tool_args}")
            
            result = await user_profiling_tool.ainvoke(tool_args)
            
            if result:
                print(result, end="", flush=True)
                self.conversation_history.append({"role": "assistant", "content": result})
                
                # 도구 호출 후 최신 프로필 정보 로드
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
                            # 빈 값도 포함하여 전체 프로필 정보 전달 (UI에서 상태 표시를 위해)
                            profile_data = profile_info
                            print(f"📊 최신 프로필 로드: {profile_data}")
                except Exception as e:
                    print(f"프로필 로드 오류: {e}")
                
                response_data = {"type": "message", "content": result, "node": "user_profiling"}
                if profile_data:
                    response_data["profile"] = profile_data
                    
                yield response_data
                
        except Exception as e:
            print(f"❌ 사용자 프로필링 오류: {e}")
            yield {"type": "error", "content": f"프로필링 중 오류가 발생했습니다: {str(e)}"}

    async def _handle_curriculum_generation(self, message: str) -> AsyncGenerator[dict, None]:
        """generate_curriculum_from_session 도구를 사용한 커리큘럼 생성"""
        print(f"📚 커리큘럼 생성 시작")
        
        try:
            # generate_curriculum_from_session 도구 찾기
            tools = await self.client.get_tools()
            curriculum_tool = next((tool for tool in tools if tool.name == "generate_curriculum_from_session"), None)
            
            if not curriculum_tool:
                yield {"type": "error", "content": "커리큘럼 생성 도구를 찾을 수 없습니다."}
                return
            
            # 도구 실행 (사용자 메시지도 전달)
            tool_args = {
                "session_id": self.current_session_id,
                "user_message": message
            }
            print(f"🔧 generate_curriculum_from_session 호출: {tool_args}")
            
            result = await curriculum_tool.ainvoke(tool_args)
            
            if result:
                print(result, end="", flush=True)
                self.conversation_history.append({"role": "assistant", "content": result})
                
                # 커리큘럼 JSON 데이터 파싱 시도
                try:
                    # result가 JSON 형태인지 확인하고 파싱
                    if result.strip().startswith('{') and '"title"' in result and '"modules"' in result:
                        import json
                        curriculum_data = json.loads(result)
                        print(f"📚 커리큘럼 데이터 파싱 성공: {curriculum_data.get('title', 'Unknown')}")
                        
                        # curriculum 속성으로 전달
                        yield {"type": "message", "content": result, "curriculum": curriculum_data, "node": "generate_curriculum"}
                    else:
                        # 일반 텍스트 응답
                        yield {"type": "message", "content": result, "node": "generate_curriculum"}
                        
                except json.JSONDecodeError as e:
                    print(f"⚠️ 커리큘럼 JSON 파싱 실패: {e}")
                    # JSON 파싱 실패해도 일반 응답으로 처리
                    yield {"type": "message", "content": result, "node": "generate_curriculum"}
                
        except Exception as e:
            print(f"❌ 커리큘럼 생성 오류: {e}")
            yield {"type": "error", "content": f"커리큘럼 생성 중 오류가 발생했습니다: {str(e)}"}

    async def _handle_general_chat(self, message: str) -> AsyncGenerator[dict, None]:
        """일반 대화 처리 (도구 없이)"""
        print(f"💬 일반 대화 처리")
        
        try:
            # LearnAI 성격의 일반 대화 프롬프트
            system_prompt = """당신은 LearnAI의 친근한 학습 멘토입니다.
            
따뜻하고 격려하는 성격으로 사용자와 자연스럽게 대화하세요.
일반적인 인사, 안부, 감사 등에 친근하게 응답하되, 
항상 학습에 대한 관심을 열어두고 도움이 필요하면 언제든 말해달라고 격려하세요."""

            from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
            
            messages = [SystemMessage(content=system_prompt)]
            
            # 최근 대화 기록만 포함 (토큰 절약)
            for item in self.conversation_history[-4:]:
                if item["role"] == "user":
                    messages.append(HumanMessage(content=item["content"]))
                elif item["role"] == "assistant":
                    messages.append(AIMessage(content=item["content"]))
            
            # LLM 직접 호출 (도구 없이)
            response_content = ""
            async for chunk in self.llm.astream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    response_content += chunk.content
                    print(chunk.content, end="", flush=True)
                    yield {"type": "message", "content": chunk.content, "node": "general_chat"}
            
            if response_content:
                self.conversation_history.append({"role": "assistant", "content": response_content})
                
        except Exception as e:
            print(f"❌ 일반 대화 오류: {e}")
            yield {"type": "error", "content": f"응답 생성 중 오류가 발생했습니다: {str(e)}"}

    async def _handle_unified_conversation(self, message: str) -> AsyncGenerator[dict, None]:
        """분류 기반 대화 처리 - with_structured_output으로 명확한 액션 선택"""
        print(f"🤖 분류 기반 대화 처리 시작")
        
        try:
            # 1. 사용자 의도 분류
            classification = await self._classify_user_intent(message)
            
            # 2. 분류 결과에 따라 처리
            if classification.action == ActionType.USER_PROFILING:
                async for chunk in self._handle_user_profiling(message):
                    yield chunk
                    
            elif classification.action == ActionType.GENERATE_CURRICULUM:
                async for chunk in self._handle_curriculum_generation(message):
                    yield chunk
                    
            else:  # GENERAL_CHAT
                async for chunk in self._handle_general_chat(message):
                    yield chunk
                
        except Exception as e:
            print(f"❌ 통합 대화 처리 오류: {e}")
            yield {
                "type": "error",
                "content": f"응답 생성 중 오류가 발생했습니다: {str(e)}"
            }
    
    def clear_conversation(self):
        """대화 기록 초기화"""
        self.conversation_history = []
        self.current_session_id = None
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
