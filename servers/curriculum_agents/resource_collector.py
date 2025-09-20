"""
Resource Collector Agent - 학습 리소스 수집 (병렬 처리)
"""
from typing import List, Dict, Any
import asyncio
import httpx
from bs4 import BeautifulSoup
import re
from urllib.parse import quote
import sys
import traceback

from .base_agent import BaseAgent
from .state import CurriculumState, ProcessingPhase


class ResourceCollectorAgent(BaseAgent):
    """학습 리소스를 수집하는 에이전트"""

    async def execute(self, state: CurriculumState) -> CurriculumState:
        """리소스 수집 실행"""
        try:
            self.safe_update_phase(state, ProcessingPhase.RESOURCE_COLLECTION, "🔍 학습 리소스 수집 중...")

            # 기본 리소스 수집
            basic_resources = await self._search_basic_resources(state["topic"])
            state["basic_resources"] = basic_resources

            # 모듈별 리소스 수집 (병렬 처리)
            if state["detailed_modules"]:
                module_resources = await self._collect_all_module_resources(
                    state["topic"],
                    state["detailed_modules"]
                )
                state["module_resources"] = module_resources

            self.log_debug(f"Collected {len(basic_resources)} basic resources and module-specific resources")

            return state

        except Exception as e:
            return self.handle_error(state, e, "Resource collection failed")

    async def _search_basic_resources(self, topic: str, num_results: int = 10) -> List[Dict[str, str]]:
        """기본 리소스 검색"""
        try:
            search_query = f"{topic} 학습 강의 튜토리얼"
            return await self._search_web_resources(search_query, num_results)
        except Exception as e:
            self.log_debug(f"Basic resource search failed: {e}")
            return []

    async def _collect_all_module_resources(self, topic: str, modules: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """모든 모듈의 리소스를 병렬로 수집"""

        # 병렬 처리를 위한 태스크 생성
        tasks = []
        for module in modules:
            module_topic = f"{topic} {module.get('title', '')}"
            task = self._collect_module_resources(module_topic, module)
            tasks.append(task)

        # 병렬 실행
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 정리
        module_resources = {}
        for i, result in enumerate(results):
            module_key = f"week_{modules[i].get('week', i+1)}"
            if isinstance(result, Exception):
                self.log_debug(f"Module {module_key} resource collection failed: {result}")
                module_resources[module_key] = {"videos": [], "web_links": [], "documents": []}
            else:
                module_resources[module_key] = result

        return module_resources

    async def _collect_module_resources(self, module_topic: str, module: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """개별 모듈의 리소스 수집"""
        week_title = module.get('title', '')

        try:
            # 병렬로 다양한 소스에서 리소스 수집
            tasks = [
                self._search_kmooc_resources(module_topic, week_title),
                self._search_document_resources(module_topic, week_title),  # Pinecone 검색 포함
                self._search_web_resources(f"{module_topic} 강의", 5)
            ]

            kmooc_results, doc_results, web_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 결과 정리 (원본 코드 형식과 동일)
            resources = {
                "videos": kmooc_results if not isinstance(kmooc_results, Exception) else [],
                "web_links": web_results if not isinstance(web_results, Exception) else [],
                "documents": doc_results if not isinstance(doc_results, Exception) else [],
                "total_resources": 0,
                "resources_with_content": 0,
                "content_coverage": 0.0
            }

            # 통계 정보 계산
            total_resources = len(resources["videos"]) + len(resources["web_links"]) + len(resources["documents"])
            resources_with_content = (
                len(resources["videos"]) +  # 비디오는 항상 콘텐츠가 있다고 가정
                len([r for r in resources["web_links"] if r.get('content')]) +
                len([d for d in resources["documents"] if d.get('has_content', False)])
            )

            resources["total_resources"] = total_resources
            resources["resources_with_content"] = resources_with_content
            resources["content_coverage"] = resources_with_content / max(total_resources, 1)

            return resources

        except Exception as e:
            self.log_debug(f"Module resource collection failed for {week_title}: {e}")
            return {"videos": [], "documents": [], "web_links": []}

    async def _search_kmooc_resources(self, topic: str, week_title: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """K-MOOC DB에서 관련 영상을 검색합니다 (Pinecone API 사용)"""
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

            print(f"DEBUG: K-MOOC 검색 시작 - query: {search_query}", file=sys.stderr, flush=True)

            # pinecone_search_kmooc.py 서버가 localhost:8099에서 실행 중이라고 가정
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8099/search",
                    json=search_payload,
                    timeout=10.0
                )

            if response.status_code == 200:
                result = response.json()
                kmooc_videos = []

                print(f"DEBUG: K-MOOC 검색 응답 - 결과 수: {len(result.get('results', []))}", file=sys.stderr, flush=True)

                for item in result.get("results", []):
                    metadata = item.get("metadata", {})
                    if metadata:
                        # Summary 파싱하여 강좌 정보 추출
                        summary = metadata.get("summary", "")
                        parsed_info = self._parse_kmooc_summary(summary)

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

                print(f"DEBUG: K-MOOC 최종 비디오 수: {len(kmooc_videos)}", file=sys.stderr, flush=True)
                return kmooc_videos

            else:
                print(f"DEBUG: K-MOOC 검색 실패 - 상태코드: {response.status_code}", file=sys.stderr, flush=True)
                return []

        except Exception as e:
            print(f"DEBUG: K-MOOC 검색 오류: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            print(f"DEBUG: 스택 트레이스:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
            return []

    def _parse_kmooc_summary(self, summary: str) -> Dict[str, str]:
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

    async def _search_document_resources(self, topic: str, week_title: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """Pinecone DB와 웹에서 병렬로 문서 자료를 검색합니다"""
        # 병렬로 Pinecone과 웹 검색 실행
        tasks = [
            self._search_pinecone_documents(topic, week_title, top_k),
            self._search_web_documents(topic, week_title, top_k)
        ]

        pinecone_results, web_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 결과 병합
        all_documents = []

        # Pinecone 결과 추가
        if not isinstance(pinecone_results, Exception):
            all_documents.extend(pinecone_results)
            print(f"DEBUG: Pinecone에서 {len(pinecone_results)}개 문서 추가", file=sys.stderr, flush=True)
        else:
            print(f"DEBUG: Pinecone 검색 실패: {pinecone_results}", file=sys.stderr, flush=True)

        # 웹 검색 결과 추가
        if not isinstance(web_results, Exception):
            all_documents.extend(web_results)
            print(f"DEBUG: 웹에서 {len(web_results)}개 문서 추가", file=sys.stderr, flush=True)
        else:
            print(f"DEBUG: 웹 검색 실패: {web_results}", file=sys.stderr, flush=True)

        # 중복 제거 및 점수 기준 정렬
        unique_docs = {}
        for doc in all_documents:
            # title과 source를 키로 사용해 중복 제거
            key = f"{doc.get('title', '')}_{doc.get('source', '')}"
            if key not in unique_docs or doc.get('score', 0) > unique_docs[key].get('score', 0):
                unique_docs[key] = doc

        # 점수 기준으로 정렬하고 top_k개만 반환
        sorted_docs = sorted(unique_docs.values(),
                           key=lambda x: x.get('score', 0),
                           reverse=True)

        return sorted_docs[:top_k*2]  # 병렬 검색이므로 좀 더 많은 결과 반환

    async def _search_pinecone_documents(self, topic: str, week_title: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """Pinecone DB에서 관련 PDF/문서 자료를 검색합니다"""
        try:
            # 검색 쿼리 구성
            search_query = f"{topic}"
            if week_title:
                search_query += f" {week_title}"

            search_payload = {
                "query": search_query,
                "top_k": top_k,
                "namespace": "main",  # DEFAULT_NAMESPACE 사용
                "rerank": True,
                "include_metadata": True
            }

            print(f"DEBUG: Pinecone 문서 검색 시작 - query: {search_query}", file=sys.stderr, flush=True)

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

                print(f"DEBUG: Pinecone 문서 검색 응답 - 결과 수: {len(result.get('results', []))}", file=sys.stderr, flush=True)

                for item in result.get("results", []):
                    metadata = item.get("metadata", {})
                    score = item.get("score", 0.0)

                    if metadata and score > 0.5:  # 관련성 임계값
                        # 메타데이터에서 정보 추출
                        preview = metadata.get("preview", "").strip()
                        file_path = metadata.get("file_path", "").strip()
                        folder = metadata.get("folder", "").strip()
                        subdir = metadata.get("subdir", "").strip()
                        page_num = metadata.get("page", "")
                        file_sha1 = metadata.get("file_sha1", "")

                        # 파일명에서 제목 추출
                        doc_title = "PDF 문서"
                        if file_path:
                            # 파일 경로에서 파일명만 추출
                            filename = file_path.split("/")[-1] if "/" in file_path else file_path
                            # 확장자 제거
                            if filename.endswith('.pdf'):
                                filename = filename[:-4]
                            doc_title = filename

                        # 카테고리 정보 (folder 또는 subdir 사용)
                        category = folder or subdir or "기타"

                        # preview가 있으면 이를 주 콘텐츠로 사용
                        doc_content = preview if preview else ""

                        # 설명 생성 (preview 우선, 없으면 기본값)
                        description = preview[:300] + "..." if preview else "문서 미리보기 없음"

                        # 소스 정보 구성
                        source_info = f"{category}/{filename}" if category != "기타" else filename

                        documents.append({
                            "title": doc_title,
                            "description": description,
                            "content": doc_content[:2000],  # preview 내용 확장
                            "preview": preview,  # 원본 preview 저장
                            "source": source_info,
                            "category": category,
                            "file_path": file_path,
                            "file_sha1": file_sha1,
                            "page": page_num,
                            "score": score,
                            "type": "document",
                            "has_content": True if preview else False
                        })

                        print(f"DEBUG: Pinecone 문서 추가 - {doc_title[:30]}... (점수: {score:.3f}, 카테고리: {category})", file=sys.stderr, flush=True)

                print(f"DEBUG: Pinecone 최종 문서 수: {len(documents)}", file=sys.stderr, flush=True)
                return documents

            else:
                print(f"DEBUG: Pinecone 문서 검색 실패 - 상태코드: {response.status_code}", file=sys.stderr, flush=True)
                return []

        except Exception as e:
            print(f"DEBUG: Pinecone 문서 검색 오류: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            print(f"DEBUG: 스택 트레이스:\n{traceback.format_exc()}", file=sys.stderr, flush=True)
            return []

    async def _search_web_documents(self, topic: str, week_title: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """웹에서 문서 자료를 검색합니다"""
        try:
            search_term = f"{topic} {week_title} 문서 PDF" if week_title else f"{topic} 문서 PDF"
            return await self._search_web_resources(search_term, top_k, filter_docs=True)
        except Exception as e:
            print(f"DEBUG: 웹 문서 검색 실패: {e}", file=sys.stderr, flush=True)
            return []

    async def _search_web_resources(self, query: str, num_results: int = 10, filter_docs: bool = False) -> List[Dict[str, str]]:
        """웹 리소스 검색"""
        try:
            encoded_query = quote(query)
            search_url = f"https://search.naver.com/search.naver?query={encoded_query}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(search_url)
                if response.status_code != 200:
                    return []

                soup = BeautifulSoup(response.text, 'html.parser')

                # 다양한 링크 패턴 시도
                link_patterns = [
                    r'<a[^>]*href="([^"]*)"[^>]*class="[^"]*link[^"]*"[^>]*>([^<]*)</a>',
                    r'<a[^>]*class="[^"]*result[^"]*"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>',
                    r'<a[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
                ]

                resources = []
                for pattern in link_patterns:
                    matches = re.findall(pattern, response.text, re.IGNORECASE)

                    for url, title in matches[:num_results]:
                        if not url or not title:
                            continue

                        title = re.sub(r'<[^>]+>', '', title).strip()

                        if filter_docs and not any(ext in url.lower() for ext in ['.pdf', '.doc', '.ppt']):
                            continue

                        if len(title) > 5 and url.startswith('http'):
                            resources.append({
                                "title": title,
                                "url": url,
                                "source": "Web Search"
                            })

                    if resources:
                        break

                return resources[:num_results]

        except Exception as e:
            self.log_debug(f"Web search failed: {e}")
            return []