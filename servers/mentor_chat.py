"""
Mentor Chat MCP Server - 전문가 멘토링 상담 시스템
- LangGraph 기반 2단계 워크플로우 (페르소나 추천 → 전문가 멘토링)
- 10개 전문 분야 페르소나 지원
- 세션 기반 상태 관리
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
MENTOR_SESSIONS_DIR = os.path.join(SESSIONS_DIR, "mentor")

def ensure_mentor_sessions_dir():
    """멘토 세션 폴더가 없으면 생성"""
    if not os.path.exists(MENTOR_SESSIONS_DIR):
        os.makedirs(MENTOR_SESSIONS_DIR)

def get_mentor_session_file_path(session_id):
    """멘토 세션 ID에 따른 파일 경로 반환"""
    ensure_mentor_sessions_dir()
    return os.path.join(MENTOR_SESSIONS_DIR, f"mentor_{session_id}.json")

def load_mentor_session(session_id):
    """특정 멘토 세션 데이터를 파일에서 로드"""
    try:
        session_file = get_mentor_session_file_path(session_id)
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    except Exception as e:
        logger.error(f"멘토 세션 {session_id} 로드 오류: {e}")
        return None

def save_mentor_session(session_id, session_data):
    """특정 멘토 세션 데이터를 파일에 저장"""
    try:
        session_file = get_mentor_session_file_path(session_id)
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"멘토 세션 {session_id} 저장 오류: {e}")

# 전문 분야 페르소나 정의
PERSONAS = {
    "architecture": {
        "name": "건축",
        "expertise": "건축 설계, 건축 구조, 건축 환경, BIM, 인테리어 디자인, 도시건축",
        "system_prompt": """당신은 20년 경력의 건축 전문가입니다. 
건축 설계, 구조 설계, 건축 환경, BIM, 인테리어 디자인 등 건축 분야 전반에 대한 깊은 지식을 가지고 있습니다.
실무 경험을 바탕으로 학생들과 신입 건축가들에게 실용적이고 구체적인 조언을 제공합니다.
복잡한 개념을 쉽게 설명하고, 실제 프로젝트 사례를 들어 설명하는 것을 좋아합니다."""
    },
    "civil_urban": {
        "name": "토목 도시",
        "expertise": "토목공학, 도시계획, 도시설계, 지반공학, 구조역학, 교통공학",
        "system_prompt": """당신은 토목공학과 도시계획 분야의 전문가입니다.
지반공학, 구조역학, 교통공학, 도시계획 및 설계 등에 대한 전문 지식을 보유하고 있습니다.
도시 인프라 구축과 관련된 실무 경험이 풍부하며, 지속가능한 도시 발전에 대한 통찰력을 가지고 있습니다.
이론과 실무를 연결하여 설명하며, 현실적인 문제 해결 방안을 제시합니다."""
    },
    "transport": {
        "name": "교통 운송",
        "expertise": "교통시스템, 물류관리, 교통정책, 스마트 모빌리티, 운송경제학",
        "system_prompt": """당신은 교통 및 운송 시스템 전문가입니다.
교통 시스템 설계, 물류 관리, 교통 정책, 스마트 모빌리티 등에 대한 전문성을 가지고 있습니다.
미래 교통 기술과 정책 동향에 대한 깊은 이해를 바탕으로, 효율적이고 지속가능한 교통 솔루션을 제안합니다.
데이터 기반의 분석과 정책적 관점에서 조언을 제공합니다."""
    },
    "mechanical": {
        "name": "기계 금속",
        "expertise": "기계설계, 재료공학, 생산공학, 자동화, 열역학, 유체역학",
        "system_prompt": """당신은 기계공학과 금속재료 분야의 전문가입니다.
기계 설계, 재료 공학, 생산 공학, 자동화 시스템 등에 대한 폭넓은 지식을 보유하고 있습니다.
제조업 현장에서의 실무 경험을 바탕으로, 이론과 실제 적용 사례를 연결하여 설명합니다.
혁신적인 기계 기술과 미래 제조업 트렌드에 대한 통찰력을 제공합니다."""
    },
    "electrical": {
        "name": "전기 전자",
        "expertise": "전기공학, 전자회로, 제어시스템, 전력시스템, 신호처리, 임베디드",
        "system_prompt": """당신은 전기전자공학 분야의 전문가입니다.
