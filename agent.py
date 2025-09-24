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
        """사용자 메시지를 분류하여 적절한 액션 결정"""

        # 프로파일링 상태 확인
        profiling_status = await self._get_profiling_status()

        # 프로파일링 진행 중인 경우
        if profiling_status["in_progress"]:
            print(f"📊 프로파일링 진행 중 (완료율: {profiling_status['completion_rate']*100:.0f}%)")

            # 최근 대화 컨텍스트 포함 (AI 질문 + 사용자 답변 맥락 파악)
            recent_context = ""
            if len(self.conversation_history) >= 2:
                # 마지막 AI 메시지와 현재 사용자 메시지
                last_ai = self.conversation_history[-1] if self.conversation_history[-1]["role"] == "assistant" else None
                if last_ai:
                    recent_context = f"AI 질문: {last_ai['content'][:100]}...\n"

            classification_prompt = f"""프로파일링 중인 사용자의 메시지를 분류하세요.

{recent_context}사용자 답변: "{message}"

현재 수집된 정보:
- 학습 주제: {profiling_status.get('topic', '미수집')}
- 수준/시간: {profiling_status.get('constraints', '미수집')}
- 학습 목표: {profiling_status.get('goal', '미수집')}

분류 기준:

1. **profiling_general_chat** (우선 체크): 다음 중 하나에 해당하면 무조건 이것으로 분류
   - 순수 인사: "안녕", "안녕하세요", "하이", "hi", "hello"
   - 감사 표현: "고마워", "감사해", "thanks", "고맙습니다"
   - 작별 인사: "잘가", "바이", "bye", "안녕히"
   - 완전 일상: "날씨 어때?", "뭐해?", "잘지내?"

2. **user_profiling**: 위에 해당하지 않고 학습 관련 정보가 있는 경우
   - 학습 주제: 파이썬, 자바, 영어, 외국어, 데이터분석 등
   - 수준/경험: 초보, 2년 경험, 기초는 알아 등
   - 학습 목표/이유: 취업, 이직, 프로젝트, 친구들과 대화, 업무에 필요해서 등
   - 학습 시간: 주 3시간, 매일 1시간 등

**중요**: 먼저 profiling_general_chat을 체크하고, 해당하지 않으면 user_profiling으로 분류하세요."""

            try:
                from pydantic import BaseModel, Field
                from enum import Enum

                class ProfilingAction(str, Enum):
                    USER_PROFILING = "user_profiling"  # 학습 정보 제공
                    PROFILING_GENERAL_CHAT = "profiling_general_chat"  # 일반 대화

                class ProfilingClassification(BaseModel):
                    action: ProfilingAction = Field(
                        description="user_profiling(학습주제/수준/목표 관련) 또는 profiling_general_chat(일상대화)"
                    )

                classifier = self.llm.with_structured_output(ProfilingClassification)
                result = classifier.invoke(classification_prompt)

                print(f"🔍 분류: {result.action}")

                if result.action == ProfilingAction.USER_PROFILING:
                    return ActionClassification(action=ActionType.USER_PROFILING)
                else:
                    return ActionClassification(action=ActionType.PROFILING_GENERAL_CHAT)

            except Exception as e:
                print(f"❌ 분류 오류: {e}")
                return ActionClassification(action=ActionType.USER_PROFILING)

        # 프로파일링 완료된 경우
        else:
            print(f"✅ 프로파일링 완료 상태")

            classification_prompt = f"""사용자 메시지의 의도를 분류하세요.

사용자 메시지: "{message}"

분류 기준:
1. **generate_curriculum**: 커리큘럼/학습계획 생성 요청 또는 긍정적 응답
   - 예: "커리큘럼 만들어줘", "학습 계획 세워줘", "로드맵 보여줘"
   - 예: "응", "좋아", "시작해줘", "네", "그래", "해줘", "만들어줘"
   - 예: "맞춤형 계획 만들어줘", "생성해줘", "시작하자"

2. **user_profiling**: 새로운 학습 주제 또는 프로필 수정
   - 예: "다른 것도 배우고 싶어", "목표가 바뀌었어", "아니 다시 할게"

3. **general_chat**: 일반 대화 (커리큘럼과 무관한)
   - 예: "고마워", "안녕", "뭐하고 있어?"

**중요**: 프로파일링 완료 후 긍정적인 응답은 대부분 generate_curriculum으로 분류하세요."""

            try:
                classifier = self.llm.with_structured_output(ActionClassification)
                result = classifier.invoke(classification_prompt)
                print(f"🔍 의도 분류: {result.action}")
                return result
            except Exception as e:
                print(f"❌ 분류 오류: {e}")
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
                # 글자별로 스트리밍처럼 출력 (각각 개별 전송)
                import asyncio

                for char in result:
                    print(char, end="", flush=True)
                    yield {"type": "message", "content": char, "node": "user_profiling"}
                    await asyncio.sleep(0.05)  # 글자별 딜레이

                # 스트리밍 완료 신호
                yield {"type": "streaming_complete", "node": "user_profiling"}

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
                            if profile_data:  # 비어있지 않을 때만 출력
                                print(f"📊 현재 프로필: {profile_data}")
                except Exception as e:
                    print(f"프로필 로드 오류: {e}")

                # 최종 완성된 응답 전송
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

                # 탭 전환 신호 먼저 전송
                yield {"type": "curriculum_created", "content": "✅ 맞춤형 커리큘럼이 생성되었습니다! 상단의 \"나의 커리큘럼\" 탭에서 확인해보세요."}

                # 일반 메시지도 전송
                yield {"type": "message", "content": result, "node": "generate_curriculum"}
                
        except Exception as e:
            print(f"❌ 커리큘럼 생성 오류: {e}")
            yield {"type": "error", "content": f"커리큘럼 생성 중 오류가 발생했습니다: {str(e)}"}

    async def _handle_general_chat(self, message: str) -> AsyncGenerator[dict, None]:
        """일반 대화 처리 (도구 없이)"""
        print(f"💬 일반 대화 처리")
        
        try:
            # LearnAI 성격의 일반 대화 프롬프트 - 학습으로 자연스럽게 유도
            system_prompt = """당신은 LearnMate의 친근한 학습 멘토입니다.

사용자의 일반적인 대화(인사, 안부, 감사 등)에 자연스럽게 응답한 후,
반드시 학습 관련 질문으로 대화를 유도하세요.

응답 구조:
1. 사용자 메시지에 대한 적절한 일반 응답 (1-2문장)
2. 자연스러운 연결어 사용
3. 학습 관련 질문으로 유도 (예: "혹시 요즘 배우고 싶은 것이 있으신가요?", "새로 도전해보고 싶은 분야는 없으신가요?")

예시:
- 사용자: "안녕하세요" → "안녕하세요! 반갑습니다. 혹시 오늘 새로 배워보고 싶은 것이 있으신가요?"
- 사용자: "고마워" → "천만에요! 그런데 혹시 요즘 관심 있는 학습 분야가 있으신가요?"

LearnMate는 학습 서비스이므로 항상 학습 방향으로 대화를 이끌어야 합니다."""

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

            # 2단계: 프로파일링 상태 확인 및 진행률 표시
            topic = profiling_status.get("topic", "")
            constraints = profiling_status.get("constraints", "")
            goal = profiling_status.get("goal", "")

            # 진행률 계산
            missing_info = []
            progress_items = []

            if not topic:
                missing_info.append("학습 주제")
                progress_items.append("❌ 학습 주제")
            else:
                progress_items.append(f"✅ 학습 주제: {topic}")

            level_keywords = ["초보", "중급", "고급", "수준", "경험", "처음", "입문", "기초"]
            has_level = any(kw in constraints for kw in level_keywords)

            if not has_level:
                missing_info.append("현재 수준")
                progress_items.append("❌ 현재 수준")
            else:
                level_part = next((part for part in constraints.split(',') if any(kw in part for kw in level_keywords)), constraints)
                progress_items.append(f"✅ 현재 수준: {level_part.strip()}")

            if not goal:
                missing_info.append("학습 목표")
                progress_items.append("❌ 학습 목표")
            else:
                progress_items.append(f"✅ 학습 목표: {goal}")

            completed_count = 3 - len(missing_info)
            progress_bar = "🟩" * completed_count + "⬜" * len(missing_info)

            # 3단계: 자연스러운 통합 응답 생성
            next_needed = missing_info[0] if missing_info else None

            integrated_prompt = f"""사용자가 일반적인 대화를 했습니다: "{message}"

이에 대해 친근하게 응답한 후, 자연스럽게 학습 관련 질문으로 연결해주세요.

현재 상황:
- 학습 주제: {"파악됨 (" + topic + ")" if topic else "아직 필요"}
- 현재 수준: {"파악됨" if has_level else "아직 필요"}
- 학습 목표: {"파악됨 (" + goal + ")" if goal else "아직 필요"}

{f"다음에 알아봐야 할 것: {next_needed}" if next_needed else ""}

**중요**: 이미 학습 주제가 "{topic}"로 정해져 있습니다. 절대 다른 주제를 묻지 말고, 반드시 {topic}에 대한 {next_needed if next_needed else "추가 정보"}를 물어보세요.

**필수 요구사항**: 응답 마지막에 반드시 "{topic}에 대한 질문"을 포함해야 합니다.

요구사항:
1. 먼저 사용자의 말에 공감하고 친근하게 반응
2. 자연스러운 연결어나 문장으로 학습 관련 질문으로 이어가기
3. "그런데", "진행률", "상태" 같은 어색한 표현 피하기
4. 전체 응답이 하나의 자연스러운 대화처럼 느껴지도록
5. 다음 필요한 정보를 자연스럽게 물어보기

예시:
사용자: "피곤해" (주제가 이미 파이썬으로 정해진 상태)
응답: "수고 많으셨어요! 😊 오늘 하루 정말 고생하셨네요. 휴식도 중요하지만, 파이썬 경험이 어느 정도 있으신지 궁금해요!"

사용자: "아니..." (주제가 이미 파이썬으로 정해진 상태)
응답: "그렇군요! 😊 괜찮아요. 그런데 파이썬 경험이 어느 정도 있으신가요? 처음 시작하시는 건가요, 아니면 조금 해보셨나요?"

자연스럽고 친근한 하나의 완전한 응답을 만들어주세요."""

            from langchain_core.messages import HumanMessage, SystemMessage

            messages = [
                SystemMessage(content=f"당신은 친근하고 자연스러운 학습 멘토입니다. 사용자의 학습 주제는 이미 '{topic}'로 정해져 있으므로, 반드시 {topic}에 대한 정보만 물어보세요. 다른 주제는 절대 묻지 마세요."),
                HumanMessage(content=integrated_prompt)
            ]

            # 통합 응답 스트리밍
            integrated_response = ""
            async for chunk in self.llm.astream(messages):
                if hasattr(chunk, 'content') and chunk.content:
                    integrated_response += chunk.content
                    print(chunk.content, end="", flush=True)
                    yield {"type": "message", "content": chunk.content, "node": "integrated_chat"}

            # 간단한 정보 추가 (필요한 경우만)
            if integrated_response:
                final_response = integrated_response.strip()

                # 이미 수집된 정보가 있으면 간단히 표시
                if topic or constraints or goal:
                    simple_info = "\n\n📝 **현재까지:**"
                    if topic:
                        simple_info += f" 주제({topic})"
                    if constraints:
                        simple_info += f" 수준 파악됨"
                    if goal:
                        simple_info += f" 목표({goal})"

                    final_response += simple_info

                # 대화 기록에 추가
                self.conversation_history.append({
                    "role": "assistant",
                    "content": final_response
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
            # 제약조건은 수준만 있어도 완료로 간주 (시간 정보는 선택사항)
            constraints_complete = bool(constraints and any(kw in constraints for kw in ["초보", "중급", "고급", "수준", "경험", "처음", "입문", "기초"]))
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
        # 기본 인사말로 재설정
        self.conversation_history = [
            {
                "role": "assistant",
                "content": "안녕하세요! LearnAI 입니다. 어떤 주제에 대해 배우고 싶으신지 알려주시면 맞춤형 학습 계획을 함께 만들어보겠습니다!"
            }
        ]
        # 세션 ID는 main.py에서 설정하므로 여기서는 초기화하지 않음
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
