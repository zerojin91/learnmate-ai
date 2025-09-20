"""
Stateful MCP Server with LangGraph Multi-Agent Workflow
- 세션 기반 상태 관리
- LangGraph Command 객체를 통한 Agent Handoff
- topic, constraints, goal 완성까지 지속적인 대화
"""

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import TypedDict, List, Dict, Optional
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
import json
import logging
from datetime import datetime
import uuid
import os
import sys

# 상위 디렉토리의 config 모듈 import
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from utils import random_uuid

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 세션 저장 폴더 경로
SESSIONS_DIR = "sessions"

def ensure_sessions_dir():
    """세션 폴더가 없으면 생성"""
    if not os.path.exists(SESSIONS_DIR):
        os.makedirs(SESSIONS_DIR)

def get_session_file_path(session_id):
    """세션 ID에 따른 파일 경로 반환"""
    ensure_sessions_dir()
    return os.path.join(SESSIONS_DIR, f"{session_id}.json")

def load_session(session_id):
    """특정 세션 데이터를 파일에서 로드"""
    try:
        session_file = get_session_file_path(session_id)
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"세션 {session_id} 로드 오류: {e}")
        return None

def save_session(session_id, session_data):
    """특정 세션 데이터를 파일에 저장"""
    try:
        session_file = get_session_file_path(session_id)
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"세션 {session_id} 저장 오류: {e}")

def load_sessions():
    """모든 세션 데이터를 로드 (호환성을 위해 유지)"""
    ensure_sessions_dir()
    sessions = {}
    try:
        for filename in os.listdir(SESSIONS_DIR):
            if filename.endswith('.json'):
                session_id = filename[:-5]  # .json 제거
                session_data = load_session(session_id)
                if session_data:
                    sessions[session_id] = session_data
    except Exception as e:
        logger.error(f"전체 세션 로드 오류: {e}")
    return sessions

def save_sessions(sessions):
    """모든 세션 데이터를 개별 파일로 저장"""
    for session_id, session_data in sessions.items():
        save_session(session_id, session_data)

# 세션 저장소 초기화
SESSIONS = load_sessions()

# 상태 스키마 정의
class AssessmentState(TypedDict):
    messages: List[Dict[str, str]]
    topic: str
    constraints: str
    goal: str
    current_agent: str
    session_id: str
    completed: bool

class UserInfoSchema(BaseModel):
    topic: str = Field(default="", description="사용자가 직접 언급한 학습 주제만. 예: '파이썬', '영어'. 추론하지 말고 정확한 단어만")
    constraints: str = Field(default="", description="사용자가 명시적으로 말한 제약조건만. 예: '초보자', '주 3시간'. 없으면 빈 문자열")
    goal: str = Field(default="", description="사용자가 직접 언급한 목표만. 예: '취업', '자격증'. 추측하지 말고 명시된 것만")

class CompletionSchema(BaseModel):
    topic_complete: bool = Field(description="학습 주제가 명확히 파악되었는가")
    constraints_complete: bool = Field(description="수준과 시간 투자 정도가 모두 파악되었는가")
    goal_complete: bool = Field(description="구체적인 학습 목표나 목적이 파악되었는가")
    missing_info: str = Field(description="부족한 정보가 있다면 무엇인지 설명")

# LLM 초기화 - config에서 설정값 가져오기
llm = ChatOpenAI(
    base_url=Config.LLM_BASE_URL,
    api_key=Config.LLM_API_KEY,
    model=Config.LLM_MODEL,
    temperature=Config.LLM_TEMPERATURE,
    max_tokens=Config.LLM_MAX_TOKENS,
    model_kwargs={"max_completion_tokens": None}  # Friendli.ai에서 지원하지 않는 파라미터 제거
)