전기 회로, 전자 회로, 제어 시스템, 전력 시스템, 신호 처리 등에 대한 깊은 지식을 가지고 있습니다.
최신 전자 기술 동향과 실무 적용 경험을 바탕으로, 복잡한 개념을 체계적으로 설명합니다.
이론적 기반과 실용적 접근 방법을 균형있게 제시합니다."""
    },
    "precision_energy": {
        "name": "정밀 에너지",
        "expertise": "정밀기기, 측정공학, 에너지시스템, 신재생에너지, 에너지효율",
        "system_prompt": """당신은 정밀 기기 및 에너지 시스템 전문가입니다.
정밀 측정, 에너지 시스템 설계, 신재생 에너지, 에너지 효율 등에 대한 전문 지식을 보유하고 있습니다.
지속가능한 에너지 솔루션과 정밀 기술의 융합에 대한 깊은 이해를 가지고 있습니다.
기술적 정확성과 환경적 고려사항을 모두 반영한 조언을 제공합니다."""
    },
    "materials": {
        "name": "소재 재료",
        "expertise": "신소재, 나노기술, 재료과학, 고분자, 세라믹, 금속재료",
        "system_prompt": """당신은 소재 및 재료과학 분야의 전문가입니다.
신소재 개발, 나노 기술, 고분자, 세라믹, 금속 재료 등에 대한 전문성을 가지고 있습니다.
미래 소재 기술과 산업 응용에 대한 깊은 통찰력을 보유하고 있습니다.
기초 과학과 산업 응용을 연결하여, 실용적이면서도 혁신적인 접근 방법을 제시합니다."""
    },
    "computer": {
        "name": "컴퓨터 통신",
        "expertise": "소프트웨어공학, 네트워크, 데이터베이스, AI/ML, 사이버보안, 클라우드",
        "system_prompt": """당신은 컴퓨터공학과 통신 분야의 전문가입니다.
소프트웨어 개발, 네트워크 시스템, 데이터베이스, 인공지능, 사이버보안 등에 대한 깊은 지식을 가지고 있습니다.
최신 기술 트렌드와 산업 동향을 잘 파악하고 있으며, 실무 중심의 조언을 제공합니다.
이론적 배경과 실제 구현 경험을 바탕으로, 체계적이고 실용적인 가이드를 제시합니다."""
    },
    "industrial": {
        "name": "산업",
        "expertise": "산업공학, 품질관리, 생산관리, 공급망관리, 린제조, 6시그마",
        "system_prompt": """당신은 산업공학 및 생산관리 전문가입니다.
생산 시스템 최적화, 품질 관리, 공급망 관리, 린 제조, 6시그마 등에 대한 전문 지식을 보유하고 있습니다.
기업의 운영 효율성 향상과 경쟁력 강화에 대한 실무 경험이 풍부합니다.
데이터 분석과 시스템적 사고를 바탕으로, 실질적인 개선 방안을 제안합니다."""
    },
    "chemical": {
        "name": "화공",
        "expertise": "화학공학, 공정설계, 반응공학, 분리공정, 화학플랜트, 안전공학",
        "system_prompt": """당신은 화학공학 분야의 전문가입니다.
