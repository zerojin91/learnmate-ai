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
from bs4 import BeautifulSoup
import time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# 진행 상태 관리 클래스
class CurriculumProgress:
    """커리큘럼 생성 과정의 진행 상태를 추적하고 공유하는 클래스"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.progress_file = f"{os.getcwd()}/data/progress/{session_id}.json"
        self.current_phase = None
        self.phase_start_time = None
        
    async def update(self, phase: str, message: str, details: dict = None, thinking: str = None):
        """진행 상태를 업데이트하고 파일에 저장"""
        try:
            # 새로운 페이즈 시작 시 시간 기록
            if phase != self.current_phase:
                self.current_phase = phase
                self.phase_start_time = datetime.now()
            
            progress_data = {
                "session_id": self.session_id,
                "timestamp": datetime.now().isoformat(),
                "phase": phase,
                "message": message,
                "details": details or {},
                "thinking": thinking,  # LLM의 사고 과정
                "phase_duration": (datetime.now() - self.phase_start_time).total_seconds() if self.phase_start_time else 0
            }
            
            # 파일에 저장 (덮어쓰기)
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
            
            # 디버깅용 stderr 출력
            print(f"PROGRESS: [{phase}] {message}", file=sys.stderr, flush=True)
            if thinking:
                print(f"THINKING: {thinking[:100]}...", file=sys.stderr, flush=True)
                
        except Exception as e:
            print(f"DEBUG: Progress update failed: {e}", file=sys.stderr, flush=True)
    
    def cleanup(self):
        """완료 후 진행 상태 파일 삭제"""
        try:
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
        except Exception:
            pass

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
                "http://localhost:8090/search",
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

# 리소스 콘텐츠 추출 함수
async def fetch_resource_content(resource: Dict[str, str]) -> Dict[str, Any]:
    """웹 리소스의 실제 콘텐츠를 가져와서 파싱합니다"""
    try:
        url = resource.get('url', '')
        if not url or not url.startswith(('http://', 'https://')):
            return {
                "success": False,
                "error": "Invalid URL",
                "raw_content": "",
                "summary": "",
                "key_points": [],
                "code_examples": []
            }
        
        # 웹 페이지 내용 가져오기
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "raw_content": "",
                    "summary": "",
                    "key_points": [],
                    "code_examples": []
                }
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'lxml')
            
            # 메타 태그 제거
            for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
                script.decompose()
            
            # 본문 텍스트 추출
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup.body
            if main_content:
                text_content = main_content.get_text(separator=' ', strip=True)
            else:
                text_content = soup.get_text(separator=' ', strip=True)
            
            # 텍스트 정리 (과도한 공백 제거)
            cleaned_text = ' '.join(text_content.split())
            
            # 코드 예제 추출
            code_examples = []
            code_blocks = soup.find_all(['code', 'pre'])
            for block in code_blocks:
                code_text = block.get_text(strip=True)
                if len(code_text) > 10:  # 너무 짧은 코드는 제외
                    code_examples.append(code_text)
            
            # 핵심 포인트 추출 (제목 태그 기반)
            key_points = []
            headers = soup.find_all(['h1', 'h2', 'h3', 'h4'])
            for header in headers:
                header_text = header.get_text(strip=True)
                if len(header_text) > 5 and len(header_text) < 100:
                    key_points.append(header_text)
            
            # 요약 생성 (첫 500자)
            summary = cleaned_text[:500] + "..." if len(cleaned_text) > 500 else cleaned_text
            
            return {
                "success": True,
                "raw_content": cleaned_text[:2000],  # 최대 2000자로 제한
                "summary": summary,
                "key_points": key_points[:10],  # 최대 10개
                "code_examples": code_examples[:5],  # 최대 5개
                "content_length": len(cleaned_text),
                "url": url,
                "title": resource.get('title', soup.title.string if soup.title else 'No title')
            }
            
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Request timeout",
            "raw_content": "",
            "summary": "",
            "key_points": [],
            "code_examples": []
        }
    except Exception as e:
        print(f"DEBUG: fetch_resource_content failed for {resource.get('url', 'unknown')}: {e}", file=sys.stderr, flush=True)
        return {
            "success": False,
            "error": str(e),
            "raw_content": "",
            "summary": "",
            "key_points": [],
            "code_examples": []
        }

# LLM을 사용한 단계별 커리큘럼 생성 (스트리밍 버전)
async def generate_with_llm_streaming(topic: str, level: str, duration_weeks: int, focus_areas: List[str], resources: List[Dict[str, str]] = None, session_id: str = None) -> Dict[str, Any]:
    """LLM을 사용하여 단계별로 커리큘럼을 생성하며 진행 상태를 공유"""
    if not llm_available:
        return create_basic_curriculum(topic, level, duration_weeks)
    
    # 진행 상태 추적기 초기화
    progress = CurriculumProgress(session_id) if session_id else None
    
    try:
        focus_text = ', '.join(focus_areas) if focus_areas else 'General coverage'
        
        # Phase 1: 학습 경로 분석
        if progress:
            await progress.update("analysis", "🧠 학습 경로를 분석하는 중...")
        
        analysis_prompt = f"""다음 학습 요구사항을 분석하여 체계적인 학습 계획을 수립해주세요:

