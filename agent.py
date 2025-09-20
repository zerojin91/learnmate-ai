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
    MENTOR_RECOMMENDATION = "mentor_recommendation"  # 전문가 멘토 페르소나 추천
    MENTOR_CHAT = "mentor_chat"  # 전문가 멘토링 대화
    PROFILING_GENERAL_CHAT = "profiling_general_chat"  # 프로파일링 중 일반 대화

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
        """사용자 메시지를 분류하여 적절한 액션 결정 - 프로파일링 우선순위 기반"""

        # 프로파일링 상태 확인 (최우선)
        profiling_status = await self._get_profiling_status()

        # 🎯 프로파일링 진행 중이면 단순 2분법
        if profiling_status["in_progress"]:
            print(f"📊 프로파일링 진행 중 - 2분법 분류 적용")

            # General Chat 여부만 판단
            general_chat_prompt = f"""다음 메시지가 학습과 완전히 무관한 일상 대화인지 판단하세요:

메시지: "{message}"

**학습 관련으로 보는 경우:**
- 시간 언급 : "주 3시간", "주 1시간", "하루 1시간"
- 수준 언급: "완전 초보자", "어려워", "중급자", "고급자", "초보", "처음"
- 목표 언급: "취업", "이직", "프로젝트", "취업 준비", "이직 준비", "프로젝트 준비"
- 학습 의지: "배우고 싶어", "공부하고 싶어", "학습하고 싶어"
- 기타 학습 관련 모든 내용

**판단 기준**: 학습과 100% 무관하고 명백한 일상 대화만 general_chat으로 분류
애매하면 무조건 학습 관련으로 판단하세요. 특히 '시간', '수준', '목표', '학습 의지' 와 관련된 메시지는 무조건 학습 관련으로 판단하세요."""

            try:
                # General Chat 판단을 위한 별도 분류
                from pydantic import BaseModel, Field

                class GeneralChatCheck(BaseModel):
                    is_profiling_chat: bool = Field(description="학습 관련 대화 여부")

                checker_model = self.llm.with_structured_output(GeneralChatCheck)
                check_result = checker_model.invoke(general_chat_prompt)

                if check_result.is_profiling_chat:
                    print(f"🔍 프로파일링 중 학습 관련으로 분류")
                    return ActionClassification(action=ActionType.USER_PROFILING)
                else:
                    print(f"🔍 프로파일링 중 일반 대화로 분류")
                    return ActionClassification(action=ActionType.PROFILING_GENERAL_CHAT)

            except Exception as e:
                print(f"❌ 일반 대화 체크 오류: {e}")
                # 오류 시 안전하게 프로파일링으로
                return ActionClassification(action=ActionType.USER_PROFILING)

        # 🎯 프로파일링 진행 중이 아닐 때는 기존 로직
        mentor_session_phase = await self._check_mentor_session_status()

        classification_prompt = f"""사용자 메시지를 다음 3가지 액션 중 하나로 분류하세요:

1. **general_chat**: 일반적인 인사, 안부, 감사 등 학습과 무관한 대화
2. **user_profiling**: 학습 관련 요청이지만 사용자 프로필이 필요한 경우
3. **generate_curriculum**: 이미 학습 프로필이 있고 커리큘럼/계획 생성을 요청하는 경우

사용자 메시지: "{message}"
현재 멘토 세션 상태: {mentor_session_phase}

## 분류 기준:
- "안녕", "고마워", "잘가", "라면먹고싶어" 등 → general_chat
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
                            profile_data = {k: v for k, v in profile_info.items() if v}
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

    async def _handle_profiling_general_chat_sequential(self, message: str) -> AsyncGenerator[dict, None]:
        """프로파일링 중 general chat 순차 처리: 일반 응답 → 연결 → 프로파일링"""
        print(f"🔄 프로파일링 중 일반 대화 순차 처리")

        try:
            # 1단계: 프로파일링이 진행 중인지 확인
            profiling_status = await self._get_profiling_status()

            if not profiling_status["in_progress"]:
                # 프로파일링이 진행중이 아니라면 일반 대화로 처리
                async for chunk in self._handle_general_chat(message):
                    yield chunk
                return

            # 2단계: 프로파일링 상태 확인
            profiling_status = await self._get_profiling_status()
            missing_info = []
            if not profiling_status.get("topic"):
                missing_info.append("학습 주제")
            if not profiling_status.get("constraints"):
                missing_info.append("현재 수준과 시간")
            if not profiling_status.get("goal"):
                missing_info.append("학습 목표")

            # 3단계: 자연스러운 통합 응답 생성
            integrated_prompt = f"""사용자가 일반적인 대화를 했습니다: "{message}"