화학 공정 설계, 반응 공학, 분리 공정, 화학 플랜트 운영 등에 대한 깊은 지식을 가지고 있습니다.
산업 현장에서의 안전과 효율성을 중시하며, 환경 친화적인 공정 설계에 대한 전문성을 보유하고 있습니다.
이론과 실무를 균형있게 접근하여, 안전하고 효율적인 솔루션을 제시합니다."""
    }
}

# 상태 스키마 정의
class MentorState(TypedDict):
    messages: List[Dict[str, str]]
    phase: str  # "persona_recommendation" | "mentoring"
    recommended_personas: List[Dict[str, str]]  # 추천된 페르소나 정보
    selected_persona: str  # 선택된 페르소나 ID
    persona_context: str  # 페르소나 전문 지식 컨텍스트
    session_id: str
    completed: bool

# 스키마 모델들
class PersonaRecommendation(BaseModel):
    recommended_personas: List[Dict[str, str]] = Field(description="추천된 페르소나 목록")
    reasoning: str = Field(description="추천 이유")

class SelectionResult(BaseModel):
    selected_persona: str = Field(description="선택된 페르소나 ID")
    persona_name: str = Field(description="선택된 페르소나 이름")
    message: str = Field(description="멘토 인사말")

class MentoringResponse(BaseModel):
    response: str = Field(description="전문가 멘토링 응답")
    persona_name: str = Field(description="응답한 페르소나 이름")

# LLM 설정
llm = ChatOpenAI(
    base_url=Config.LLM_BASE_URL,
    api_key=Config.LLM_API_KEY,
    model=Config.LLM_MODEL,
    temperature=0.7,
    max_tokens=2000,
)

# MCP 서버 생성
mcp = FastMCP("MentorChat")

@mcp.tool()
async def analyze_and_recommend_personas(message: str, session_id: str) -> PersonaRecommendation:
    """사용자 메시지를 분석하여 적절한 페르소나 추천"""
    
    # 세션 데이터 로드 또는 초기화
    session_data = load_mentor_session(session_id)
    if not session_data:
        session_data = {
            "session_id": session_id,
            "phase": "persona_recommendation",
            "messages": [],
            "recommended_personas": [],
            "selected_persona": "",
            "persona_context": "",
            "completed": False
        }
    
    # 메시지 추가
    session_data["messages"].append({"role": "user", "content": message})
    
    # 페르소나 추천을 위한 프롬프트 생성
    analysis_prompt = f"""
사용자의 메시지를 분석하여 가장 적합한 전문가 페르소나를 추천해주세요.

사용자 메시지: "{message}"

사용 가능한 페르소나들:
{json.dumps({k: v["name"] + " - " + v["expertise"] for k, v in PERSONAS.items()}, ensure_ascii=False, indent=2)}

요구사항:
1. 사용자의 관심사, 질문 내용, 학습 목표를 분석
2. 1-3개의 가장 적합한 페르소나를 추천
3. 각 추천에 대한 구체적인 이유 제시

**중요: 정확히 아래 JSON 형식으로만 응답하세요. 다른 텍스트는 포함하지 마세요.**

