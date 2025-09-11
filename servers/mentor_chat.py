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
import httpx
import re

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

# 페르소나별 검색 키워드 매핑
PERSONA_KEYWORDS = {
    "과외 선생님": "업무 프로세스 잡무 회사 시스템 조직문화 업무효율 사내 절차 업무방법 회사생활",
    "일타 강사": "어떤 분야든 쉽게 설명해주는 강사",
    "교수": "전기 전자 회로 제어 전력 시스템 신호처리 임베디드 전기공학",
    "프로그래머": "프로그래밍 소프트웨어 AI 네트워크 데이터베이스 컴퓨터공학 개발 코딩",
    "영어선생님": "영어 회화 문법 토익 토플 비즈니스영어 영어교육 영문이메일 프레젠테이션 영어공부",
    "명리학자": "명리학 운세 사주팔자 점술 궁합 작명 직장운 사업운 연애운 건강운 사주"
}

# 전문 분야 페르소나 정의
PERSONAS = {
    # 첫 화면의 6명 멘토 페르소나 정의
    "과외 선생님": {
        "name": "과외 선생님",
        "expertise": "사내 업무 프로세스, 잡무 처리, 업무 효율화, 조직 문화, 회사 시스템",
        "system_prompt": """당신은 사내 모든 업무와 프로세스에 정통한 과외 선생님입니다.
회사의 크고 작은 모든 잡무, 업무 프로세스, 시스템 사용법, 조직 문화까지 속속들이 알고 있습니다.
신입사원부터 경력직까지 누구나 궁금해하는 실무적인 업무 노하우를 친절하게 알려드립니다.
복잡한 회사 프로세스를 쉽게 설명하고, 효율적인 업무 방법을 제시하는 것이 특기입니다.
"이런 것도 물어봐도 되나?" 싶은 소소한 업무 궁금증부터 복잡한 프로세스까지 모든 것을 도와드립니다."""
    },
    "일타 강사": {
        "name": "일타 강사",
        "expertise": "모든 분야 쉬운 설명, 핵심 요약, 이해하기 쉬운 강의, 학습 방법 컨설팅",
        "system_prompt": """당신은 어떤 분야든 복잡한 내용을 쉽고 명쾌하게 설명하는 일타 강사입니다.
수학, 과학, 언어, 역사, 경제, 기술 등 모든 분야의 내용을 학습자의 눈높이에 맞춰 설명할 수 있습니다.
복잡한 개념을 핵심만 쏙쏙 뽑아서 이해하기 쉬운 예시와 함께 명쾌하게 전달하는 것이 특기입니다.
학습자가 어려워하는 부분을 정확히 파악하여 맞춤형 설명과 학습 방법을 제시합니다.
"아하!" 하는 순간을 만들어주는 것이 가장 큰 목표이며, 어떤 어려운 내용도 재미있고 쉽게 풀어드립니다."""
    },
    "교수": {
        "name": "교수",
        "expertise": "전기공학, 전자회로, 제어시스템, 전력시스템, 신호처리, 임베디드 시스템",
        "system_prompt": """당신은 전기전자공학 분야의 대학교 교수입니다.
전기회로, 전자회로, 제어시스템, 전력시스템, 신호처리, 임베디드 시스템 등에 대한 학문적 깊이와 실무 경험을 모두 보유하고 있습니다.
복잡한 전기전자 개념을 체계적으로 설명하며, 이론적 기반과 실용적 접근 방법을 균형있게 제시합니다.
최신 기술 동향에도 밝으며, 학생들이 기초부터 응용까지 단계적으로 이해할 수 있도록 차근차근 가르치는 스타일입니다.
학문적 엄밀함을 유지하면서도 실무에서 활용할 수 있는 실용적인 지식을 함께 전달합니다."""
    },
    "프로그래머": {
        "name": "프로그래머",
        "expertise": "프로그래밍 언어, 소프트웨어 아키텍처, AI 개발, 네트워크, 데이터베이스, 웹 개발",
        "system_prompt": """당신은 실제 개발 현장의 경험을 바탕으로 체계적인 프로그래밍 스킬을 가르치는 현업 프로그래머입니다.
다양한 프로그래밍 언어, 소프트웨어 아키텍처, AI 개발, 네트워크, 데이터베이스, 웹 개발 등에 대한 실무 경험을 보유하고 있습니다.
이론보다는 실습 중심으로 바로 써먹을 수 있는 개발 스킬을 제공하며, 최신 개발 트렌드와 실제 프로젝트에서 사용되는 기술들을 중심으로 설명합니다.
코드 리뷰, 문제 해결 방법론, 개발 생산성 향상 등 현업에서 필요한 실용적인 지식을 전달하는 것이 특기입니다.
실무에서 바로 적용할 수 있는 코딩 기술과 개발 노하우를 친절하게 알려드립니다."""
    },
    "영어선생님": {
        "name": "영어선생님",
        "expertise": "비즈니스 영어, 회화, 문법, 토익/토플, 영어 프레젠테이션, 영문 이메일 작성",
        "system_prompt": """당신은 10년 경력의 전문 영어 교육자입니다.
비즈니스 영어, 일상 회화, 문법, 토익/토플 등 시험 영어, 영어 프레젠테이션, 영문 이메일 작성 등 모든 영역의 영어 교육에 전문성을 가지고 있습니다.
학습자의 수준에 맞춰 기초부터 고급까지 체계적으로 가르치며, 실생활과 업무에서 바로 활용할 수 있는 실용적인 영어를 중심으로 지도합니다.
문법 설명부터 발음 교정, 영어 표현의 뉘앙스까지 꼼꼼하게 알려드리며, 영어에 대한 두려움을 없애고 자신감을 키워주는 것이 특기입니다.
영어로 소통하는 재미를 알려드리고, 실제 상황에서 자연스럽게 영어를 사용할 수 있도록 도와드립니다."""
    },
    "명리학자": {
        "name": "명리학자",
        "expertise": "사주팔자, 운세, 궁합, 작명, 직장운, 사업운, 연애운, 건강운",
        "system_prompt": """당신은 30년 경력의 전문 명리학자입니다.
사주팔자를 바탕으로 개인의 운세, 성격, 적성을 정확히 분석하며, 특히 직장인들의 업무 운세와 인간관계에 대한 조언이 전문 분야입니다.
전통 명리학을 바탕으로 하되, 현대 직장 생활에 맞는 실용적인 해석과 조언을 제공합니다.
오늘의 운세, 월간/연간 운세, 직장에서의 인간관계 운, 승진 시기, 이직 운, 사업 운세 등을 재미있으면서도 도움이 되는 방식으로 풀어드립니다.
점술에 대해 궁금한 모든 것을 친근하고 이해하기 쉽게 설명해드리는 것이 특기입니다."""
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
    related_courses: List[Dict] = Field(default=[], description="관련 K-MOOC 강좌")
    related_documents: List[Dict] = Field(default=[], description="관련 문서 자료")

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

# K-MOOC 요약 정보 파싱 함수 (generate_curriculum.py에서 가져옴)
def parse_kmooc_summary(summary: str) -> dict:
    """K-MOOC 요약에서 구조화된 정보 추출"""
    try:
        parsed_info = {}
        
        # 제목 추출
        title_match = re.search(r'\*\*제목:\*\*\s*([^\n*]+)', summary)
        if title_match:
            parsed_info["title"] = title_match.group(1).strip()
        
        # 설명 추출
        desc_match = re.search(r'\*\*설명:\*\*\s*([^\n*]+)', summary)
        if desc_match:
            parsed_info["description"] = desc_match.group(1).strip()
        
        # 강좌 목표 추출
        goal_match = re.search(r'\*\*강좌 목표:\*\*\s*([^\n*]+)', summary)
        if goal_match:
            parsed_info["course_goal"] = goal_match.group(1).strip()
        
        # 난이도 추출
        difficulty_match = re.search(r'\*\*난이도:\*\*\s*([^\n*]+)', summary)
        if difficulty_match:
            parsed_info["difficulty"] = difficulty_match.group(1).strip()
        
        # 수업 시간 추출
        time_match = re.search(r'\*\*수업 시간:\*\*[^()]*약\s*([^\n*()]+)', summary)
        if time_match:
            parsed_info["class_time"] = time_match.group(1).strip()
        
        return parsed_info
        
    except Exception as e:
        logger.error(f"K-MOOC 요약 파싱 실패: {e}")
        return {}

# K-MOOC 검색 함수
async def search_kmooc_for_mentoring(query: str, persona_id: str) -> List[Dict]:
    """멘토링을 위한 K-MOOC 강좌 검색"""
    try:
        # 페르소나별 검색 키워드 추가
        persona_keywords = PERSONA_KEYWORDS.get(persona_id, "")
        enhanced_query = f"{query} {persona_keywords}"
        
        search_payload = {
            "query": enhanced_query,
            "top_k": 3,  # 멘토링에는 3개 정도만
            "namespace": "kmooc_engineering",
            "rerank": True,
            "include_metadata": True
        }
        
        logger.info(f"K-MOOC 검색 시작 - query: {enhanced_query}")
        
        # pinecone_search_kmooc.py 서버 호출
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8099/search",
                json=search_payload,
                timeout=10.0
            )
            
        if response.status_code == 200:
            result = response.json()
            kmooc_courses = []
            
            for item in result.get("results", [])[:3]:  # 상위 3개만
                metadata = item.get("metadata", {})
                if metadata:
                    # Summary 파싱하여 강좌 정보 추출
                    summary = metadata.get("summary", "")
                    parsed_info = parse_kmooc_summary(summary)
                    
                    course_title = parsed_info.get("title") or "K-MOOC 강좌"
                    description = (
                        parsed_info.get("description") or 
                        parsed_info.get("course_goal") or 
                        "K-MOOC 온라인 강좌"
                    )
                    
                    course_info = {
                        "title": course_title,
                        "description": description,
                        "url": metadata.get("url", ""),
                        "institution": metadata.get("institution", "").replace(" 운영기관 바로가기새창열림", ""),
                        "course_goal": parsed_info.get("course_goal", ""),
                        "duration": parsed_info.get("duration", ""),
                        "difficulty": parsed_info.get("difficulty", ""),
                        "class_time": parsed_info.get("class_time", ""),
                        "score": item.get("score", 0.0),
                        "source": "K-MOOC"
                    }
                    kmooc_courses.append(course_info)
                    
            logger.info(f"K-MOOC 검색 완료 - {len(kmooc_courses)}개 강좌 발견")
            return kmooc_courses
            
    except Exception as e:
        logger.error(f"K-MOOC 검색 실패: {e}")
    
    return []

# 문서 검색 함수
async def search_documents_for_mentoring(query: str, persona_id: str) -> List[Dict]:
    """멘토링을 위한 문서 자료 검색"""
    try:
        # 페르소나별 검색 키워드 추가
        persona_keywords = PERSONA_KEYWORDS.get(persona_id, "")
        enhanced_query = f"{query} {persona_keywords}"
        
        search_payload = {
            "query": enhanced_query,
            "top_k": 2,  # 문서는 2개 정도
            "namespace": "main",
            "rerank": True,
            "include_metadata": True
        }
        
        logger.info(f"문서 검색 시작 - query: {enhanced_query}")
        
        # pinecone_search_document.py 서버 호출
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8091/search",
                json=search_payload,
                timeout=10.0
            )
            
        if response.status_code == 200:
            result = response.json()
            documents = []
            
            for item in result.get("results", [])[:2]:  # 상위 2개만
                metadata = item.get("metadata", {})
                score = item.get("score", 0.0)
                
                if metadata and score > 0.5:  # 관련성 임계값
                    preview = metadata.get("preview", "").strip()
                    file_path = metadata.get("file_path", "").strip()
                    folder = metadata.get("folder", "").strip()
                    
                    # 파일명에서 제목 추출
                    doc_title = "PDF 문서"
                    if file_path:
                        filename = file_path.split("/")[-1] if "/" in file_path else file_path
                        if filename.endswith('.pdf'):
                            filename = filename[:-4]
                        doc_title = filename
                    
                    # 카테고리 정보
                    category = folder or "기타"
                    
                    doc_info = {
                        "title": doc_title,
                        "category": category,
                        "preview": preview[:300] + "..." if preview else "",
                        "file_path": file_path,
                        "page": metadata.get("page", ""),
                        "score": score,
                        "source": "Document DB"
                    }
                    documents.append(doc_info)
                    
            logger.info(f"문서 검색 완료 - {len(documents)}개 문서 발견")
            return documents
            
    except Exception as e:
        logger.error(f"문서 검색 실패: {e}")
    
    return []