class AssessmentAgentSystem:
    """Stateful Assessment Agent System"""
    
    def __init__(self):
        self.workflow = self._create_workflow()
    
    def _create_workflow(self):
        """Multi-Agent 워크플로우 생성"""
        workflow = StateGraph(AssessmentState)
        
        # 에이전트 노드 추가
        workflow.add_node("extraction_agent", self._extraction_agent) 
        workflow.add_node("response_agent", self._response_agent)
        
        # 단순화된 워크플로우: 추출 -> 응답 -> 종료
        workflow.add_edge(START, "extraction_agent")
        
        workflow.add_conditional_edges(
            "extraction_agent",
            self._should_continue,
            {
                "complete": "response_agent",
                "continue": "response_agent"
            }
        )
        
        workflow.add_edge("response_agent", END)
        
        return workflow.compile()
    
    def _response_agent(self, state: AssessmentState) -> Command:
        """응답 생성 담당 에이전트"""
        logger.info(f"💬 Response Agent 실행 - Session: {state.get('session_id')}")

        # LLM 완성도 판단
        completion_result = self._is_profile_complete(state)

        if (completion_result.topic_complete and
            completion_result.constraints_complete and
            completion_result.goal_complete):
            # 완료된 경우 - 완료 메시지
            response = self._generate_completion_message(state)
            completed = True
        else:
            # 미완료된 경우 - LLM 판단 결과를 활용한 다음 질문
            response = self._generate_next_question_with_llm_result(state, completion_result)
            completed = False

        # 메시지 업데이트
        updated_messages = state.get("messages", []).copy()
        updated_messages.append({"role": "assistant", "content": response})

        return Command(
            update={
                "messages": updated_messages,
                "completed": completed,
                "current_agent": "response"
            }
        )
    
    def _extraction_agent(self, state: AssessmentState) -> Command:
        """정보 추출 담당 에이전트"""
        logger.info(f"🔍 Extraction Agent 실행 - Session: {state.get('session_id')}")
        
        if not state.get("messages"):
            return Command(update={"current_agent": "extraction"})
        
        # 최신 대화에서 정보 추출
        messages_text = self._format_conversation(state["messages"])
        
        try:
            # 구조화된 정보 추출 - 매우 엄격한 기준
            extraction_prompt = f"""
다음 대화에서 학습 관련 정보를 추출하세요. 극도로 엄격하게 추출하세요:

{messages_text}

현재 상태:
- 주제: {state.get('topic', '미파악')}
- 제약조건: {state.get('constraints', '미파악')}  
- 목표: {state.get('goal', '미파악')}

## 학습 주제 추출 규칙:
1. **사용자가 직접 언급한 주제나 분야명** 추출
2. **축약된 표현도 인식**: "전지지식", "영어", "파이썬" 등
3. **학습 의도가 있는 명사/구문** 우선 추출
4. **없으면 빈 문자열("")로 두세요**
5. **기존 정보가 있으면 덮어쓰지 말고 유지하세요**

**중요**: 다음과 같은 축약/생략 표현에서도 주제를 반드시 추출하세요:
- "나 전지지식" → topic: "전지지식"
- "파이썬" → topic: "파이썬"  
- "영어" → topic: "영어"
- "데이터 분석" → topic: "데이터 분석"

정확한 추출 예시:
- "파이썬 배우고 싶어" → topic: "파이썬", constraints: "", goal: ""
- "나 전지지식" → topic: "전지지식", constraints: "", goal: ""
- "영어 공부하고 싶어" → topic: "영어", constraints: "", goal: ""
- "나 완전 초보야" → constraints: "완전 초보"
- "주 3시간만 할 수 있어" → constraints: "주 3시간"  
- "취업하려고" → goal: "취업"
- "웹 개발 배우고 싶어" → topic: "웹 개발"

**핵심**: 학습과 관련된 모든 명사는 주제로 추출하세요!
"""
            
            model_with_structure = llm.with_structured_output(UserInfoSchema)
            extracted = model_with_structure.invoke(extraction_prompt)
            
            # 기존 정보와 병합 - 기존 정보 우선, 새로운 명시적 정보만 추가
            current_topic = state.get("topic", "")
            current_constraints = state.get("constraints", "")
            current_goal = state.get("goal", "")
            
            # 새로운 정보가 있을 때만 업데이트 (빈 문자열이 아닌 경우)
            updated_topic = extracted.topic.strip() if extracted.topic.strip() else current_topic
            updated_constraints = extracted.constraints.strip() if extracted.constraints.strip() else current_constraints
            updated_goal = extracted.goal.strip() if extracted.goal.strip() else current_goal
            
            logger.info(f"추출된 정보 - Topic: {updated_topic}, Constraints: {updated_constraints}, Goal: {updated_goal}")
            
            return Command(
                update={
                    "topic": updated_topic,
                    "constraints": updated_constraints, 
                    "goal": updated_goal,
                    "current_agent": "extraction"
                }
            )
            
        except Exception as e:
            logger.error(f"정보 추출 오류: {e}")
            return Command(update={"current_agent": "extraction"})
    
    def _generate_completion_message(self, state: AssessmentState) -> str:
        """완료 메시지 생성"""
        return f"""
🎯 **학습 프로필 분석 완료!**

**📚 학습 주제**: {state.get('topic', '')}
**⚠️ 제약 조건**: {state.get('constraints', '')}
**🚀 구체적 목표**: {state.get('goal', '')}

완벽한 정보를 수집했습니다! 이제 맞춤형 학습 계획을 수립할 준비가 되었어요.
        """.strip()
    
    def _is_profile_complete(self, state: AssessmentState) -> CompletionSchema:
        """LLM을 사용하여 프로필 완성도를 지능적으로 판단"""

        current_info = f"""
현재 수집된 정보:
- 주제: "{state.get('topic', '')}"
- 제약조건: "{state.get('constraints', '')}"
- 목표: "{state.get('goal', '')}"

대화 기록:
{self._format_conversation(state.get('messages', []))}
"""

        completion_prompt = f"""
다음 학습 프로필 정보가 완성되었는지 판단해주세요:

{current_info}

판단 기준:
1. **주제 완성**: 구체적인 학습 분야가 명확한가? (예: "파이썬", "영어", "데이터분석")
2. **제약조건 완성**: 현재 수준 AND 시간 투자 정도가 모두 파악되었는가?
   - 수준: "초보자", "중급자" 등
   - 시간: "주 3시간", "매일 1시간" 등
3. **목표 완성**: 구체적인 학습 목적이 명확한가? (예: "취업", "업무활용", "자격증")

각 항목별로 완성 여부를 정확히 판단하고, 부족한 정보가 있다면 구체적으로 명시해주세요.
"""

        try:
            model_with_structure = llm.with_structured_output(CompletionSchema)
            return model_with_structure.invoke(completion_prompt)
        except Exception as e:
            logger.error(f"LLM 완성도 판단 오류: {e}")
            # 오류 시 기존 방식으로 폴백
            return CompletionSchema(
                topic_complete=bool(state.get("topic")),
                constraints_complete=bool(state.get("constraints")),
                goal_complete=bool(state.get("goal")),
                missing_info="완성도 판단 중 오류 발생"
            )

    def _should_continue(self, state: AssessmentState) -> str:
        """LLM 기반 완성도 판단"""

        # LLM으로 완성도 판단
        completion_result = self._is_profile_complete(state)

        logger.info(f"LLM 완성도 판단 - Topic: {completion_result.topic_complete}, "
                   f"Constraints: {completion_result.constraints_complete}, "
                   f"Goal: {completion_result.goal_complete}")

        if completion_result.missing_info:
            logger.info(f"부족한 정보: {completion_result.missing_info}")

        # 모든 항목이 완성되었으면 complete
        if (completion_result.topic_complete and
            completion_result.constraints_complete and
            completion_result.goal_complete):
            return "complete"
        else:
            return "continue"
    
    def _generate_next_question_with_llm_result(self, state: AssessmentState, completion_result: CompletionSchema) -> str:
        """LLM 완성도 판단 결과를 활용한 다음 질문 생성"""

        topic = state.get("topic", "")
        constraints = state.get("constraints", "")
        goal = state.get("goal", "")

        # 주제가 완성되지 않은 경우
        if not completion_result.topic_complete:
            return """
🎯 **어떤 분야를 학습하고 싶으신가요?**

구체적으로 말씀해주시면 더 정확한 계획을 세울 수 있어요:
- 프로그래밍 (Python, JavaScript 등)
- 언어 (영어, 중국어 등)
- 데이터 분석/AI
- 기타 분야

자세히 알려주세요!
            """.strip()

        # 제약조건이 완성되지 않은 경우
        elif not completion_result.constraints_complete:
            # missing_info를 활용하여 구체적인 질문 생성
            missing_info = completion_result.missing_info.lower()

            if "시간" in missing_info:
                return f"""
📚 **{topic} 학습 시간을 알려주세요!**

현재 수준은 파악했어요: {constraints}

**시간 투자**: 일주일에 몇 시간 정도 공부할 수 있으신가요?
- 매일 1-2시간
- 주 3-4시간
- 주말에만 집중적으로
- 기타 (구체적으로 알려주세요)

현실적인 학습 계획을 세우기 위해 필요해요!
                """.strip()
            elif "수준" in missing_info:
                return f"""
📚 **{topic} 학습 수준을 알려주세요!**

**현재 수준**: 완전 초보자이신가요, 아니면 어느 정도 아시나요?
- 완전 처음 시작
- 기초는 알고 있음
- 어느 정도 경험 있음
- 기타 (구체적으로 알려주세요)

정확한 수준을 알아야 맞춤형 계획을 세울 수 있어요!
                """.strip()
            else:
                # 일반적인 제약조건 질문
                return f"""
📚 **{topic} 학습 조건을 알려주세요!**

**현재 수준**: 완전 초보자이신가요, 아니면 어느 정도 아시나요?
**시간 투자**: 일주일에 몇 시간 정도 공부할 수 있으신가요?

이런 정보가 있어야 현실적인 학습 계획을 세울 수 있어요!
                """.strip()

        # 목표가 완성되지 않은 경우
        elif not completion_result.goal_complete:
            return f"""
🚀 **{topic} 학습 목표를 알려주세요!**

어떤 목적으로 {topic}을(를) 배우시나요?
- 취업이나 이직을 위해서
- 현재 업무에 활용하려고
- 개인 프로젝트를 만들고 싶어서
- 취미나 자기계발로

구체적인 목표를 알면 더 맞춤형 로드맵을 제시할 수 있어요!
            """.strip()

        return "모든 정보가 수집되었습니다!"
    
    def _format_conversation(self, messages: List[Dict]) -> str:
        """대화 기록을 텍스트로 변환"""
        formatted = []
        for msg in messages[-10:]:  # 최근 10개 메시지만
            role = "사용자" if msg.get("role") == "user" else "AI"
            content = msg.get("content", "")
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

