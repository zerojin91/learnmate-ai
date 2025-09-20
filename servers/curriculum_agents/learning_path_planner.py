"""
Learning Path Planner Agent - 전체 학습 경로 분석 및 설계
"""
import asyncio
import json
import os
import re
from typing import Dict, List, Any
from langchain_neo4j import Neo4jGraph
from langchain_openai import ChatOpenAI
from neo4j.time import DateTime
from config import Config
from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class LearningPathPlannerAgent(BaseAgent):
    """전체 학습 경로를 분석하고 설계하는 에이전트"""

    # 클래스 레벨에서 Neo4j 연결 풀링
    _neo4j_graph = None
    _connection_failed = False
    _document_cache = {}  # 문서 콘텐츠 캐싱

    def __init__(self, llm=None):
        # BaseAgent 초기화를 위해 더미 llm이라도 전달해야 함
        if llm is None:
            llm = ChatOpenAI(model="gpt-3.5-turbo", api_key="dummy")
        super().__init__(llm)

        # OpenAI GPT-4o-mini 전용 LLM 인스턴스
        self.openai_llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        # workflow에서 전달되는 llm은 무시하고 OpenAI 사용

        # Neo4j 연결 초기화
        self._ensure_neo4j_connection()

    def _ensure_neo4j_connection(self):
        """Neo4j 연결 확보 (싱글톤 패턴)"""
        if LearningPathPlannerAgent._connection_failed:
            return False

        if LearningPathPlannerAgent._neo4j_graph is None:
            try:
                LearningPathPlannerAgent._neo4j_graph = Neo4jGraph(
                    url=Config.NEO4J_BASE_URL,
                    username=Config.NEO4J_USERNAME,
                    password=os.getenv("NEO4J_PASSWORD")
                )
                self.log_debug("Neo4j 연결 풀 생성 성공")
                return True
            except Exception as e:
                self.log_debug(f"Neo4j 연결 실패: {e}")
                LearningPathPlannerAgent._connection_failed = True
                return False
        return True

    async def _call_openai_llm(self, system_prompt: str, user_prompt: str) -> str:
        """OpenAI GPT-4o-mini를 사용하여 LLM 호출"""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            response = await self.openai_llm.ainvoke(messages)
            return response.content
        except Exception as e:
            self.log_debug(f"OpenAI LLM 호출 오류: {e}")
            # fallback to base agent's LLM
            return await self.call_llm(system_prompt, user_prompt)

    def _convert_neo4j_datetime(self, obj):
        """Neo4j DateTime 객체를 JSON 직렬화 가능한 형태로 변환"""
        if isinstance(obj, DateTime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._convert_neo4j_datetime(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_neo4j_datetime(item) for item in obj]
        else:
            return obj

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """학습 경로 계획 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.LEARNING_PATH_PLANNING, "🧠 학습 경로 분석 중...")

            focus_text = ', '.join(state["focus_areas"]) if state["focus_areas"] else 'General coverage'

            # 1. 기본 학습 경로 분석
            analysis_text = await self._analyze_learning_path(
                topic=state["topic"],
                level=state["level"],
                duration_weeks=state["duration_weeks"],
                focus_areas=focus_text
            )

            # 2. Neo4j 그래프에서 실제 학습 리소스 검색
            graph_curriculum = await self._search_graph_curriculum(
                topic=state["topic"],
                goal=state["goal"],
                level=state["level"]
            )

            # 상태 업데이트
            state["learning_path_analysis"] = analysis_text
            state["graph_curriculum"] = graph_curriculum

            self.log_debug(f"Learning path analysis completed: {len(analysis_text)} characters")
            if graph_curriculum:
                self.log_debug(f"Graph curriculum found: {len(graph_curriculum)} procedures")
            else:
                self.log_debug("No graph curriculum found")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Learning path planning failed")

    async def _analyze_learning_path(self, topic: str, level: str, duration_weeks: int, focus_areas: str) -> str:
        """학습 경로 분석"""

        system_prompt = """당신은 전문 교육 설계자입니다. 학습자의 요구에 맞는 최적의 학습 경로를 분석하고 설계해주세요."""

        user_prompt = f"""다음 학습 요구사항을 분석하여 체계적인 학습 계획을 수립해주세요:

학습 주제: {topic}
학습 레벨: {level}
학습 기간: {duration_weeks}주
포커스 영역: {focus_areas}

먼저 다음을 분석해주세요:
1. 이 주제의 핵심 학습 영역은 무엇인가?
2. {level} 수준에서 시작하여 어떤 순서로 학습해야 하는가?
3. {focus_areas}를 고려할 때 중점을 둬야 할 부분은?
4. {duration_weeks}주 동안 현실적으로 달성 가능한 목표는?

분석 결과를 자세히 설명하고, 전체 학습 로드맵을 제시해주세요."""

        analysis_text = await self._call_openai_llm(system_prompt, user_prompt)
        return analysis_text

    async def _search_graph_curriculum(self, topic: str, goal: str, level: str) -> Dict[str, Any]:
        """Neo4j 그래프에서 학습 커리큘럼 검색"""
        try:
            self.log_debug(f"Starting Neo4j graph search for topic: {topic}")

            # 연결 풀에서 기존 연결 사용
            if not self._ensure_neo4j_connection():
                self.log_debug("Neo4j 연결 사용 불가, fallback 사용")
                return self._create_fallback_graph_curriculum(topic, goal, level)

            graph = LearningPathPlannerAgent._neo4j_graph
            self.log_debug("Using existing Neo4j connection pool")

            # 사용자 프로파일 구성
            user_profile = {
                "주제": topic,
                "목표": goal,
                "시간": "주2시간",  # 기본값
                "수준": level or "초급"
            }

            # 그래프 검색 실행
            curriculum_result = await self._graph_search(graph, user_profile)

            if curriculum_result:
                self.log_debug("Graph search completed successfully")
                return curriculum_result
            else:
                self.log_debug("Graph search returned empty result, using fallback")
                return self._create_fallback_graph_curriculum(topic, goal, level)

        except Exception as e:
            self.log_debug(f"Graph search failed: {e}")
            return self._create_fallback_graph_curriculum(topic, goal, level)

    async def _graph_search(self, graph, user_profile: Dict[str, str]) -> Dict[str, Any]:
        """그래프에서 학습 커리큘럼 검색 (neo4j_search_test.py 기반)"""

        # 캐시된 스킬 목록 사용 (클래스 레벨 캐싱)
        if not hasattr(LearningPathPlannerAgent, '_cached_skills'):
            self.log_debug("스킬 목록 캐싱 중...")
            # 사용 가능한 스킬 목록 가져오기
            skills_query = """
            MATCH (s:Skill)
            RETURN s.name as name, s.keywords as keywords, s.category as category, s.description as description
            ORDER BY s.name
            """

            try:
                skills_result = await asyncio.to_thread(graph.query, skills_query)
                LearningPathPlannerAgent._cached_skills = skills_result
                self.log_debug(f"스킬 목록 캐싱 완료: {len(skills_result)}개")
            except Exception as e:
                self.log_debug(f"스킬 목록 가져오기 오류: {e}")
                return None
        else:
            skills_result = LearningPathPlannerAgent._cached_skills
            self.log_debug(f"캐시된 스킬 목록 사용: {len(skills_result)}개")

        # 스킬 정보를 정리
        skills_context = ""
        skills_list = []
        for i, skill in enumerate(skills_result, 1):
            skill_name = skill['name']
            skills_list.append(skill_name)
            skills_context += f"'{skill_name}'\n"

        self.log_debug(f"사용 가능한 스킬 개수: {len(skills_list)}개")

        # 학습 절차 생성을 위한 프롬프트
        prompt = f"""
사용자 프로파일을 분석하여 학습 절차를 생성해주세요.

사용자 프로파일:
- 주제: {user_profile['주제']}
- 목표: {user_profile['목표']}
- 시간: {user_profile['시간']}
- 수준: {user_profile['수준']}

=== 사용 가능한 스킬 목록 (총 {len(skills_list)}개) ===
{skills_context}

=== 절대적 제약 조건 ===
**중요: 스킬명은 반드시 위 목록에서 따옴표 안의 내용을 정확하게 복사해서 사용하세요**
1. 위에 나열된 스킬명을 한 글자도 바꾸지 말고 따옴표 안의 내용을 정확히 복사해서 사용하세요
2. 스킬명의 대소문자, 공백, 특수문자, 한글/영어 모두 정확히 일치시켜야 합니다
3. 존재하지 않는 스킬명을 임의로 만들거나 수정하지 마세요
4. 반드시 위 목록에 있는 스킬명만 사용하세요!

=== 작업 요구사항 ===
1. 사용자의 목표와 수준에 맞는 3-7개의 학습 절차 생성
2. 각 절차별로 관련 스킬 3-5개 선택
3. 절차는 논리적 순서로 배열
4. 수준에 맞는 적절한 난이도로 구성

=== 출력 형식 ===
반드시 아래 JSON 형식으로만 출력하세요:
{{
    "절차1": {{
        "title": "구체적인 학습 단계 제목",
        "skills": ["스킬목록에_있는_스킬명1", "스킬목록에_있는_스킬명2", "스킬목록에_있는_스킬명3"]
    }},
    "절차2": {{
        "title": "구체적인 학습 단계 제목",
        "skills": ["스킬목록에_있는_스킬명4", "스킬목록에_있는_스킬명5"]
    }}
}}

⚠️ 경고: 목록에 없는 스킬명을 사용하면 오류가 발생합니다. 반드시 위 목록의 스킬명을 정확히 복사하여 사용하세요.

JSON만 출력하고 다른 설명이나 주석은 절대 포함하지 마세요.
"""

        # LLM 호출 및 검증 재시도 로직
        max_retries = 3
        learning_path = None

        for attempt in range(max_retries):
            try:
                self.log_debug(f"학습 절차 생성 시도 ({attempt + 1}/{max_retries})...")

                # LLM 호출하여 학습 절차 생성
                response = await self._call_openai_llm(
                    "당신은 교육과정 설계 전문가입니다. 주어진 스킬 목록을 바탕으로 체계적인 학습 절차를 생성해주세요.",
                    prompt
                )

                # 응답 정리
                content = response.strip()
                if content.startswith('```json'):
                    content = content[7:]
                if content.startswith('```'):
                    content = content[3:]
                if content.endswith('```'):
                    content = content[:-3]
                content = content.strip()

                # JSON 파싱
                parsed_json = json.loads(content)

                # 구조 검증
                self._validate_learning_path_structure(parsed_json)
                self._validate_skill_names(parsed_json, skills_list)

                learning_path = parsed_json
                self.log_debug("학습 절차 생성 성공!")
                break

            except json.JSONDecodeError as e:
                self.log_debug(f"시도 {attempt + 1} 실패: JSON 파싱 오류: {e}")
            except ValueError as e:
                self.log_debug(f"시도 {attempt + 1} 실패: 검증 실패: {e}")
            except Exception as e:
                self.log_debug(f"시도 {attempt + 1} 실패: 예상치 못한 오류: {e}")

            if attempt < max_retries - 1:
                await asyncio.sleep(2)

        if learning_path is None:
            self.log_debug(f"최대 재시도 ({max_retries}회) 후에도 학습 절차 생성에 실패했습니다.")
            return None

        self.log_debug(f"학습 절차 생성 완료: {len(learning_path)}개 절차")

        # 문서 및 전문가 정보 수집
        enriched_learning_path = await self._enrich_with_documents_and_experts(graph, learning_path)

        return enriched_learning_path

    async def _enrich_with_documents_and_experts(self, graph, learning_path: Dict) -> Dict[str, Any]:
        """학습 절차에 문서와 전문가 정보 추가 (배치 처리 최적화)"""

        # 모든 스킬 이름 수집
        all_skills = []
        for procedure_data in learning_path.values():
            all_skills.extend(procedure_data['skills'])

        # 배치로 모든 스킬의 문서 정보 가져오기
        batch_skill_to_doc_query = """
        MATCH (s:Skill)<-[:COVERS]-(d:Document)
        WHERE s.name IN $skill_names
           OR ANY(skill IN $skill_names WHERE s.name CONTAINS skill OR s.keywords CONTAINS skill)
        RETURN s, d
        """

        try:
            self.log_debug(f"배치로 {len(all_skills)}개 스킬의 문서 정보 조회 중...")
            batch_docs_result = await asyncio.to_thread(graph.query, batch_skill_to_doc_query, {"skill_names": all_skills})
            self.log_debug(f"배치 조회 완료: {len(batch_docs_result)}개 결과")
        except Exception as e:
            self.log_debug(f"배치 조회 실패: {e}")
            batch_docs_result = []

        # 스킬별로 결과 그룹화
        skill_docs_map = {}
        for record in batch_docs_result:
            skill_name = record['s']['name']
            if skill_name not in skill_docs_map:
                skill_docs_map[skill_name] = []
            skill_docs_map[skill_name].append(record)

        async def process_skill(skill_name: str):
            """단일 스킬에 대한 문서와 전문가 정보를 가져옵니다."""
            self.log_debug(f"스킬 처리: {skill_name}")

            skill_data = {
                "skill_info": {},
                "documents": {}
            }

            # 배치 결과에서 해당 스킬 찾기
            skill_docs_result = []
            for mapped_skill, records in skill_docs_map.items():
                if (skill_name == mapped_skill or
                    skill_name in mapped_skill or
                    mapped_skill in skill_name):
                    skill_docs_result.extend(records)
                    break

            try:
                if not skill_docs_result:
                    self.log_debug(f"    -> 문서 0개 발견")
                    return skill_name, skill_data

                first_result = skill_docs_result[0]
                skill_data["skill_info"] = self._convert_neo4j_datetime({
                    "name": first_result['s']['name'],
                    "category": first_result['s'].get('category', ''),
                    "description": first_result['s'].get('description', ''),
                    "keywords": first_result['s'].get('keywords', ''),
                    "difficulty": first_result['s'].get('difficulty', ''),
                    "importance_score": first_result['s'].get('importance_score', '')
                })

                async def get_experts_for_doc(doc_record):
                    doc_id = doc_record['d']['doc_id']
                    doc_title = doc_record['d']['title']
                    doc_info = self._convert_neo4j_datetime({
                        "doc_id": doc_id,
                        "title": doc_title,
                        "department": doc_record['d'].get('department', ''),
                        "document_type": doc_record['d'].get('document_type', ''),
                        "target_audience": doc_record['d'].get('target_audience', ''),
                        "difficulty_level": doc_record['d'].get('difficulty_level', ''),
                        "estimated_time": doc_record['d'].get('estimated_time', ''),
                        "confidential_level": doc_record['d'].get('confidential_level', ''),
                        "folder_path": doc_record['d'].get('folder_path', ''),
                        "created_date": doc_record['d'].get('created_date', ''),
                        "updated_date": doc_record['d'].get('updated_date', ''),
                        "experts": {}
                    })

                    # 문서 콘텐츠 읽기
                    if doc_title:
                        content = self._read_document_content_by_title(doc_title)
                        if content:
                            doc_info["content"] = content
                            doc_info["content_length"] = len(content)
                        else:
                            doc_info["content"] = ""
                            doc_info["content_length"] = 0

                    doc_to_expert_query = """
                    MATCH (d:Document)<-[:AUTHORED]-(p:Person)
                    WHERE d.doc_id = $doc_id
                    RETURN p
                    """
                    experts_result = await asyncio.to_thread(graph.query, doc_to_expert_query, {"doc_id": doc_id})

                    for expert_record in experts_result:
                        expert_name = expert_record['p']['name']
                        doc_info["experts"][expert_name] = self._convert_neo4j_datetime({
                            "name": expert_name,
                            "department": expert_record['p'].get('department', ''),
                            "role": expert_record['p'].get('role', ''),
                            "expertise": expert_record['p'].get('expertise', ''),
                            "updated_date": expert_record['p'].get('updated_date', '')
                        })
                    return doc_id, doc_info

                expert_tasks = [get_experts_for_doc(record) for record in skill_docs_result]
                document_results = await asyncio.gather(*expert_tasks)

                for doc_id, doc_info in document_results:
                    skill_data["documents"][doc_id] = doc_info

                self.log_debug(f"    -> 문서 {len(skill_data['documents'])}개 발견")

            except Exception as e:
                self.log_debug(f"    -> 오류 발생: {e}")
                skill_data["error"] = str(e)

            return skill_name, skill_data

        async def process_procedure(procedure_key, procedure_data):
            self.log_debug(f"절차 처리: {procedure_key} - {procedure_data['title']}")

            skill_tasks = [process_skill(skill_name) for skill_name in procedure_data['skills']]
            processed_skills = await asyncio.gather(*skill_tasks)

            enriched_procedure = {
                "title": procedure_data['title'],
                "skills": dict(processed_skills)
            }

            self.log_debug(f"  {procedure_key} 완료!")
            return procedure_key, enriched_procedure

        procedure_tasks = [
            process_procedure(key, data) for key, data in learning_path.items()
        ]

        processed_procedures = await asyncio.gather(*procedure_tasks)

        enriched_learning_path = dict(processed_procedures)

        # 전체 결과에 DateTime 변환 적용
        enriched_learning_path = self._convert_neo4j_datetime(enriched_learning_path)

        self.log_debug("학습 커리큘럼 생성 완료")
        return enriched_learning_path

    def _validate_learning_path_structure(self, data: Dict) -> None:
        """학습 경로 구조 검증"""
        if not isinstance(data, dict):
            raise ValueError("결과는 딕셔너리여야 합니다")

        for key, value in data.items():
            if not key.startswith('절차'):
                raise ValueError(f"키는 '절차'로 시작해야 합니다: {key}")

            if 'title' not in value or 'skills' not in value:
                raise ValueError(f"{key}에 필수 필드가 없습니다")

            if not isinstance(value['skills'], list):
                raise ValueError(f"{key}의 'skills'는 리스트여야 합니다")

    def _validate_skill_names(self, learning_path: Dict, available_skills: List[str]) -> None:
        """선택된 스킬명이 실제 DB에 존재하는지 검증"""
        available_skills_set = set(available_skills)

        for procedure_key, procedure_data in learning_path.items():
            for skill_name in procedure_data['skills']:
                if skill_name not in available_skills_set:
                    self.log_debug(f"경고: '{skill_name}'은 DB에 존재하지 않는 스킬입니다 ({procedure_key})")
                    raise ValueError(f"존재하지 않는 스킬: {skill_name}")


    def _create_fallback_graph_curriculum(self, topic: str, goal: str, level: str) -> Dict[str, Any]:
        """Neo4j 실패 시 기본 graph_curriculum 생성"""
        self.log_debug("Creating fallback graph curriculum")

        # 기본적인 학습 절차 생성
        fallback_curriculum = {
            "절차1": {
                "title": f"{topic} 기초 이해",
                "skills": {
                    f"{topic} 기초": {
                        "skill_info": {
                            "name": f"{topic} 기초",
                            "category": "기초",
                            "description": f"{topic}의 기본 개념과 원리 학습",
                            "keywords": [topic, "기초", "개념"],
                            "difficulty": level,
                            "importance_score": 8
                        },
                        "documents": {
                            "basic_doc": {
                                "doc_id": "fallback_basic",
                                "title": f"{topic} 기초 학습 가이드",
                                "department": "교육",
                                "document_type": "guide",
                                "target_audience": f"{topic} 학습자",
                                "difficulty_level": level,
                                "estimated_time": 120,
                                "experts": {
                                    "교육전문가": {
                                        "name": "교육전문가",
                                        "department": "교육",
                                        "role": "전문가",
                                        "expertise": f"{topic} 교육 및 컨설팅"
                                    }
                                }
                            }
                        }
                    }
                }
            },
            "절차2": {
                "title": f"{topic} 실습 및 응용",
                "skills": {
                    f"{topic} 실습": {
                        "skill_info": {
                            "name": f"{topic} 실습",
                            "category": "실습",
                            "description": f"{topic}을 활용한 실제 프로젝트 수행",
                            "keywords": [topic, "실습", "프로젝트"],
                            "difficulty": level,
                            "importance_score": 9
                        },
                        "documents": {
                            "practice_doc": {
                                "doc_id": "fallback_practice",
                                "title": f"{topic} 실습 프로젝트 가이드",
                                "department": "교육",
                                "document_type": "project",
                                "target_audience": f"{topic} 학습자",
                                "difficulty_level": level,
                                "estimated_time": 180,
                                "experts": {
                                    "프로젝트매니저": {
                                        "name": "프로젝트매니저",
                                        "department": "교육",
                                        "role": "매니저",
                                        "expertise": f"{topic} 프로젝트 관리"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        return fallback_curriculum

    def _read_document_content_by_title(self, title: str, docs_directory: str = None) -> str:
        """
        문서 제목을 기반으로 docs 디렉토리에서 해당 JSON 파일을 찾아 콘텐츠를 읽어오는 함수 (캐싱)

        Args:
            title (str): 문서 제목 (예: "MES운영매뉴얼_2024하반기")
            docs_directory (str): 문서가 저장된 디렉토리 경로

        Returns:
            str: 파일 내용 또는 오류 메시지
        """
        if docs_directory is None:
            docs_directory = "/Users/jinwoo/Documents/project/2025_kt_intelligence/learnmate-ai/docs"

        # 캐시 확인
        if title in LearningPathPlannerAgent._document_cache:
            self.log_debug(f"캐시된 문서 사용: '{title}'")
            return LearningPathPlannerAgent._document_cache[title]

        self.log_debug(f"문서 콘텐츠 읽기 시도: '{title}'")

        if not title:
            return ""

        # 제목에 확장자가 없으면 .json을 추가
        if not title.endswith('.json'):
            filename = f"{title}.json"
        else:
            filename = title

        file_path = os.path.join(docs_directory, filename)

        try:
            # JSON 파일 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # 캐시에 저장
            LearningPathPlannerAgent._document_cache[title] = content
            self.log_debug(f"파일 읽기 성공! (크기: {len(content)} 문자) - 캐시에 저장")
            return content

        except FileNotFoundError:
            # 정확한 파일명을 찾을 수 없는 경우, 유연한 검색
            try:
                def normalize_string(s):
                    """특수문자, 공백, 확장자를 제거하고 소문자로 변환"""
                    # 확장자 제거
                    if s.endswith('.json'):
                        s = s[:-5]
                    # 특수문자와 공백 제거, 소문자 변환
                    return re.sub(r'[^가-힣a-zA-Z0-9]', '', s).lower()

                available_files = os.listdir(docs_directory)
                normalized_title = normalize_string(title)

                # 1단계: 공백 제거해서 정확 매칭
                title_no_space = title.replace(' ', '')
                if not title_no_space.endswith('.json'):
                    title_no_space += '.json'

                exact_match_no_space = os.path.join(docs_directory, title_no_space)
                if os.path.exists(exact_match_no_space):
                    with open(exact_match_no_space, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 캐시에 저장
                    LearningPathPlannerAgent._document_cache[title] = content
                    self.log_debug(f"공백 제거 매칭으로 파일 '{title_no_space}' 읽기 성공! - 캐시에 저장")
                    return content

                # 2단계: 유연한 문자열 포함 검색
                matches = []
                for file in available_files:
                    if file.endswith('.json'):
                        normalized_filename = normalize_string(file)

                        # 양방향 포함 검색
                        if normalized_title in normalized_filename or normalized_filename in normalized_title:
                            matches.append((file, 'exact_contain'))
                        # 부분 일치 검색
                        elif len(normalized_title) > 3 and normalized_title[:4] in normalized_filename:
                            matches.append((file, 'partial_match'))

                # 3단계: 키워드 기반 검색
                if not matches:
                    title_words = [word for word in re.findall(r'[가-힣a-zA-Z0-9]+', title) if len(word) > 1]
                    for file in available_files:
                        if file.endswith('.json'):
                            normalized_filename = normalize_string(file)
                            # 제목의 키워드 중 하나라도 파일명에 포함되면 매칭
                            if any(normalize_string(word) in normalized_filename for word in title_words):
                                matches.append((file, 'keyword_match'))

                if matches:
                    # 매칭 우선순위
                    matches.sort(key=lambda x: {'exact_contain': 0, 'partial_match': 1, 'keyword_match': 2}[x[1]])

                    # 가장 좋은 매치 선택
                    best_match_file = matches[0][0]
                    similar_path = os.path.join(docs_directory, best_match_file)
                    with open(similar_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    # 캐시에 저장
                    LearningPathPlannerAgent._document_cache[title] = content
                    self.log_debug(f"유사한 파일 '{best_match_file}' 읽기 성공! - 캐시에 저장")
                    return content

                self.log_debug(f"파일을 찾을 수 없음: {file_path}")
                return ""

            except Exception as e:
                self.log_debug(f"디렉토리 검색 중 오류: {e}")
                return ""

        except json.JSONDecodeError as e:
            self.log_debug(f"JSON 파일 형식 오류: {e}")
            return ""
        except Exception as e:
            self.log_debug(f"파일 읽기 오류: {e}")
            return ""