학습 주제: {topic}
학습 레벨: {level}
학습 기간: {duration_weeks}주
포커스 영역: {focus_text}

먼저 다음을 분석해주세요:
1. 이 주제의 핵심 학습 영역은 무엇인가?
2. {level} 수준에서 시작하여 어떤 순서로 학습해야 하는가?
3. {focus_areas}를 고려할 때 중점을 둬야 할 부분은?
4. {duration_weeks}주 동안 현실적으로 달성 가능한 목표는?

분석 결과를 자세히 설명하고, 전체 학습 로드맵을 제시해주세요."""
        
        analysis_messages = [
            SystemMessage(content="당신은 전문 교육 설계자입니다. 학습자의 요구에 맞는 최적의 학습 경로를 분석하고 설계해주세요."),
            HumanMessage(content=analysis_prompt)
        ]
        
        print(f"DEBUG: Starting Phase 1 - Learning Path Analysis", file=sys.stderr, flush=True)
        analysis_response = await llm.agenerate([analysis_messages])
        analysis_text = analysis_response.generations[0][0].text if analysis_response.generations else ""
        
        if progress:
            await progress.update("analysis", "💡 분석 완료", thinking=analysis_text[:500])
        
        # Phase 2: 전체 모듈 구조 설계
        if progress:
            await progress.update("structure_design", "📋 전체 모듈 구조를 설계하는 중...")
        
        structure_prompt = f"""앞선 분석을 바탕으로 {duration_weeks}주 커리큘럼의 전체 구조를 설계해주세요.

이전 분석 결과:
{analysis_text}

각 주차별로 다음 정보만 포함하여 JSON 형태로 생성해주세요:
- week: 주차 번호
- title: 주차 제목 (한국어)
- main_topic: 주요 학습 주제 (한국어)
- learning_goals: 이번 주차의 핵심 목표 2-3개 (한국어 리스트)
- difficulty_level: 난이도 (1-10)