이에 대해 친근하게 응답한 후, 자연스럽게 학습 프로파일링으로 연결해주세요.

현재 아직 파악하지 못한 정보: {', '.join(missing_info) if missing_info else '없음'}

요구사항:
1. 먼저 사용자의 말에 공감하고 친근하게 반응
2. 자연스러운 연결어나 문장으로 학습 관련 질문으로 이어가기
3. "그런데"와 같은 어색한 연결어 피하기
4. 전체 응답이 하나의 자연스러운 대화처럼 느껴지도록

예시:
사용자: "피곤해"
응답: "수고 많으셨어요! 😊 오늘 하루 정말 고생하셨네요. 휴식도 중요하지만, 혹시 어떤 분야를 배우고 싶으신지 궁금해요!"

자연스럽고 친근한 하나의 완전한 응답을 만들어주세요."""

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content="당신은 친근하고 자연스러운 학습 멘토입니다. 일반 대화와 학습 질문을 자연스럽게 연결하세요."),
                HumanMessage(content=integrated_prompt)
            ]

            # 통합 응답 스트리밍
            integrated_response = ""
            async for chunk in self.llm.astream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    integrated_response += chunk.content
                    print(chunk.content, end="", flush=True)
                    yield {"type": "message", "content": chunk.content, "node": "integrated_chat"}

            # 대화 기록에 추가
            if integrated_response:
                self.conversation_history.append({
                    "role": "assistant",
                    "content": integrated_response.strip()
                })

        except Exception as e:
            print(f"❌ 순차 처리 오류: {e}")
            yield {"type": "error", "content": f"응답 생성 중 오류가 발생했습니다: {str(e)}"}

    async def _get_profiling_status(self) -> dict:
        """현재 프로파일링 상태 확인"""
        try:
            if not self.current_session_id:
                return {"in_progress": False, "missing_step": None, "completion_rate": 0}

            from servers.user_assessment import load_session
            session_data = load_session(self.current_session_id)

            if not session_data:
                return {"in_progress": False, "missing_step": None, "completion_rate": 0}

            topic = session_data.get("topic", "").strip()
            constraints = session_data.get("constraints", "").strip()
            goal = session_data.get("goal", "").strip()

            topic_complete = bool(topic)
            # 제약조건은 수준과 시간이 모두 있어야 완료로 간주 (쉼표로 구분)
            constraints_complete = bool(constraints and "," in constraints)
            goal_complete = bool(goal)

            completed_steps = []
            if topic_complete: completed_steps.append("topic")
            if constraints_complete: completed_steps.append("constraints")
            if goal_complete: completed_steps.append("goal")

            completion_rate = len(completed_steps) / 3.0

            # 다음 필요한 단계 결정
            missing_step = None
            if not topic_complete:
                missing_step = "topic"
            elif not constraints_complete:
                missing_step = "constraints"
            elif not goal_complete:
                missing_step = "goal"

            is_in_progress = not (topic_complete and constraints_complete and goal_complete)

            return {
                "in_progress": is_in_progress,
                "missing_step": missing_step,
                "completion_rate": completion_rate,
                "completed_steps": completed_steps,
                "topic": topic,
                "constraints": constraints,
                "goal": goal
            }

        except Exception as e:
            print(f"❌ 프로파일링 상태 확인 오류: {e}")
            return {"in_progress": False, "missing_step": None, "completion_rate": 0}

    async def _check_mentor_session_status(self) -> str:
        """현재 멘토 세션 상태 확인"""
        try:
            if not self.current_session_id:
                return "no_session"

            # get_mentor_session_status 도구 찾기
            tools = await self.client.get_tools()
            status_tool = next((tool for tool in tools if tool.name == "get_mentor_session_status"), None)
            
            if not status_tool:
                return "no_mentor_tool"
            
            # 도구 실행
            result = await status_tool.ainvoke({"session_id": self.current_session_id})
            
            if isinstance(result, dict):
                if result.get("status") == "active":
                    return result.get("phase", "persona_recommendation")
            return "inactive"
            
        except Exception as e:
            print(f"❌ 멘토 세션 상태 확인 오류: {e}")
            return "error"

    async def _handle_mentor_recommendation(self, message: str) -> AsyncGenerator[dict, None]:
        """전문가 멘토 페르소나 추천 처리"""
        print(f"🎯 멘토 페르소나 추천 시작")
        
        try:
            # analyze_and_recommend_personas 도구 찾기
            tools = await self.client.get_tools()
            recommend_tool = next((tool for tool in tools if tool.name == "analyze_and_recommend_personas"), None)
            
            if not recommend_tool:
                yield {"type": "error", "content": "멘토 추천 도구를 찾을 수 없습니다."}
                return
            
            # 도구 실행
            tool_args = {"message": message, "session_id": self.current_session_id}
            print(f"🔧 analyze_and_recommend_personas 호출: {tool_args}")
            
            result = await recommend_tool.ainvoke(tool_args)
            
            if result:
                print(result, end="", flush=True)
                self.conversation_history.append({"role": "assistant", "content": result})
                yield {"type": "message", "content": result, "node": "mentor_recommendation"}
                
        except Exception as e:
            print(f"❌ 멘토 추천 오류: {e}")
            yield {"type": "error", "content": f"멘토 추천 중 오류가 발생했습니다: {str(e)}"}

    async def _handle_mentor_chat(self, message: str) -> AsyncGenerator[dict, None]:
        """전문가 멘토링 대화 처리"""
        print(f"👨‍🏫 전문가 멘토링 대화 처리")
        
        try:
            # 페르소나 선택인지 일반 멘토링인지 확인
            if any(keyword in message.lower() for keyword in ["선택", "고르", "결정", "원해"]):
                # 페르소나 선택 처리
                select_tool = None
                tools = await self.client.get_tools()
                select_tool = next((tool for tool in tools if tool.name == "select_persona"), None)
                
                if select_tool:
                    # 메시지에서 페르소나 ID 추출 (간단한 매핑)
                    persona_mapping = {
                        "건축": "architecture",
                        "토목": "civil_urban", "도시": "civil_urban",
                        "교통": "transport", "운송": "transport",
                        "기계": "mechanical", "금속": "mechanical",
                        "전기": "electrical", "전자": "electrical",
                        "정밀": "precision_energy", "에너지": "precision_energy",
                        "소재": "materials", "재료": "materials",
                        "컴퓨터": "computer", "통신": "computer",
                        "산업": "industrial",
                        "화공": "chemical"
                    }
                    
                    selected_persona = None
                    for key, value in persona_mapping.items():
                        if key in message:
                            selected_persona = value
                            break
                    
                    if selected_persona:
                        tool_args = {"persona_id": selected_persona, "session_id": self.current_session_id}
                        result = await select_tool.ainvoke(tool_args)
                        
                        if result:
                            print(result, end="", flush=True)
                            self.conversation_history.append({"role": "assistant", "content": result})
                            yield {"type": "message", "content": result, "node": "mentor_selection"}
                            return
            
            # 일반 멘토링 대화 처리
            expert_tool = None
            tools = await self.client.get_tools()
            expert_tool = next((tool for tool in tools if tool.name == "expert_mentoring"), None)
            
            if not expert_tool:
                yield {"type": "error", "content": "전문가 멘토링 도구를 찾을 수 없습니다."}
                return
            
            # 도구 실행
            tool_args = {"message": message, "session_id": self.current_session_id}
            print(f"🔧 expert_mentoring 호출: {tool_args}")
            
            result = await expert_tool.ainvoke(tool_args)
            
            if result:
                print(result, end="", flush=True)
                self.conversation_history.append({"role": "assistant", "content": result})
                yield {"type": "message", "content": result, "node": "mentor_chat"}
                
        except Exception as e:
            print(f"❌ 멘토 채팅 오류: {e}")
            yield {"type": "error", "content": f"멘토링 중 오류가 발생했습니다: {str(e)}"}

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
                    
            elif classification.action == ActionType.MENTOR_RECOMMENDATION:
                async for chunk in self._handle_mentor_recommendation(message):
                    yield chunk
                    
            elif classification.action == ActionType.MENTOR_CHAT:
                async for chunk in self._handle_mentor_chat(message):
                    yield chunk

            elif classification.action == ActionType.PROFILING_GENERAL_CHAT:
                # 순차적 처리: General Chat 응답 → 연결어 → 프로파일링
                async for chunk in self._handle_profiling_general_chat_sequential(message):
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
