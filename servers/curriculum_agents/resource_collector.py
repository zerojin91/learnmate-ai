"""
Resource Collector Agent - 학습 리소스 수집 (병렬 처리)
"""
from typing import List, Dict, Any
import asyncio
import httpx
from bs4 import BeautifulSoup
import re
from urllib.parse import quote

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
                self._search_document_resources(module_topic, week_title),
                self._search_web_resources(f"{module_topic} 강의", 5)
            ]

            kmooc_results, doc_results, web_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 결과 정리
            resources = {
                "videos": kmooc_results if not isinstance(kmooc_results, Exception) else [],
                "documents": doc_results if not isinstance(doc_results, Exception) else [],
                "web_links": web_results if not isinstance(web_results, Exception) else []
            }

            return resources

        except Exception as e:
            self.log_debug(f"Module resource collection failed for {week_title}: {e}")
            return {"videos": [], "documents": [], "web_links": []}

    async def _search_kmooc_resources(self, topic: str, week_title: str = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """K-MOOC에서 리소스 검색"""
        try:
            search_term = f"{topic} {week_title}" if week_title else topic
            encoded_query = quote(search_term.replace(" ", "+"))

            url = f"https://www.kmooc.kr/courses?search_query={encoded_query}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code != 200:
                    return []

                soup = BeautifulSoup(response.text, 'html.parser')
                course_items = soup.find_all('article', class_='course-item') or soup.find_all('div', class_='course')

                resources = []
                for item in course_items[:top_k]:
                    try:
                        title_elem = item.find('h3') or item.find('h2') or item.find(['h1', 'h4', 'h5'])
                        title = title_elem.get_text(strip=True) if title_elem else "제목 없음"

                        link_elem = item.find('a')
                        link = f"https://www.kmooc.kr{link_elem.get('href')}" if link_elem and link_elem.get('href') else ""

                        summary_elem = item.find('p') or item.find('div', class_='description')
                        summary = summary_elem.get_text(strip=True) if summary_elem else ""

                        if title and link:
                            resources.append({
                                "title": title,
                                "url": link,
                                "summary": summary,
                                "source": "K-MOOC",
                                "type": "video_course"
                            })

                    except Exception as e:
                        self.log_debug(f"Error parsing K-MOOC item: {e}")
                        continue

                return resources

        except Exception as e:
            self.log_debug(f"K-MOOC search failed: {e}")
            return []

    async def _search_document_resources(self, topic: str, week_title: str = None, top_k: int = 3) -> List[Dict[str, Any]]:
        """문서 리소스 검색"""
        try:
            search_term = f"{topic} {week_title} 문서 PDF" if week_title else f"{topic} 문서 PDF"
            return await self._search_web_resources(search_term, top_k, filter_docs=True)
        except Exception as e:
            self.log_debug(f"Document search failed: {e}")
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