JSON 형식:
{{
    "modules": [
        {{
            "week": 1,
            "title": "주차 제목",
            "main_topic": "주요 학습 주제", 
            "learning_goals": ["목표1", "목표2"],
            "difficulty_level": 3
        }}
    ],
    "overall_goal": "전체 학습 목표"
}}"""
        
        structure_messages = [
            SystemMessage(content="전체 커리큘럼 구조를 설계하는 전문가입니다. 논리적이고 체계적인 학습 흐름을 만들어주세요."),
            HumanMessage(content=structure_prompt)
        ]
        
        print(f"DEBUG: Starting Phase 2 - Structure Design", file=sys.stderr, flush=True)
        structure_response = await llm.agenerate([structure_messages])
        structure_text = structure_response.generations[0][0].text if structure_response.generations else ""
        
        # JSON 파싱
        json_match = re.search(r'\{[\s\S]*\}', structure_text)
        if not json_match:
            if progress:
                await progress.update("structure_design", "❌ 구조 설계 실패", details={"error": "JSON 파싱 실패"})
            return create_basic_curriculum(topic, level, duration_weeks)
        
        structure_data = json.loads(json_match.group())
        modules = structure_data.get("modules", [])
        
        if progress:
            # f-string 중첩 문제를 피하기 위해 분리
            module_titles = [m.get('title', f"{m.get('week')}주차") for m in modules[:5]]
            flow_text = ' → '.join(module_titles)
            await progress.update("structure_design", f"✅ {len(modules)}개 모듈 구조 설계 완료", 
                                thinking=f"전체 학습 흐름: {flow_text}...")
        
        # Phase 3: 각 모듈 상세 내용 생성
        detailed_modules = []
        for i, module in enumerate(modules):
            if progress:
                # f-string 중첩 문제를 피하기 위해 분리
                module_title = module.get('title', f"{module.get('week')}주차")
                await progress.update("detail_generation", 
                                    f"📝 {module_title} 상세 내용 생성 중...",
                                    details={"current": i + 1, "total": len(modules)})
            
            detail_prompt = f"""다음 모듈의 상세 내용을 생성해주세요:

모듈 정보:
- 주차: {module.get('week')}주차
- 제목: {module.get('title')}
- 주요 주제: {module.get('main_topic')}
- 학습 목표: {module.get('learning_goals')}

이전 모듈들: {[m.get('title') for m in detailed_modules[-2:]] if detailed_modules else '없음'}