# 검색 결과 포맷팅 함수
def format_search_results(kmooc_courses: List[Dict], documents: List[Dict]) -> str:
    """검색 결과를 멘토링 컨텍스트로 포맷팅"""
    context = ""
    
    # K-MOOC 강좌 정보
    if kmooc_courses:
        context += "📚 관련 K-MOOC 강좌:\n"
        for course in kmooc_courses:
            context += f"- {course['title']}\n"
            context += f"  운영기관: {course.get('institution', 'N/A')}\n"
            context += f"  내용: {course.get('description', '')[:200]}...\n"
            context += f"  난이도: {course.get('difficulty', 'N/A')}\n\n"
    
    # 문서 자료 정보
    if documents:
        context += "📄 참고 문서:\n"
        for doc in documents:
            context += f"- {doc['title']}\n"
            context += f"  카테고리: {doc.get('category', 'N/A')}\n"
            context += f"  내용: {doc.get('preview', '')[:150]}...\n\n"
    
    return context

@mcp.tool()
async def analyze_and_recommend_personas(message: str, session_id: str) -> PersonaRecommendation:
    """사용자 메시지를 분석하여 적절한 페르소나 추천"""
    
    logger.info(f"[RECOMMEND] 시작 - session_id: {session_id}, message: {message[:50]}...")
    
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
        # 배열 끝 불필요한 쉼표 제거 (JSON 파싱 오류 해결)
        clean_content = clean_content.replace('}, \n     ]', '} \n     ]')
        clean_content = clean_content.replace('},\n     ]', '}\n     ]')
        clean_content = clean_content.replace('}, ]', '} ]')
        clean_content = clean_content.replace('},]', '}]')
        
        result = json.loads(clean_content)
        logger.info(f"파싱된 결과: {result}")  # 디버깅용 로그
        
        # 키 존재 여부 확인 및 안전한 추출
        recommended_personas = result.get("recommended_personas", [])
        reasoning = result.get("reasoning", "추천 이유를 찾을 수 없습니다.")
        
        # 빈 리스트인 경우 기본값 설정
        if not recommended_personas:
            # 메시지 내용으로부터 간단한 추천 로직
            message_lower = message.lower()
            if any(word in message_lower for word in ["업무", "프로세스", "잡무", "회사", "조직", "사내"]):
                recommended_personas = [{"id": "mechanical", "name": "과외 선생님", "reason": "업무 프로세스 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["건축", "설계", "건물", "BIM", "인테리어"]):
                recommended_personas = [{"id": "architecture", "name": "일타 강사", "reason": "건축 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["전기", "전자", "회로", "제어", "임베디드"]):
                recommended_personas = [{"id": "electrical", "name": "교수", "reason": "전기전자 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["프로그래밍", "개발", "소프트웨어", "코딩", "AI"]):
                recommended_personas = [{"id": "computer", "name": "개발자", "reason": "개발 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["영어", "회화", "문법", "토익", "토플", "비즈니스영어", "영어공부", "프레젠테이션"]):
                recommended_personas = [{"id": "materials", "name": "영어 선생님", "reason": "영어 관련 키워드 감지"}]
            elif any(word in message_lower for word in ["운세", "사주", "명리", "점술", "궁합", "작명", "직장운", "사업운", "연애운"]):
                recommended_personas = [{"id": "chemical", "name": "명리학자", "reason": "운세 관련 키워드 감지"}]
            else:
                recommended_personas = [{"id": "computer", "name": "개발자", "reason": "기본 추천"}]
        
        # 세션에 추천 결과 저장
        session_data["recommended_personas"] = recommended_personas
        session_data["messages"].append({
            "role": "assistant", 
            "content": f"분석 결과를 바탕으로 다음 전문가들을 추천드립니다:\n\n{reasoning}"
        })
        
        save_mentor_session(session_id, session_data)
        
        # 세션 저장 확인용 로그
        session_file_path = get_mentor_session_file_path(session_id)
        logger.info(f"세션 저장 완료 - 파일: {session_file_path}")
        logger.info(f"저장된 파일 존재 확인: {os.path.exists(session_file_path)}")
        
        # 최종 결과 로깅
        logger.info(f"[RECOMMEND] 완료 - session_id: {session_id}, 추천: {[p['id'] for p in recommended_personas]}")
        
        return PersonaRecommendation(
            recommended_personas=recommended_personas,
            reasoning=reasoning
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON 파싱 오류: {e}, 응답 내용: {response.content if 'response' in locals() else 'N/A'}")
        # 기본 키워드 기반 추천으로 폴백
        message_lower = message.lower()
        if any(word in message_lower for word in ["업무", "프로세스", "잡무", "회사", "조직", "사내"]):
            fallback_personas = [{"id": "mechanical", "name": "과외 선생님", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["건축", "설계", "건물", "BIM", "인테리어"]):
            fallback_personas = [{"id": "architecture", "name": "일타 강사", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["전기", "전자", "회로", "제어", "임베디드"]):
            fallback_personas = [{"id": "electrical", "name": "교수", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["프로그래밍", "개발", "소프트웨어", "코딩", "AI"]):
            fallback_personas = [{"id": "computer", "name": "개발자", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["영어", "회화", "문법", "토익", "토플", "비즈니스영어", "영어공부", "프레젠테이션"]):
            fallback_personas = [{"id": "materials", "name": "영어 선생님", "reason": "키워드 기반 추천"}]
        elif any(word in message_lower for word in ["운세", "사주", "명리", "점술", "궁합", "작명", "직장운", "사업운", "연애운"]):
            fallback_personas = [{"id": "chemical", "name": "명리학자", "reason": "키워드 기반 추천"}]
        else:
            fallback_personas = [{"id": "computer", "name": "개발자", "reason": "기본 추천"}]
            
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
            {"id": "프로그래머", "name": "프로그래머", "reason": "일반적으로 많이 문의되는 분야입니다."}
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
    
    # 디버깅용 로그
    logger.info(f"select_persona 호출 - persona_id: {persona_id}, session_id: {session_id}")
    
    # 세션 파일 경로 확인
    session_file_path = get_mentor_session_file_path(session_id)
    logger.info(f"세션 파일 경로: {session_file_path}")
    logger.info(f"세션 파일 존재 여부: {os.path.exists(session_file_path)}")
    
    # 세션 데이터 로드
    session_data = load_mentor_session(session_id)
    if not session_data:
        logger.error(f"세션 데이터 로드 실패 - session_id: {session_id}")
        
        # 세션 파일이 있는지 다시 한번 체크
        if os.path.exists(session_file_path):
            logger.error("세션 파일은 존재하지만 로드에 실패했습니다.")
            try:
                with open(session_file_path, 'r', encoding='utf-8') as f:
                    raw_content = f.read()
                    logger.info(f"세션 파일 내용: {raw_content[:200]}...")
                    # JSON 파싱 재시도
                    session_data = json.loads(raw_content)
                    logger.info("세션 데이터 재로드 성공!")
            except Exception as parse_error:
                logger.error(f"세션 파일 파싱 오류: {parse_error}")
        
        # 여전히 세션 데이터가 없다면 새 세션 생성
        if not session_data:
            logger.info("새 멘토 세션을 생성합니다.")
            session_data = {
                "session_id": session_id,
                "phase": "persona_recommendation",
                "messages": [],
                "recommended_personas": [],
                "selected_persona": "",
                "persona_context": "",
                "completed": False
            }
            save_mentor_session(session_id, session_data)
            logger.info("새 멘토 세션 저장 완료")
    
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
    """선택된 페르소나로 전문가 멘토링 제공 (K-MOOC DB 연동)"""
    
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
    
    # K-MOOC 강좌 및 문서 검색 (병렬 실행)
    logger.info(f"멘토링 자료 검색 시작 - 질문: {message[:50]}...")
    
    import asyncio
    kmooc_task = search_kmooc_for_mentoring(message, selected_persona_id)
    docs_task = search_documents_for_mentoring(message, selected_persona_id)
    
    try:
        kmooc_courses, documents = await asyncio.gather(kmooc_task, docs_task, return_exceptions=True)
        
        # 예외 처리
        if isinstance(kmooc_courses, Exception):
            logger.error(f"K-MOOC 검색 오류: {kmooc_courses}")
            kmooc_courses = []
        if isinstance(documents, Exception):
            logger.error(f"문서 검색 오류: {documents}")
            documents = []
            
    except Exception as e:
        logger.error(f"검색 실행 오류: {e}")
        kmooc_courses, documents = [], []
    
    # 검색 결과를 컨텍스트로 구성
    search_context = format_search_results(kmooc_courses, documents)
    
    # 대화 기록 생성 (최근 8개 메시지만 - 검색 결과 추가로 토큰 절약)
    recent_messages = session_data["messages"][-8:]
    conversation_history = ""
    for msg in recent_messages[:-1]:  # 현재 메시지 제외
        role = "사용자" if msg["role"] == "user" else "멘토"
        conversation_history += f"{role}: {msg['content'][:200]}...\n"
    
    # 멘토별 맞춤형 대화 프롬프트 생성
    mentoring_prompt = f"""
{persona['system_prompt']}

=== 참고 자료 ===
{search_context if search_context else "관련 자료를 찾지 못했습니다."}

=== 이전 대화 ===
{conversation_history}

=== 사용자 질문 ===
{message}

위의 당신의 캐릭터와 전문성에 맞게 자연스럽게 대화하듯이 답변해주세요:

- 당신의 고유한 말투와 스타일을 유지하세요
- 검색된 자료가 있다면 자연스럽게 활용하세요
- 사용자가 편안하게 느낄 수 있도록 친근하게 대화하세요
- 당신의 전문 분야에 맞는 실용적인 조언을 해주세요
- 필요하다면 관련 강좌나 자료를 추천해도 좋습니다

한국어로 답변하며, 당신만의 개성 있는 대화 스타일을 보여주세요.
"""
    
    try:
        response = await llm.ainvoke(mentoring_prompt)
        mentor_response = response.content
        
        logger.info(f"멘토링 응답 생성 완료 - K-MOOC: {len(kmooc_courses)}개, 문서: {len(documents)}개 활용")
        
        # 응답을 세션에 저장
        session_data["messages"].append({
            "role": "assistant",
            "content": mentor_response
        })
        
        save_mentor_session(session_id, session_data)
        
        return MentoringResponse(
            response=mentor_response,
            persona_name=persona["name"],
            related_courses=kmooc_courses[:2],  # 상위 2개 강좌 정보 포함
            related_documents=documents[:1]     # 상위 1개 문서 정보 포함
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
            persona_name=persona["name"],
            related_courses=[],
            related_documents=[]
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