# Assessment Agent 시스템 인스턴스
assessment_system = AssessmentAgentSystem()

mcp = FastMCP(
    "UserAssessment",
    instructions="""이 서버는 Stateful Multi-Agent Assessment를 수행합니다.
    user_profiling 도구를 호출하면 세션 기반으로 사용자와 지속적인 대화를 진행하며,
    topic, constraints, goal을 모두 수집할 때까지 계속됩니다.
    
    각 호출마다 session_id를 포함하여 상태를 유지하세요.""",
    host=Config.MCP_SERVER_HOST,
    port=Config.MCP_SERVER_PORT,
)

@mcp.tool()
async def user_profiling(user_message: str, session_id: str = None) -> str:
    """
    Stateful Multi-Agent 사용자 프로필링을 수행합니다.
    
    LangGraph 기반의 Multi-Agent 시스템이 다음 에이전트들을 조율합니다:
    - Conversation Agent: 사용자와의 대화 담당
    - Extraction Agent: 정보 추출 담당  
    - Completion Agent: 완료 처리 담당
    
    Args:
        user_message: 사용자 메시지
        session_id: 세션 ID (없으면 새로 생성)
        
    Returns:
        str: 다음 질문 또는 완료 메시지 + 세션 정보
    """
    
    logger.info(f"=== user_profiling 호출됨 ===")
    logger.info(f"메시지: {user_message}")
    logger.info(f"세션 ID: {session_id}")
    logger.info(f"현재 SESSIONS 키들: {list(SESSIONS.keys())}")
    
    # 세션 ID가 없으면 오류 (main.py에서 항상 생성되어야 함)
    if not session_id:
        return "오류: 세션 ID가 제공되지 않았습니다. 페이지를 새로고침해주세요."
    
    # 기존 세션 상태 가져오기 또는 새로 생성
    current_state = load_session(session_id)
    if current_state:
        logger.info(f"기존 세션 복원: {session_id}")
        logger.info(f"기존 상태 - Topic: {current_state.get('topic')}, Constraints: {current_state.get('constraints')}, Goal: {current_state.get('goal')}")
    else:
        current_state = {
            "messages": [],
            "topic": "",
            "constraints": "",
            "goal": "",
            "current_agent": "response",
            "session_id": session_id,
            "completed": False
        }
        save_session(session_id, current_state)  # 개별 파일에 저장
        logger.info(f"새 세션 초기화: {session_id}")
    
    # 사용자 메시지 추가
    current_state["messages"].append({"role": "user", "content": user_message})
    
    try:
        # Multi-Agent 워크플로우 실행
        logger.info(f"🤖 Multi-Agent 워크플로우 시작 - Session: {session_id}")
        
        result = assessment_system.workflow.invoke(current_state)
        
        # 세션 상태 업데이트
        SESSIONS[session_id] = result
        save_sessions(SESSIONS)  # 파일에 저장
        
        # 최신 AI 응답 가져오기
        if result.get("messages"):
            latest_response = result["messages"][-1]
            if latest_response.get("role") == "assistant":
                response_content = latest_response.get("content", "")
                
                logger.info(f"응답 생성 완료 - Session: {session_id}")
                return response_content
        
        return f"처리 중 오류가 발생했습니다. (Session: {session_id})"
        
    except Exception as e:
        logger.error(f"워크플로우 실행 오류: {str(e)}")
        return f"오류가 발생했습니다: {str(e)} (Session: {session_id})"


if __name__ == "__main__":
    mcp.run(transport="stdio")