다음 내용을 포함한 상세 모듈을 JSON으로 생성해주세요:
{{
    "week": {module.get('week')},
    "title": "{module.get('title')}",
    "description": "모듈에 대한 상세한 설명 (한국어)",
    "objectives": ["구체적인 학습목표1", "학습목표2", "학습목표3"],
    "learning_outcomes": ["내가 배울 수 있는 것1", "내가 배울 수 있는 것2"],
    "key_concepts": ["핵심개념1", "핵심개념2", "핵심개념3"],
    "estimated_hours": 예상학습시간(숫자)
}}"""
            
            detail_messages = [
                SystemMessage(content="각 모듈의 상세 내용을 설계하는 전문가입니다. 실용적이고 구체적인 학습 내용을 만들어주세요."),
                HumanMessage(content=detail_prompt)
            ]
            
            detail_response = await llm.agenerate([detail_messages])
            detail_text = detail_response.generations[0][0].text if detail_response.generations else ""
            
            # JSON 파싱
            detail_json_match = re.search(r'\{[\s\S]*\}', detail_text)
            if detail_json_match:
                try:
                    detailed_module = json.loads(detail_json_match.group())
                    detailed_modules.append(detailed_module)
                    
                    if progress:
                        await progress.update("detail_generation", 
                                            f"✅ {module.get('title')} 완료",
                                            thinking=f"핵심 개념: {', '.join(detailed_module.get('key_concepts', [])[:2])}")
                except json.JSONDecodeError:
                    # 파싱 실패 시 기본 구조 사용
                    detailed_modules.append(module)
            else:
                detailed_modules.append(module)
        
        if progress:
            await progress.update("completion", "✅ 커리큘럼 생성 완료!")
        
        return {
            "modules": detailed_modules,
            "overall_goal": structure_data.get("overall_goal", f"Master {topic}")
        }
        
    except Exception as e:
        print(f"DEBUG: Streaming curriculum generation failed: {e}", file=sys.stderr, flush=True)
        if progress:
            await progress.update("error", f"❌ 생성 실패: {str(e)}")
        return create_basic_curriculum(topic, level, duration_weeks)

# LLM을 사용한 커리큘럼 생성 (기존 버전)
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

# 모듈별 리소스 수집 함수 (콘텐츠 포함)
async def collect_module_resources(topic: str, module_info: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """주차별 모듈에 대한 K-MOOC 영상과 웹 리소스를 수집하고 실제 콘텐츠도 가져옵니다"""
    try:
        # K-MOOC 검색과 웹 검색을 병렬로 실행
        import asyncio
        
        # 검색 쿼리 생성 - 더 구체적이고 관련성 높은 키워드
        week_title = module_info.get('title', '')
        key_concepts = module_info.get('key_concepts', [])
        
        # 기본 주제에서 핵심 용어 추출
        core_topic = topic.split()[0] if topic else ""  # 첫 번째 단어만 사용
        
        # 주차 제목에서 핵심 키워드 추출
        week_keywords = []
        if "기초" in week_title:
            week_keywords.append("기초")
        if "회로" in week_title:
            week_keywords.append("회로")
        if "분석" in week_title:
            week_keywords.append("분석")
        if "설계" in week_title:
            week_keywords.append("설계")
        
        # 핵심 개념에서 구체적 키워드 선택 (최대 2개)
        concept_keywords = []
        for concept in key_concepts[:2]:
            if "옴의 법칙" in concept:
                concept_keywords.append("옴의법칙")
            elif "키르히호프" in concept:
                concept_keywords.append("키르히호프")
            elif "저항" in concept:
                concept_keywords.append("저항")
            elif "전류" in concept:
                concept_keywords.append("전류")
            elif "전압" in concept:
                concept_keywords.append("전압")
        
        # 검색 키워드 조합
        search_parts = [core_topic]
        search_parts.extend(week_keywords[:1])  # 주차 키워드 1개
        search_parts.extend(concept_keywords[:1])  # 개념 키워드 1개
        
        search_keywords = " ".join(filter(None, search_parts))
        
        print(f"DEBUG: Enhanced search keywords: {search_keywords} (from topic: {topic}, week: {week_title})", file=sys.stderr, flush=True)
        
        # 병렬 검색 실행
        kmooc_task = search_kmooc_resources(topic, week_title, top_k=3)
        web_task = search_resources(search_keywords, num_results=5)  # 더 많은 웹 결과 수집
        
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
        
        # 웹 리소스의 실제 콘텐츠 가져오기
        enhanced_web_links = []
        if web_results and len(web_results) > 0:
            print(f"DEBUG: Fetching content for {len(web_results)} web resources", file=sys.stderr, flush=True)
            
            # 각 웹 리소스에 대해 콘텐츠 수집 (최대 3개)
            content_tasks = []
            for resource in web_results[:3]:  # Rate limit 고려하여 최대 3개로 제한
                content_tasks.append(fetch_resource_content(resource))
            
            if content_tasks:
                # 콘텐츠 수집을 병렬로 실행
                content_results = await asyncio.gather(*content_tasks, return_exceptions=True)
                
                # 성공한 콘텐츠만 추가
                for i, content in enumerate(content_results):
                    if not isinstance(content, Exception) and content.get('success', False):
                        enhanced_resource = {
                            **web_results[i],  # 기존 정보 유지
                            "content": content,  # 새로운 콘텐츠 정보 추가
                            "has_content": True
                        }
                        enhanced_web_links.append(enhanced_resource)
                        print(f"DEBUG: Successfully fetched content for: {content.get('title', 'Unknown')[:50]}...", file=sys.stderr, flush=True)
                    else:
                        # 콘텐츠 수집 실패시 기본 정보만 유지
                        enhanced_resource = {
                            **web_results[i],
                            "has_content": False,
                            "content_error": str(content) if isinstance(content, Exception) else content.get('error', 'Unknown error')
                        }
                        enhanced_web_links.append(enhanced_resource)
                        print(f"DEBUG: Failed to fetch content for: {web_results[i].get('title', 'Unknown')}", file=sys.stderr, flush=True)
                
                # Rate limiting을 위한 짧은 대기
                await asyncio.sleep(0.5)
        
        # K-MOOC 리소스도 콘텐츠 정보 확장 (summary 기반)
        enhanced_kmooc_videos = []
        for video in kmooc_results:
            enhanced_video = {
                **video,
                "has_content": True,  # K-MOOC는 summary가 있으므로 True
                "content": {
                    "success": True,
                    "summary": video.get('description', ''),
                    "key_points": [video.get('course_goal', '')] if video.get('course_goal') else [],
                    "raw_content": video.get('description', '') + ' ' + video.get('course_goal', ''),
                    "code_examples": [],
                    "title": video.get('title', ''),
                    "url": video.get('url', '')
                }
            }
            enhanced_kmooc_videos.append(enhanced_video)
        
        total_resources = len(enhanced_web_links) + len(enhanced_kmooc_videos)
        resources_with_content = len([r for r in enhanced_web_links if r.get('has_content', False)]) + len(enhanced_kmooc_videos)
        
        print(f"DEBUG: Collected {total_resources} resources, {resources_with_content} with content", file=sys.stderr, flush=True)
        
        return {
            "videos": enhanced_kmooc_videos,
            "web_links": enhanced_web_links,
            "documents": [],  # 향후 구현 예정
            "total_resources": total_resources,
            "resources_with_content": resources_with_content,
            "content_coverage": resources_with_content / max(total_resources, 1)
        }
        
    except Exception as e:
        print(f"DEBUG: collect_module_resources failed: {e}", file=sys.stderr, flush=True)
        return {
            "videos": [],
            "web_links": [],
            "documents": [],
            "total_resources": 0,
            "resources_with_content": 0,
            "content_coverage": 0.0
        }

# 리소스 기반 강의 콘텐츠 생성 함수
async def generate_lecture_content(module: Dict[str, Any], resources: Dict[str, Any]) -> Dict[str, str]:
    """수집된 리소스 콘텐츠를 기반으로 강의 내용을 생성합니다"""
    if not llm_available:
        return {
            "introduction": f"{module.get('title', 'Module')} 학습을 시작합니다.",
            "main_content": "내부 자료 부족으로 기본 학습 안내를 제공합니다.",
            "examples": [],
            "exercises": [],
            "summary": f"{module.get('title', 'Module')} 학습을 완료했습니다.",
            "content_sources": [],
            "coverage_note": "추가 학습 자료가 필요합니다."
        }
    
    try:
        # 리소스에서 콘텐츠 추출
        all_content = []
        source_references = []
        
        # 중복 제거를 위한 세트
        seen_urls = set()
        seen_titles = set()
        
        # 웹 리소스 콘텐츠 수집
        web_links = resources.get("web_links", [])
        for link in web_links:
            if link.get("has_content", False) and link.get("content", {}).get("success", False):
                content_info = link["content"]
                url = link.get("url", "")
                title = content_info.get("title", link.get("title", "Unknown"))
                
                # 중복 체크 (URL 또는 제목)
                if url in seen_urls or title in seen_titles:
                    print(f"DEBUG: 중복 웹 링크 제외: {title}", file=sys.stderr, flush=True)
                    continue
                    
                seen_urls.add(url)
                seen_titles.add(title)
                
                all_content.append({
                    "source": "web",
                    "title": title,
                    "summary": content_info.get("summary", ""),
                    "raw_content": content_info.get("raw_content", "")[:3000],
                    "key_points": content_info.get("key_points", []),
                    "code_examples": content_info.get("code_examples", []),
                    "url": url
                })
                source_references.append({
                    "title": title,
                    "url": url,
                    "type": "web"
                })
        
        # K-MOOC 비디오 콘텐츠 수집
        videos = resources.get("videos", [])
        for video in videos:
            if video.get("has_content", False) and video.get("content", {}).get("success", False):
                content_info = video["content"]
                url = video.get("url", "")
                title = content_info.get("title", video.get("title", "Unknown"))
                
                # 중복 체크 (URL 또는 제목)
                if url in seen_urls or title in seen_titles:
                    print(f"DEBUG: 중복 비디오 제외: {title}", file=sys.stderr, flush=True)
                    continue
                    
                seen_urls.add(url)
                seen_titles.add(title)
                
                all_content.append({
                    "source": "kmooc",
                    "title": title,
                    "summary": content_info.get("summary", ""),
                    "raw_content": content_info.get("raw_content", "")[:3000],
                    "key_points": content_info.get("key_points", []),
                    "course_goal": video.get("course_goal", ""),
                    "institution": video.get("institution", ""),
                    "url": url
                })
                source_references.append({
                    "title": title,
                    "url": url,
                    "institution": video.get("institution", ""),
                    "type": "kmooc"
                })
        
        content_coverage = resources.get("content_coverage", 0.0)
        
        # 콘텐츠가 충분하지 않은 경우
        if len(all_content) == 0:
            return {
                "introduction": f"{module.get('title', 'Module')} 학습을 시작합니다.",
                "main_content": "현재 내부 DB에서 관련 학습 자료를 찾을 수 없습니다. 추가 자료 수집이 필요합니다.",
                "examples": [],
                "exercises": [],
                "summary": "학습 자료 부족으로 기본 안내만 제공됩니다.",
                "content_sources": [],
                "coverage_note": "관련 학습 자료를 추가로 수집해주세요."
            }
        
        # LLM에게 강의 내용 생성 요청
        combined_content = ""
        for content in all_content:
            combined_content += f"\n=== {content['title']} ({content['source']}) ===\n"
            combined_content += f"요약: {content['summary']}\n"
            combined_content += f"내용: {content['raw_content']}\n"
            if content.get('key_points'):
                combined_content += f"핵심 포인트: {', '.join(content['key_points'][:3])}\n"
            if content.get('code_examples'):
                combined_content += f"코드 예제: {content['code_examples'][0][:200]}...\n"
        
        lecture_prompt = f"""다음 내부 DB에서 수집한 자료들을 기반으로 충실한 강의 내용을 작성해주세요:

주차: {module.get('title', 'Module')}
학습 목표: {', '.join(module.get('objectives', []))}
핵심 개념: {', '.join(module.get('key_concepts', []))}

=== 수집된 내부 자료 ===
{combined_content}

**강의 작성 지침:**
- 최소 1000자 이상의 충실한 강의 내용을 작성해주세요
- 제공된 내부 자료의 내용만을 활용하여 체계적으로 구성
- 각 섹션마다 구체적이고 실질적인 내용 포함

**중요: 반드시 다음과 같은 정확한 JSON 형식으로만 응답하세요:**

{{
  "introduction": "텍스트 내용 (따옴표 안에 텍스트만, JSON 객체 절대 금지)",
  "main_content": "텍스트 내용 (따옴표 안에 텍스트만, JSON 객체 절대 금지)",
  "examples": ["텍스트1", "텍스트2", "텍스트3"],
  "exercises": ["텍스트1", "텍스트2", "텍스트3"], 
  "summary": "텍스트 내용 (따옴표 안에 텍스트만, JSON 객체 절대 금지)"
}}

**절대 금지사항:**
- JSON 안에 또 다른 JSON 객체를 넣지 마세요
- 중괄호 {{}} 나 따옴표를 텍스트에 포함하지 마세요
- 각 필드는 순수한 텍스트나 텍스트 배열만 포함하세요