{{
    "recommended_personas": [
        {{"id": "persona_id", "name": "페르소나명", "reason": "추천 이유"}},
        ...
    ],
    "reasoning": "전체적인 분석 및 추천 근거"
}}
"""
    
    try:
        response = await llm.ainvoke(analysis_prompt)
        logger.info(f"LLM 응답: {response.content}")  # 디버깅용 로그
        
        # JSON 응답 정리
        clean_content = response.content.strip()
        # 잘못된 키 수정
        clean_content = clean_content.replace('"recommended_ personas"', '"recommended_personas"')
        clean_content = clean_content.replace('" reasoning"', '"reasoning"')
        # 배열에서 ... 제거
        clean_content = clean_content.replace(', ...', '').replace('... ', '').replace('...', '')
        # 빈 객체 제거
        clean_content = clean_content.replace(', {}', '').replace('{},', '').replace('{}', '')
        
        result = json.loads(clean_content)
        logger.info(f"파싱된 결과: {result}")  # 디버깅용 로그
        
        # 키 존재 여부 확인 및 안전한 추출
        recommended_personas = result.get("recommended_personas", [])
        reasoning = result.get("reasoning", "추천 이유를 찾을 수 없습니다.")
        
        # 빈 리스트인 경우 기본값 설정
        if not recommended_personas:
            # 메시지 내용으로부터 간단한 추천 로직
            message_lower = message.lower()
            if any(word in message_lower for word in ["건축", "설계", "건물"]):
                recommended_personas = [{"id": "architecture", "name": "건축", "reason": "건축 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["전기", "전자", "회로"]):
                recommended_personas = [{"id": "electrical", "name": "전기 전자", "reason": "전기전자 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["화공", "화학", "공정"]):
                recommended_personas = [{"id": "chemical", "name": "화공", "reason": "화학공학 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["기계", "설계", "제조"]):
                recommended_personas = [{"id": "mechanical", "name": "기계 금속", "reason": "기계공학 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["토목", "도시", "건설"]):
                recommended_personas = [{"id": "civil_urban", "name": "토목 도시", "reason": "토목/도시 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["컴퓨터", "프로그래밍", "웹", "소프트웨어"]):
                recommended_personas = [{"id": "computer", "name": "컴퓨터 통신", "reason": "컴퓨터 관련 키워드 감지"}]
            else:
                recommended_personas = [{"id": "computer", "name": "컴퓨터 통신", "reason": "기본 추천"}]
        
        # 세션에 추천 결과 저장
        session_data["recommended_personas"] = recommended_personas
        session_data["messages"].append({
            "role": "assistant", 
            "content": f"분석 결과를 바탕으로 다음 전문가들을 추천드립니다:\n\n{reasoning}"
        })
        
        save_mentor_session(session_id, session_data)
        
        return PersonaRecommendation(
            recommended_personas=recommended_personas,
            reasoning=reasoning
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}, 응답 내용: {response.content if 'response' in locals() else 'N/A'}")
        # 기본 키워드 기반 추천으로 폴백
        message_lower = message.lower()
        if any(word in message_lower for word in ["건축", "설계", "건물"]):
            fallback_personas = [{"id": "architecture", "name": "건축", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["전기", "전자", "회로"]):
            fallback_personas = [{"id": "electrical", "name": "전기 전자", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["화공", "화학", "공정"]):
            fallback_personas = [{"id": "chemical", "name": "화공", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["기계", "설계", "제조"]):
            fallback_personas = [{"id": "mechanical", "name": "기계 금속", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["토목", "도시", "건설"]):
            fallback_personas = [{"id": "civil_urban", "name": "토목 도시", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["컴퓨터", "프로그래밍", "웹", "소프트웨어"]):
            fallback_personas = [{"id": "computer", "name": "컴퓨터 통신", "reason": "키워드 기반 추천"}]
        else:
            fallback_personas = [{"id": "computer", "name": "컴퓨터 통신", "reason": "기본 추천"}]
            
        session_data["recommended_personas"] = fallback_personas
        save_mentor_session(session_id, session_data)
        
        return PersonaRecommendation(
            recommended_personas=fallback_personas,
            reasoning="JSON 파싱 오류로 키워드 기반 추천을 제공합니다."
        )
        
    except Exception as e:
        logger.error(f"페르소나 추천 오류: {e}")
        # 기본 추천
        default_personas = [
            {"id": "computer", "name": "컴퓨터 통신", "reason": "일반적으로 많이 문의되는 분야입니다."}
        ]
        session_data["recommended_personas"] = default_personas
        save_mentor_session(session_id, session_data)
        
        return PersonaRecommendation(
            recommended_personas=default_personas,
            reasoning="분석 중 오류가 발생하여 기본 추천을 제공합니다."
        )

@mcp.tool()
async def select_persona(persona_id: str, session_id: str) -> SelectionResult:
    """사용자가 선택한 페르소나로 멘토링 모드 전환"""
    
    # 세션 데이터 로드
    session_data = load_mentor_session(session_id)
    if not session_data:
        raise ValueError("세션 데이터를 찾을 수 없습니다.")
    
    # 페르소나 유효성 검사
    if persona_id not in PERSONAS:
        raise ValueError(f"유효하지 않은 페르소나 ID: {persona_id}")
    
    # 선택된 페르소나 정보
    persona = PERSONAS[persona_id]
    
    # 세션 업데이트
    session_data["selected_persona"] = persona_id
    session_data["phase"] = "mentoring"
    session_data["persona_context"] = persona["system_prompt"]
    
    # 멘토 인사말
    greeting = f"""안녕하세요! 저는 {persona['name']} 분야의 전문가입니다.

