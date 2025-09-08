from mcp.server.fastmcp import FastMCP
import asyncio
import httpx
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import re
from urllib.parse import quote
import os
import glob
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from enum import Enum
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# MCP 서버 설정
mcp = FastMCP(
    "CurriculumGenerator",
    instructions="Generate personalized learning curriculums from session data",
    host="0.0.0.0",
    port=8006,
)

# LLM 초기화
def initialize_llm():
    try:
        llm = ChatOpenAI(
            base_url=Config.LLM_BASE_URL,
            api_key=Config.LLM_API_KEY,
            model=Config.LLM_MODEL,
            temperature=0.7,
            max_tokens=Config.LLM_MAX_TOKENS,
            model_kwargs={"max_completion_tokens": None}  # Friendli.ai에서 지원하지 않는 파라미터 제거
        )
        # print(f"🤖 LLM initialized: {Config.LLM_MODEL}")  # MCP 통신 방해 방지
        return llm, True
    except Exception as e:
        # print(f"❌ LLM initialization failed: {e}")  # MCP 통신 방해 방지
        return None, False

llm, llm_available = initialize_llm()

# Pydantic 모델 정의
class LevelEnum(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"

class SessionParameters(BaseModel):
    """세션 파라미터 추출을 위한 구조화된 출력"""
    level: LevelEnum = Field(description="학습자의 레벨 (beginner/intermediate/advanced)")
    duration_weeks: int = Field(description="학습 기간 (주 단위, 1-52 사이)", ge=1, le=52)  # 1년까지 확장
    focus_areas: List[str] = Field(description="학습 포커스 영역들")
    
class ExtractionRequest(BaseModel):
    """파라미터 추출 요청"""
    constraints: str = Field(description="학습 제약 조건")
    goal: str = Field(description="학습 목표")

# 데이터베이스 클래스
class CurriculumDB:
    def __init__(self, data_dir: str = "data"):
        self.curriculums = {}
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._load_data()
    
    def _load_data(self):
        try:
            file_path = os.path.join(self.data_dir, "curriculums.json")
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.curriculums = json.load(f)
                # print(f"📚 Loaded {len(self.curriculums)} curriculums")  # MCP 통신 방해 방지
        except Exception as e:
            # print(f"❌ Error loading data: {e}")  # MCP 통신 방해 방지
            self.curriculums = {}
            pass
    
    def _save_data(self):
        try:
            file_path = os.path.join(self.data_dir, "curriculums.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.curriculums, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # print(f"❌ Error saving data: {e}")  # MCP 통신 방해 방지
            pass
    
    def save_curriculum(self, user_id: str, curriculum: Dict):
        if user_id not in self.curriculums:
            self.curriculums[user_id] = []
        curriculum['id'] = len(self.curriculums[user_id])
        curriculum['created_at'] = datetime.now().isoformat()
        self.curriculums[user_id].append(curriculum)
        self._save_data()
        return curriculum['id']
    
    def get_curriculum(self, user_id: str, curriculum_id: int) -> Optional[Dict]:
        if user_id in self.curriculums and curriculum_id < len(self.curriculums[user_id]):
            return self.curriculums[user_id][curriculum_id]
        return None

db = CurriculumDB()

# 세션 데이터 로더
class SessionLoader:
    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = sessions_dir
    
    def get_completed_sessions(self) -> List[Dict[str, Any]]:
        completed_sessions = []
        session_files = glob.glob(os.path.join(self.sessions_dir, "*.json"))
        
        for session_file in session_files:
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    session_data = json.load(f)
                
                if (session_data.get("completed") and 
                    session_data.get("topic") and 
                    session_data.get("constraints") and 
                    session_data.get("goal")):
                    
                    completed_sessions.append({
                        "session_id": session_data.get("session_id"),
                        "topic": session_data.get("topic"),
                        "constraints": session_data.get("constraints"),
                        "goal": session_data.get("goal")
                    })
            except Exception as e:
                # print(f"⚠️ Error loading {session_file}: {e}")  # MCP 통신 방해 방지
                continue
        
        return completed_sessions
    
    async def extract_parameters_with_llm(self, constraints: str, goal: str, max_retries: int = 3) -> Dict[str, Any]:
        """LLM을 사용하여 세션 파라미터를 추출합니다 (재시도 메커니즘 포함)"""
        if not llm_available:
            # print("⚠️ LLM not available, using fallback method")  # MCP 통신 방해 방지
            return self.parse_constraints_fallback(constraints, goal)
        
        for attempt in range(max_retries):
            try:
                prompt = f"""다음 한국어 학습 제약조건과 목표에서 학습 파라미터를 추출해주세요:

제약조건: "{constraints}"
목표: "{goal}"

다음 기준으로 분석해주세요:

1. 레벨 (level):
   - "초보", "처음", "시작", "beginner" → "beginner"
   - "중급", "어느정도", "중간", "intermediate" → "intermediate"  
   - "고급", "전문", "숙련", "advanced" → "advanced"

2. 기간 (duration_weeks):
   - "1주", "일주일", "1week" → 1
   - "2주", "2week", "2일" → 2
   - "1달", "한달", "1month", "4주" → 4
   - "2달", "두달", "2month", "8주" → 8
   - "3달", "세달", "3month", "12주" → 12
   - "4개월", "4month", "16주" → 16
   - "5개월", "5month", "20주" → 20
   - "6개월", "반년", "6month", "24주" → 24
   - "9개월", "9month" → 36
   - "1년", "12개월", "1year", "52주" → 52
   - 명시되지 않으면 → 4

3. 포커스 영역 (focus_areas):
   - "웹", "web" → ["web development"]
   - "데이터", "data" → ["data analysis"]
   - "머신러닝", "AI", "인공지능" → ["machine learning"]
   - "앱", "모바일", "app" → ["mobile development"]
   - "개인 프로젝트", "토이 프로젝트" → ["personal projects"]
   - "취업", "면접", "job" → ["job preparation"]
   - 기타 관련 키워드들을 포함

JSON 형식으로만 응답해주세요."""
                
                # Pydantic을 사용한 구조화된 출력
                structured_llm = llm.with_structured_output(SessionParameters)
                
                messages = [
                    SystemMessage(content="당신은 한국어 학습 요구사항을 분석하는 전문가입니다."),
                    HumanMessage(content=prompt)
                ]
                
                # print(f"🤖 LLM parameter extraction attempt {attempt + 1}/{max_retries}...")  # MCP 통신 방해 방지
                result = await structured_llm.ainvoke(messages)
                
                # 성공하면 결과 반환
                extracted_params = {
                    "level": result.level.value,
                    "duration_weeks": result.duration_weeks,
                    "focus_areas": result.focus_areas
                }
                # print(f"✅ LLM extraction successful on attempt {attempt + 1}")  # MCP 통신 방해 방지
                return extracted_params
            
            except Exception as e:
                # print(f"⚠️ LLM extraction attempt {attempt + 1} failed: {e}")  # MCP 통신 방해 방지
                
                # 마지막 시도가 아니면 계속 재시도
                if attempt < max_retries - 1:
                    # print(f"🔄 Retrying... ({max_retries - attempt - 1} attempts remaining)")  # MCP 통신 방해 방지
                    continue
                else:
                    # print(f"❌ All {max_retries} LLM attempts failed, falling back to rule-based parsing")  # MCP 통신 방해 방지
                    break
        
        # 모든 재시도 실패시 fallback 사용
        return self.parse_constraints_fallback(constraints, goal)
    
    def parse_constraints_fallback(self, constraints: str, goal: str) -> Dict[str, Any]:
        """LLM 실패시 기존 규칙 기반 파싱 (fallback)"""
        constraints_lower = constraints.lower()
        goal_lower = goal.lower()
        
        # 레벨 파싱
        level = "beginner"
        if any(word in constraints_lower for word in ["중급", "어느정도", "intermediate"]):
            level = "intermediate"
        elif any(word in constraints_lower for word in ["고급", "전문", "advanced"]):
            level = "advanced"
        
        # 기간 파싱 (주 단위) - 확장된 버전
        duration_weeks = 4  # 기본값
        if any(word in constraints_lower for word in ["1주", "1week"]):
            duration_weeks = 1
        elif any(word in constraints_lower for word in ["2주", "2week", "2일"]):
            duration_weeks = 2
        elif any(word in constraints_lower for word in ["1달", "1month", "4주"]):
            duration_weeks = 4
        elif any(word in constraints_lower for word in ["2달", "2month", "8주"]):
            duration_weeks = 8
        elif any(word in constraints_lower for word in ["3달", "3month", "12주"]):
            duration_weeks = 12
        elif any(word in constraints_lower for word in ["4개월", "4month", "16주"]):
            duration_weeks = 16
        elif any(word in constraints_lower for word in ["5개월", "5month", "20주"]):
            duration_weeks = 20
        elif any(word in constraints_lower for word in ["6개월", "반년", "6month", "24주"]):
            duration_weeks = 24
        elif any(word in constraints_lower for word in ["9개월", "9month"]):
            duration_weeks = 36
        elif any(word in constraints_lower for word in ["1년", "12개월", "1year", "52주"]):
            duration_weeks = 52
        
        # 포커스 영역 추출
        focus_areas = []
        mappings = {
            "웹": ["web development"],
            "데이터": ["data analysis"],
            "머신러닝": ["machine learning"],
            "앱": ["mobile development"],
            "개인 프로젝트": ["personal projects"],
            "취업": ["job preparation"]
        }
        
        for keyword, areas in mappings.items():
            if keyword in goal_lower:
                focus_areas.extend(areas)
        
        return {
            "level": level, 
            "duration_weeks": duration_weeks,
            "focus_areas": list(set(focus_areas))
        }
    
    def update_session_with_curriculum(self, session_id: str, curriculum: Dict[str, Any]) -> bool:
        """세션 JSON 파일에 커리큘럼 정보를 추가합니다"""
        try:
            session_file_path = os.path.join(self.sessions_dir, f"{session_id}.json")
            
            if not os.path.exists(session_file_path):
                # print(f"⚠️ Session file not found: {session_file_path}")  # MCP 통신 방해 방지
                return False
            
            # 기존 세션 데이터 로드
            with open(session_file_path, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            
            # 모듈 데이터 정규화 (LLM 오류 수정)
            modules = curriculum.get("modules", [])
            cleaned_modules = []
            
            for module in modules:
                cleaned_module = {}
                for key, value in module.items():
                    # 키 정규화: 한국어 키를 영어로 매핑
                    cleaned_key = key.replace("_ ", "_").replace(" _", "_").strip()
                    
                    # 한국어 키 매핑
                    key_mapping = {
                        "key_개념들": "key_concepts",
                        "key_개념": "key_concepts",
                        "estimated_시간": "estimated_hours",
                        "estimated_시간": "estimated_hours",
                        "학습목표": "objectives",
                        "제목": "title",
                        "설명": "description",
                        "주차": "week"
                    }
                    
                    if cleaned_key in key_mapping:
                        cleaned_key = key_mapping[cleaned_key]
                    
                    cleaned_module[cleaned_key] = value
                cleaned_modules.append(cleaned_module)
            
            # 세부 커리큘럼 정보 추가 (전체 내용 포함)
            curriculum_full = {
                "curriculum_generated": True,
                "curriculum_id": curriculum.get("curriculum_id"),
                "title": curriculum.get("title"),
                "level": curriculum.get("level"),
                "duration_weeks": curriculum.get("duration_weeks"),
                "overall_goal": curriculum.get("overall_goal"),
                "generated_at": curriculum.get("generated_at"),
                "original_constraints": curriculum.get("original_constraints"),
                "original_goal": curriculum.get("original_goal"),
                
                # 정규화된 모듈 정보 포함
                "modules": cleaned_modules,
                "modules_count": len(cleaned_modules),
                
                # 학습 자료 정보 포함
                "resources": curriculum.get("resources", []),
                "resources_count": len(curriculum.get("resources", [])),
                
                # 통계 정보 계산
                "total_estimated_hours": sum(
                    module.get("estimated_hours", module.get("estimated_ hours", 0)) 
                    for module in cleaned_modules
                ),
                "average_hours_per_week": 0  # 임시로 0으로 설정
            }
            
            # 평균 시간 재계산
            total_hours = curriculum_full["total_estimated_hours"]
            duration = curriculum.get("duration_weeks", 1)
            curriculum_full["average_hours_per_week"] = (
                total_hours / duration
            ) if duration > 0 else 0
            
            session_data["curriculum"] = curriculum_full
            
            # 파일에 다시 저장
            with open(session_file_path, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, indent=2, ensure_ascii=False)
            
            # print(f"✅ Session {session_id} updated with curriculum info")  # MCP 통신 방해 방지
            return True
            
        except Exception as e:
            # print(f"❌ Failed to update session {session_id}: {e}")  # MCP 통신 방해 방지
            return False

session_loader = SessionLoader()

# 사용자 메시지에서 기간 추출하는 함수
def extract_duration_from_message(message: str) -> int:
    """사용자 메시지에서 기간을 추출하여 주 단위로 반환"""
    message_lower = message.lower()
    
    # 기간 키워드 매핑 (주 단위)
    duration_patterns = {
        "1주": 1, "1week": 1, "일주일": 1,
        "2주": 2, "2week": 2, "이주": 2,
        "1개월": 4, "1month": 4, "한달": 4, "4주": 4,
        "2개월": 8, "2month": 8, "두달": 8, "8주": 8,
        "3개월": 12, "3month": 12, "세달": 12, "12주": 12,
        "4개월": 16, "4month": 16, "16주": 16,
        "5개월": 20, "5month": 20, "20주": 20,
        "6개월": 24, "6month": 24, "반년": 24, "24주": 24,
        "9개월": 36, "9month": 36,
        "1년": 52, "12개월": 52, "1year": 52, "52주": 52
    }
    
    # 메시지에서 기간 키워드 찾기
    for keyword, weeks in duration_patterns.items():
        if keyword in message_lower:
            return weeks
    
    return None  # 기간 정보가 없으면 None 반환

# K-MOOC Summary 파싱 헬퍼 함수
def parse_kmooc_summary(summary: str) -> Dict[str, str]:
    """K-MOOC summary에서 강좌 정보를 추출합니다"""
    try:
        if not summary:
            return {}
        
        parsed_info = {}
        
        # 강좌 목표 추출
        goal_match = re.search(r'\*\*강좌 목표:\*\*\s*([^\n*]+)', summary)
        if goal_match:
            parsed_info["course_goal"] = goal_match.group(1).strip()
            # 강좌 목표에서 첫 번째 문장을 제목으로 사용
            goal_text = goal_match.group(1).strip()
            # 첫 번째 문장이나 핵심 키워드를 제목으로 추출
            if "," in goal_text:
                parsed_info["title"] = goal_text.split(",")[0].strip()
            else:
                parsed_info["title"] = goal_text[:50] + "..." if len(goal_text) > 50 else goal_text
        
        # 주요 내용 추출
        content_match = re.search(r'\*\*주요 내용:\*\*\s*([^\n*]+)', summary)
        if content_match:
            content = content_match.group(1).strip()
            parsed_info["main_content"] = content
            # 주요 내용을 요약하여 설명으로 사용
            if len(content) > 100:
                parsed_info["description"] = content[:97] + "..."
            else:
                parsed_info["description"] = content
        
        # 강좌 기간 추출
        duration_match = re.search(r'\*\*강좌 기간:\*\*[^()]*\((\d+주)\)', summary)
        if duration_match:
            parsed_info["duration"] = duration_match.group(1)
        
        # 난이도 추출
        difficulty_match = re.search(r'\*\*난이도:\*\*\s*([^\n*]+)', summary)
        if difficulty_match:
            parsed_info["difficulty"] = difficulty_match.group(1).strip()
        
        # 수업 시간 추출
        time_match = re.search(r'\*\*수업 시간:\*\*[^()]*약\s*([^\n*()]+)', summary)
        if time_match:
            parsed_info["class_time"] = time_match.group(1).strip()
        
        print(f"DEBUG: Parsed summary - title: {parsed_info.get('title', 'N/A')}, description: {parsed_info.get('description', 'N/A')[:50]}...", file=sys.stderr, flush=True)
        
        return parsed_info
        
    except Exception as e:
        print(f"DEBUG: Summary parsing failed: {e}", file=sys.stderr, flush=True)
        return {}

# K-MOOC DB 검색 (Pinecone API 연동)
async def search_kmooc_resources(topic: str, week_title: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
    """K-MOOC DB에서 관련 영상을 검색합니다"""
    try:
        # Pinecone 검색 API 호출
        search_query = f"{topic}"
        if week_title:
            search_query += f" {week_title}"
            
        search_payload = {
            "query": search_query,
            "top_k": top_k,
            "namespace": "kmooc_engineering",
            "filter": {"institution": {"$ne": ""}},
            "rerank": True,
            "include_metadata": True
        }
        
        # pinecone_use.py 서버가 localhost:8000에서 실행 중이라고 가정
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8001/search",
                json=search_payload,
                timeout=10.0
            )
            
        if response.status_code == 200:
            result = response.json()
            kmooc_videos = []
            
            for item in result.get("results", []):
                metadata = item.get("metadata", {})
                if metadata:
                    # Summary 파싱하여 강좌 정보 추출
                    summary = metadata.get("summary", "")
                    parsed_info = parse_kmooc_summary(summary)
                    
                    # 제목 결정: 파싱된 제목 > 기본 "K-MOOC 강좌"
                    course_title = parsed_info.get("title") or "K-MOOC 강좌"
                    
                    # 설명 결정: 파싱된 설명 > 주요 내용 > 강좌 목표 > 기본 메시지
                    description = (
                        parsed_info.get("description") or 
                        parsed_info.get("main_content") or 
                        parsed_info.get("course_goal") or 
                        "K-MOOC 온라인 강좌"
                    )
                    
                    video_info = {
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
                    kmooc_videos.append(video_info)
            
            return kmooc_videos
            
    except Exception as e:
        print(f"DEBUG: K-MOOC search failed: {e}", file=sys.stderr, flush=True)
        pass
    
    return []

# 학습 자료 검색 (웹 검색)
async def search_resources(topic: str, num_results: int = 10) -> List[Dict[str, str]]:
    try:
        encoded_query = quote(f"{topic} tutorial")
        url = f"https://lite.duckduckgo.com/lite/?q={encoded_query}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10.0)
            
            if response.status_code == 200:
                content = response.text
                results = []
                
                link_pattern = r'<a[^>]*class="result-link"[^>]*href="([^"]*)"[^>]*>(.*?)</a>'
                matches = re.finditer(link_pattern, content)
                
                for i, match in enumerate(matches):
                    if len(results) >= num_results:
                        break
                    results.append({
                        "title": re.sub(r'<[^>]+>', '', match.group(2)).strip(),
                        "url": match.group(1),
                        "source": "Web Search"
                    })
                
                return results
    except Exception as e:
        # print(f"❌ Search failed: {e}")  # MCP 통신 방해 방지
        pass
    
    return []

# LLM을 사용한 커리큘럼 생성
async def generate_with_llm(topic: str, level: str, duration_weeks: int, focus_areas: List[str], resources: List[Dict[str, str]] = None) -> Dict[str, Any]:
    if not llm_available:
        return create_basic_curriculum(topic, level, duration_weeks)
    
    try:
        print(f"DEBUG: generate_with_llm called - topic:{topic}, level:{level}, duration:{duration_weeks}", file=sys.stderr, flush=True)
        
        focus_text = ', '.join(focus_areas) if focus_areas else 'General coverage'
        print(f"DEBUG: Focus areas processed: {focus_text}", file=sys.stderr, flush=True)
        
        # 학습 자료가 있으면 프롬프트에 포함
        resources_text = ""
        if resources and len(resources) > 0:
            print(f"DEBUG: Processing {len(resources)} resources for prompt", file=sys.stderr, flush=True)
            resources_text = "\n\nAvailable learning resources:\n"
            for i, resource in enumerate(resources[:5], 1):
                resources_text += f"{i}. {resource.get('title', 'No title')} - {resource.get('url', 'No URL')}\n"
            resources_text += "\nConsider these resources when designing the curriculum modules.\n"
        else:
            print(f"DEBUG: No resources found, using fallback text", file=sys.stderr, flush=True)
            resources_text = "\n\nNote: No specific learning resources were found, but design a comprehensive curriculum anyway.\n"
        
        prompt = f"""다음 조건에 맞는 {duration_weeks}주 커리큘럼을 생성해주세요:

학습 주제: {topic}
학습 레벨: {level}
포커스 영역: {focus_text}{resources_text}
중요: JSON 키는 영어로, 모든 내용은 한국어로 작성해주세요!

각 모듈은 다음을 포함해야 합니다:
- 명확한 제목과 설명 (한국어)
- 3-4개의 학습 목표 (한국어)
- 학습 성과 ("내가 배울 수 있는 것") (한국어)
- 예상 학습 시간
- 핵심 개념들 (한국어)

JSON 형식 (키는 영어, 값은 한국어):
{{
    "modules": [
        {{
            "week": 1,
            "title": "모듈 제목 (한국어)",
            "description": "모듈에 대한 상세한 설명 (한국어)",
            "objectives": ["학습목표1 (한국어)", "학습목표2 (한국어)", "학습목표3 (한국어)"],
            "learning_outcomes": ["내가 배울 수 있는 것1 (한국어)", "내가 배울 수 있는 것2 (한국어)"],
            "key_concepts": ["핵심개념 1 (한국어)", "핵심개념 2 (한국어)"],
            "estimated_hours": 10
        }}
    ],
    "overall_goal": "전체 학습 목표 (한국어)"
}}"""
        
        print(f"DEBUG: Prompt constructed. Length: {len(prompt)} chars", file=sys.stderr, flush=True)
        
        messages = [
            SystemMessage(content="당신은 전문 커리큘럼 설계자입니다. 반드시 JSON 키는 영어로, 모든 값(내용)은 한국어로 작성해주세요. 예시: 'key_concepts', 'estimated_hours' 같은 키는 영어를 유지하고, 그 값들만 한국어로 작성합니다."),
            HumanMessage(content=prompt)
        ]
        
        print(f"DEBUG: Calling LLM.agenerate() - this may take a while for {duration_weeks} weeks...", file=sys.stderr, flush=True)
        import time
        start_time = time.time()
        
        # print("🤖 Generating curriculum with LLM...")  # MCP 통신 방해 방지
        response = await llm.agenerate([messages])
        
        end_time = time.time()
        print(f"DEBUG: LLM.agenerate() completed in {end_time - start_time:.2f} seconds", file=sys.stderr, flush=True)
        
        if response.generations and response.generations[0]:
            response_text = response.generations[0][0].text
            print(f"DEBUG: LLM response received. Length: {len(response_text)} chars", file=sys.stderr, flush=True)
            
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                print(f"DEBUG: JSON found in response. Parsing...", file=sys.stderr, flush=True)
                parsed_json = json.loads(json_match.group())
                print(f"DEBUG: JSON parsed successfully. Modules count: {len(parsed_json.get('modules', []))}", file=sys.stderr, flush=True)
                return parsed_json
            else:
                print(f"DEBUG: No valid JSON found in LLM response", file=sys.stderr, flush=True)
        else:
            print(f"DEBUG: No generations found in LLM response", file=sys.stderr, flush=True)
    
    except Exception as e:
        print(f"DEBUG: Exception in generate_with_llm: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        # print(f"❌ LLM generation failed: {e}")  # MCP 통신 방해 방지
        pass
    
    return create_basic_curriculum(topic, level, duration_weeks)

# 모듈별 리소스 수집 함수
async def collect_module_resources(topic: str, module_info: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """주차별 모듈에 대한 K-MOOC 영상과 웹 리소스를 수집합니다"""
    try:
        # K-MOOC 검색과 웹 검색을 병렬로 실행
        import asyncio
        
        # 검색 쿼리 생성
        week_title = module_info.get('title', '')
        key_concepts = module_info.get('key_concepts', [])
        search_keywords = f"{topic} {week_title}"
        if key_concepts:
            search_keywords += f" {key_concepts[0]}"
        
        # 병렬 검색 실행
        kmooc_task = search_kmooc_resources(topic, week_title, top_k=3)
        web_task = search_resources(search_keywords, num_results=3)
        
        kmooc_results, web_results = await asyncio.gather(
            kmooc_task, web_task, return_exceptions=True
        )
        
        # 예외 처리
        if isinstance(kmooc_results, Exception):
            print(f"DEBUG: K-MOOC search exception: {kmooc_results}", file=sys.stderr, flush=True)
            kmooc_results = []
        if isinstance(web_results, Exception):
            print(f"DEBUG: Web search exception: {web_results}", file=sys.stderr, flush=True)
            web_results = []
        
        return {
            "videos": kmooc_results or [],
            "web_links": web_results or [],
            "documents": []  # 향후 구현 예정
        }
        
    except Exception as e:
        print(f"DEBUG: collect_module_resources failed: {e}", file=sys.stderr, flush=True)
        return {
            "videos": [],
            "web_links": [],
            "documents": []
        }

# 기본 커리큘럼 생성 (LLM 실패시 fallback)
def create_basic_curriculum(topic: str, level: str, duration_weeks: int) -> Dict[str, Any]:
    modules = []
    
    for i in range(1, duration_weeks + 1):
        modules.append({
            "week": i,
            "title": f"{topic} - {i}주차",
            "description": f"{i}주차 학습 내용",
            "objectives": [f"{i}주차 핵심 개념 학습", "실습 과제 완료", "이론 이해 및 적용"],
            "learning_outcomes": [f"{topic} 기본 개념 이해", f"{i}주차 실무 지식 습득"],
            "key_concepts": [f"{i}주차 기초 개념", "실습 예제"],
            "estimated_hours": 8 + i * 2
        })
    
    return {
        "modules": modules,
        "overall_goal": f"{duration_weeks}주 동안 {topic} 기초를 마스터하기"
    }

# === MCP Tools ===

@mcp.tool()
async def list_session_topics() -> Dict[str, Any]:
    """List all completed sessions available for curriculum generation"""
    sessions = session_loader.get_completed_sessions()
    
    if not sessions:
        return {"message": "No completed sessions found", "sessions": []}
    
    topics_count = {}
    for session in sessions:
        topic = session["topic"]
        topics_count[topic] = topics_count.get(topic, 0) + 1
    
    return {
        "total_sessions": len(sessions),
        "unique_topics": len(topics_count),
        "topics": topics_count,
        "all_sessions": sessions
    }

@mcp.tool()
async def generate_curriculum_from_session(session_id: str, user_message: str = "") -> Dict[str, Any]:
    """Generate curriculum from a specific session with optional user message for duration override"""
    sessions = session_loader.get_completed_sessions()
    session_data = None
    
    for session in sessions:
        if session["session_id"] == session_id:
            session_data = session
            break
    
    if not session_data:
        return {"error": f"Session {session_id} not found"}
    
    # 파라미터 추출
    topic = session_data["topic"]
    constraints = session_data["constraints"]
    goal = session_data["goal"]
    
    params = await session_loader.extract_parameters_with_llm(constraints, goal)
    
    # 사용자 메시지에서 기간 정보 추출 및 오버라이드
    if user_message:
        message_duration = extract_duration_from_message(user_message)
        print(f"DEBUG: user_message='{user_message}'", file=sys.stderr, flush=True)
        print(f"DEBUG: extracted duration={message_duration}", file=sys.stderr, flush=True)
        print(f"DEBUG: original params duration={params.get('duration_weeks')}", file=sys.stderr, flush=True)
        
        if message_duration is not None:
            params["duration_weeks"] = message_duration
            print(f"DEBUG: overridden to {message_duration} weeks", file=sys.stderr, flush=True)
        else:
            print(f"DEBUG: no duration found in message", file=sys.stderr, flush=True)
    
    # print(f"📚 Generating curriculum for {session_id}:")  # MCP 통신 방해 방지
    # print(f"  Topic: {topic}")  # MCP 통신 방해 방지
    # print(f"  Level: {params['level']}")  # MCP 통신 방해 방지
    # print(f"  Duration: {params['duration_weeks']} weeks")  # MCP 통신 방해 방지
    
    # 기본 학습 자료 검색 (프롬프트용)
    print(f"DEBUG: Starting basic resource search for topic: {topic}", file=sys.stderr, flush=True)
    basic_resources = await search_resources(topic)
    print(f"DEBUG: Basic resource search completed. Found {len(basic_resources)} resources", file=sys.stderr, flush=True)
    
    # 커리큘럼 생성 (기본 구조)
    print(f"DEBUG: Starting LLM curriculum generation...", file=sys.stderr, flush=True)
    print(f"DEBUG: LLM parameters - topic:{topic}, level:{params['level']}, duration:{params['duration_weeks']}, focus_areas:{params['focus_areas']}", file=sys.stderr, flush=True)
    print(f"DEBUG: llm_available status: {llm_available}", file=sys.stderr, flush=True)
    
    try:
        curriculum_data = await generate_with_llm(
            topic=topic,
            level=params["level"],
            duration_weeks=params["duration_weeks"],
            focus_areas=params["focus_areas"],
            resources=basic_resources
        )
        print(f"DEBUG: LLM curriculum generation completed successfully", file=sys.stderr, flush=True)
        print(f"DEBUG: Generated {len(curriculum_data.get('modules', []))} modules", file=sys.stderr, flush=True)
    except Exception as e:
        print(f"DEBUG: LLM curriculum generation failed with error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise
    
    # 각 모듈에 대해 구조화된 리소스 수집
    modules = curriculum_data.get("modules", [])
    print(f"DEBUG: Processing {len(modules)} modules for resource collection", file=sys.stderr, flush=True)
    
    for module in modules:
        module_topic = f"{topic} {module.get('title', '')}"
        week_title = module.get('title', '')
        
        print(f"DEBUG: Collecting resources for module: {week_title}", file=sys.stderr, flush=True)
        
        # 병렬로 리소스 수집 (K-MOOC + 웹 검색)
        module_resources = await collect_module_resources(module_topic, module)
        
        # 모듈에 리소스 추가
        module["resources"] = {
            "videos": module_resources.get("videos", []),
            "web_links": module_resources.get("web_links", []),
            "documents": []  # 추후 문서 검색 API 연동 시 사용
        }
        
        print(f"DEBUG: Added {len(module_resources.get('videos', []))} videos and {len(module_resources.get('web_links', []))} web links", file=sys.stderr, flush=True)
    
    # 최종 커리큘럼 구성
    curriculum = {
        "title": f"{topic} Learning Path",
        "level": params["level"],
        "duration_weeks": params["duration_weeks"],
        "modules": modules,  # 리소스가 포함된 모듈들
        "overall_goal": curriculum_data.get("overall_goal", f"Master {topic}"),
        "resources": basic_resources[:5] if basic_resources else [],  # 전체 참고 자료
        "session_id": session_id,
        "original_constraints": constraints,
        "original_goal": goal,
        "generated_at": datetime.now().isoformat()
    }
    
    # 데이터베이스 저장
    curriculum_id = db.save_curriculum(session_id, curriculum)
    curriculum["curriculum_id"] = curriculum_id
    
    # 세션 파일에도 커리큘럼 정보 업데이트
    session_loader.update_session_with_curriculum(session_id, curriculum)
    
    return curriculum

@mcp.tool()
async def generate_curriculums_from_all_sessions() -> Dict[str, Any]:
    """Generate curriculums for all completed sessions"""
    sessions = session_loader.get_completed_sessions()
    
    if not sessions:
        return {
            "message": "No completed sessions found",
            "sessions_processed": 0,
            "curriculums_generated": 0
        }
    
    successful = []
    failed = []
    
    for session in sessions:
        session_id = session["session_id"]
        
        try:
            # 이미 존재하는지 확인
            existing = db.get_curriculum(session_id, 0)
            if existing:
                # print(f"⚠️ Curriculum already exists for {session_id}")  # MCP 통신 방해 방지
                continue
            
            result = await generate_curriculum_from_session(session_id)
            
            if "error" in result:
                failed.append({"session_id": session_id, "error": result["error"]})
            else:
                successful.append({
                    "session_id": session_id,
                    "topic": session["topic"],
                    "curriculum_id": result.get("curriculum_id")
                })
                # print(f"✅ Generated curriculum for {session_id}")  # MCP 통신 방해 방지
                
        except Exception as e:
            failed.append({"session_id": session_id, "error": str(e)})
    
    return {
        "sessions_processed": len(sessions),
        "curriculums_generated": len(successful),
        "successful_generations": successful,
        "failed_generations": failed,
        "success_rate": f"{(len(successful) / len(sessions)) * 100:.1f}%" if sessions else "0%"
    }

@mcp.tool()
async def get_curriculum(user_id: str, curriculum_id: int = 0) -> Dict[str, Any]:
    """Get a specific curriculum"""
    curriculum = db.get_curriculum(user_id, curriculum_id)
    
    if not curriculum:
        return {"error": "Curriculum not found"}
    
    return curriculum

@mcp.tool()
async def search_learning_resources(topic: str, num_results: int = 10) -> Dict[str, Any]:
    """Search for learning resources on a topic"""
    resources = await search_resources(topic, num_results)
    
    return {
        "topic": topic,
        "total_resources": len(resources),
        "resources": resources
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")