**내용 요구사항:**
- introduction: 최소 100자 이상의 인사말과 목표 소개
- main_content: 최소 600자 이상의 학습 내용 (출처 표기 포함)
- examples: 3개의 구체적 실습 예제
- exercises: 3개의 연습 문제
- summary: 최소 150자 이상의 핵심 내용 정리

오직 위 JSON 형식만 응답하세요. 다른 텍스트나 설명은 일절 포함하지 마세요."""

        messages = [
            SystemMessage(content="당신은 사내 교육 강사입니다. 제공된 내부 DB 자료만을 활용하여 정확하고 체계적인 강의를 작성해주세요."),
            HumanMessage(content=lecture_prompt)
        ]
        
        print(f"DEBUG: Generating lecture content with {len(all_content)} resources", file=sys.stderr, flush=True)
        response = await llm.agenerate([messages])
        
        if response.generations and response.generations[0]:
            response_text = response.generations[0][0].text
            print(f"DEBUG: LLM 응답 길이: {len(response_text)} 문자", file=sys.stderr, flush=True)
            print(f"DEBUG: LLM 응답 첫 500문자: {response_text[:500]}", file=sys.stderr, flush=True)
            
            # JSON 파싱 시도 - 더 정확한 패턴 매칭
            # 전체 응답이 JSON인지 먼저 확인
            response_text = response_text.strip()
            if response_text.startswith('{') and response_text.endswith('}'):
                json_text = response_text
            else:
                # JSON 패턴 찾기
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text)
                if json_match:
                    json_text = json_match.group()
                else:
                    json_text = None
            
            if json_text:
                try:
                    lecture_data = json.loads(json_text)
                    print(f"DEBUG: JSON 파싱 성공! 키들: {list(lecture_data.keys())}", file=sys.stderr, flush=True)
                    
                    # 기본 구조 확인 및 보완
                    lecture_content = {
                        "introduction": lecture_data.get("introduction", f"{module.get('title', 'Module')} 학습을 시작합니다."),
                        "main_content": lecture_data.get("main_content", "강의 내용을 준비 중입니다."),
                        "examples": lecture_data.get("examples", []),
                        "exercises": lecture_data.get("exercises", []),
                        "summary": lecture_data.get("summary", "학습을 완료했습니다."),
                        "content_sources": source_references,
                        "coverage_note": f"DB 커버리지: {content_coverage:.0%}, {len(all_content)}개 자료 활용"
                    }
                    
                    print(f"DEBUG: 최종 강의 내용 - introduction: {len(lecture_content['introduction'])}자, main_content: {len(lecture_content['main_content'])}자", file=sys.stderr, flush=True)
                    return lecture_content
                    
                except json.JSONDecodeError as e:
                    print(f"DEBUG: JSON 파싱 실패: {str(e)}", file=sys.stderr, flush=True)
                    print(f"DEBUG: JSON 매치된 텍스트: {json_match.group()[:300]}", file=sys.stderr, flush=True)
            else:
                print("DEBUG: JSON 패턴을 찾을 수 없음", file=sys.stderr, flush=True)
        
        # 파싱 실패시 response_text에서 안전하게 내용 추출
        fallback_content = f"수집된 {len(all_content)}개 자료를 기반으로 학습 내용을 구성했습니다."
        
        # 응답에서 JSON이 아닌 유용한 텍스트만 추출 시도
        if response_text and len(response_text) > 100:
            # JSON 구조 문자열이 포함된 경우 제거
            if '{' in response_text and '}' in response_text:
                print("DEBUG: JSON 파싱 실패, JSON 구조 제거 후 텍스트 추출", file=sys.stderr, flush=True)
                # JSON 부분을 제거하고 순수 텍스트만 추출
                lines = response_text.split('\n')
                clean_lines = []
                skip_json = False
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('{') or '"' in line[:10]:  # JSON 시작으로 보이는 라인
                        skip_json = True
                        continue
                    elif skip_json and line.endswith('}'):  # JSON 끝
                        skip_json = False
                        continue
                    elif not skip_json and len(line) > 20 and not line.startswith('"'):
                        clean_lines.append(line)
                
                if clean_lines:
                    fallback_content = ' '.join(clean_lines[:3])[:800]  # 처음 3줄, 최대 800자
                    print(f"DEBUG: 텍스트 추출 성공, 길이: {len(fallback_content)}", file=sys.stderr, flush=True)
            else:
                print("DEBUG: 순수 텍스트 응답으로 보임, 일부 사용", file=sys.stderr, flush=True)
                fallback_content = response_text[:800] + "..."
        
        # 수집된 자료 정보를 포함한 더 풍부한 기본 콘텐츠 생성
        resource_summary = ""
        if all_content:
            resource_summary = f"\n\n📚 수집된 학습 자료:\n"
            for i, content in enumerate(all_content[:3], 1):  # 상위 3개만 표시
                resource_summary += f"{i}. {content['title']} ({content['source']})\n"
                if content.get('summary'):
                    resource_summary += f"   요약: {content['summary'][:100]}...\n"
        
        return {
            "introduction": f"안녕하세요! {module.get('title', 'Module')} 학습을 시작합니다. 이번 주차에서는 {', '.join(module.get('key_concepts', ['핵심 개념들'])[:2])} 등을 다룰 예정입니다.",
            "main_content": fallback_content + resource_summary,
            "examples": ["수집된 자료의 실습 예제를 참고해주세요.", "각 자료의 예시 코드를 직접 실행해보세요."],
            "exercises": [
                f"{module.get('title', 'Module')}의 핵심 개념을 설명해보세요.",
                "학습한 내용을 실제 상황에 어떻게 적용할 수 있는지 생각해보세요.", 
                "참고 자료의 예제를 응용한 새로운 문제를 만들어보세요."
            ],
            "summary": f"{module.get('title', 'Module')} 학습을 통해 {', '.join(module.get('objectives', ['학습 목표'])[:2])} 등을 달성할 수 있습니다. 제공된 {len(all_content)}개 자료를 통해 심화 학습을 진행하세요.",
            "content_sources": source_references,
            "coverage_note": f"DB 커버리지: {content_coverage:.0%}, {len(all_content)}개 자료 활용 (JSON 파싱 실패로 fallback 사용)"
        }
        
    except Exception as e:
        print(f"DEBUG: generate_lecture_content failed: {e}", file=sys.stderr, flush=True)
        return {
            "introduction": f"{module.get('title', 'Module')} 학습을 시작합니다.",
            "main_content": "강의 내용 생성 중 오류가 발생했습니다.",
            "examples": [],
            "exercises": [],
            "summary": "오류로 인해 기본 안내만 제공됩니다.",
            "content_sources": [],
            "coverage_note": "강의 생성 실패"
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
        # 스트리밍 버전을 사용하여 진행 상태 공유
        curriculum_data = await generate_with_llm_streaming(
            topic=topic,
            level=params["level"],
            duration_weeks=params["duration_weeks"],
            focus_areas=params["focus_areas"],
            resources=basic_resources,
            session_id=session_id
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
        
        # 모듈에 리소스 추가 (모든 콘텐츠 정보 포함)
        module["resources"] = module_resources  # 전체 정보를 그대로 포함
        
        # 수집된 리소스가 있으면 강의 콘텐츠 생성
        if module_resources.get('resources_with_content', 0) > 0:
            print(f"DEBUG: Generating lecture content for module: {week_title}", file=sys.stderr, flush=True)
            try:
                lecture_content = await generate_lecture_content(module, module_resources)
                module["lecture_content"] = lecture_content
                print(f"DEBUG: Successfully generated lecture content with {len(lecture_content.get('sections', []))} sections", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"DEBUG: Failed to generate lecture content: {e}", file=sys.stderr, flush=True)
                # 강의 생성 실패시에도 커리큘럼은 계속 진행
        else:
            print(f"DEBUG: No content available for lecture generation in module: {week_title}", file=sys.stderr, flush=True)
        
        print(f"DEBUG: Added {len(module_resources.get('videos', []))} videos and {len(module_resources.get('web_links', []))} web links", file=sys.stderr, flush=True)
        print(f"DEBUG: Content coverage: {module_resources.get('content_coverage', 0.0):.2f}", file=sys.stderr, flush=True)
    
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