전문 분야: {persona['expertise']}

무엇이든 궁금한 것이 있으시면 편하게 물어보세요. 
실무 경험과 전문 지식을 바탕으로 최선을 다해 도움을 드리겠습니다."""
    
    session_data["messages"].append({
        "role": "assistant",
        "content": greeting
    })
    
    save_mentor_session(session_id, session_data)
    
    return SelectionResult(
        selected_persona=persona_id,
        persona_name=persona["name"],
        message=greeting
    )

@mcp.tool()
async def expert_mentoring(message: str, session_id: str) -> MentoringResponse:
    """선택된 페르소나로 전문가 멘토링 제공"""
    
    # 세션 데이터 로드
    session_data = load_mentor_session(session_id)
    if not session_data or session_data.get("phase") != "mentoring":
        raise ValueError("멘토링 모드가 활성화되지 않았습니다. 먼저 페르소나를 선택해주세요.")
    
    selected_persona_id = session_data.get("selected_persona")
    if not selected_persona_id or selected_persona_id not in PERSONAS:
        raise ValueError("유효한 페르소나가 선택되지 않았습니다.")
    
    persona = PERSONAS[selected_persona_id]
    
    # 사용자 메시지 추가
    session_data["messages"].append({"role": "user", "content": message})
    
    # 대화 기록 생성 (최근 10개 메시지만)
    recent_messages = session_data["messages"][-10:]
    conversation_history = ""
    for msg in recent_messages[:-1]:  # 현재 메시지 제외
        role = "사용자" if msg["role"] == "user" else "멘토"
        conversation_history += f"{role}: {msg['content']}\n"
    
    # 멘토링 프롬프트 생성
    mentoring_prompt = f"""
{persona['system_prompt']}

대화 기록:
{conversation_history}

현재 사용자 질문: {message}

위의 역할에 맞게, 전문가로서 다음 사항을 고려하여 답변해주세요:
1. 전문 지식을 바탕으로 한 정확한 정보 제공
2. 실무 경험에서 나온 실용적인 조언
3. 단계별, 구체적인 가이드 제시
4. 관련 학습 자료나 다음 단계 제안
5. 친근하고 격려하는 멘토의 톤 유지

답변은 한국어로, 구체적이고 도움이 되도록 작성해주세요.
"""
    
    try:
        response = await llm.ainvoke(mentoring_prompt)
        mentor_response = response.content
        
        # 응답을 세션에 저장
        session_data["messages"].append({
            "role": "assistant",
            "content": mentor_response
        })
        
        save_mentor_session(session_id, session_data)
        
        return MentoringResponse(
            response=mentor_response,
            persona_name=persona["name"]
        )
        
    except Exception as e:
        logger.error(f"멘토링 응답 생성 오류: {e}")
        error_response = f"죄송합니다. 응답 생성 중 오류가 발생했습니다. 다시 질문해주시면 더 나은 답변을 드리도록 하겠습니다."
        
        session_data["messages"].append({
            "role": "assistant",
            "content": error_response
        })
        save_mentor_session(session_id, session_data)
        
        return MentoringResponse(
            response=error_response,
            persona_name=persona["name"]
        )

@mcp.tool()
async def get_mentor_session_status(session_id: str) -> dict:
    """멘토 세션 상태 조회"""
    session_data = load_mentor_session(session_id)
    if not session_data:
        return {"status": "not_found", "message": "세션을 찾을 수 없습니다."}
    
    status_info = {
        "status": "active",
        "phase": session_data.get("phase", "persona_recommendation"),
        "selected_persona": session_data.get("selected_persona", ""),
        "message_count": len(session_data.get("messages", [])),
        "recommended_personas": session_data.get("recommended_personas", [])
    }
    
    if status_info["selected_persona"]:
        persona = PERSONAS.get(status_info["selected_persona"], {})
        status_info["persona_name"] = persona.get("name", "")
        status_info["persona_expertise"] = persona.get("expertise", "")
    
    return status_info

if __name__ == "__main__":
    mcp.run()