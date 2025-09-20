from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import json
import os
import time
from datetime import datetime
from contextlib import asynccontextmanager

from agent import MultiMCPAgent
from config import Config
from utils import random_uuid
from servers.user_assessment import save_session
from langchain_neo4j import Neo4jGraph

# 전역 에이전트 (여러 서버 동시 사용)
agent_instance: MultiMCPAgent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global agent_instance
    try:
        print("🚀 Starting multi-MCP agent...")
        
        # 일시적으로 user_assessment 서버만 사용 (테스트용)
        servers = [
            "servers/user_assessment.py",
            "servers/generate_curriculum.py",  # 임시 비활성화
            # "servers/evaluate_user.py"         # 임시 비활성화
        ]
        
        print(f"📋 서버 리스트: {servers}")
        agent_instance = MultiMCPAgent(servers)
        print("🔄 에이전트 인스턴스 생성 완료, 초기화 시작...")
        
        await agent_instance.initialize()
        print("✅ Multi-MCP Agent ready!")
        
    except Exception as e:
        print(f"❌ Startup failed: {e}")
        import traceback
        traceback.print_exc()
    
    yield
    
    # Shutdown
    if agent_instance:
        await agent_instance.cleanup()

app = FastAPI(title="MCP Chat Agent", lifespan=lifespan)

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 정적 파일 설정
app.mount("/static", StaticFiles(directory="static"), name="static")

class ChatRequest(BaseModel):
    message: str
    session_id: str = None

def create_initial_session(session_id: str) -> dict:
    """새로운 세션 초기 데이터 생성 및 저장"""
    initial_session_data = {
        "messages": [],
        "topic": "",
        "constraints": "",
        "goal": "",
        "current_agent": "response",
        "session_id": session_id,
        "completed": False
    }
    save_session(session_id, initial_session_data)
    print(f"💾 세션 파일 저장 완료: {session_id}")
    return initial_session_data

@app.get("/", response_class=HTMLResponse)
async def home(request: Request, response: Response):
    """메인 페이지 - 채팅 UI (세션 생성 및 저장)"""
    # 쿠키에서 세션 ID 확인 또는 새로 생성
    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = random_uuid()[:8]
        # 쿠키 설정 개선: SameSite와 Secure 옵션 추가
        response.set_cookie(
            key="session_id", 
            value=session_id, 
            httponly=False,  # JavaScript에서 접근 가능하도록 변경
            max_age=86400*30,  # 30일
            samesite="lax",    # CSRF 보호
            path="/"           # 모든 경로에서 접근 가능
        )
        print(f"🆕 새 사용자 세션 생성: {session_id}")

        # 세션 파일 즉시 생성
        create_initial_session(session_id)
    else:
        print(f"🔄 기존 세션 복원: {session_id}")
    
    # agent_instance에 세션 ID 설정
    if agent_instance:
        agent_instance.current_session_id = session_id
        
    import time
    timestamp = str(int(time.time()))
    return templates.TemplateResponse("index.html", {"request": request, "session_id": session_id, "timestamp": timestamp})

@app.post("/chat")
async def chat(chat_request: Request):
    """채팅 API - SSE 스트리밍"""
    if not agent_instance:
        return {"error": "Agent not initialized"}
    
    # 요청 바디 파싱
    body = await chat_request.json()
    message = body.get("message", "")
    
    # 세션 ID 가져오기 - 여러 방법 시도
    session_id = None
    
    # 1. 쿠키에서 확인
    session_id = chat_request.cookies.get("session_id")
    if session_id:
        print(f"📋 쿠키에서 세션 ID 가져옴: {session_id}")
    else:
        # 2. 헤더에서 확인
        session_from_header = chat_request.headers.get("X-Session-ID")
        if session_from_header:
            session_id = session_from_header
            print(f"📋 헤더에서 세션 ID 가져옴: {session_id}")
        else:
            # 3. 바디에서 확인
            session_from_body = body.get("session_id")
            if session_from_body:
                session_id = session_from_body
                print(f"📋 바디에서 세션 ID 가져옴: {session_id}")
    
    if not session_id:
        print("⚠️ 세션 ID를 찾을 수 없습니다.")
        print(f"🍪 쿠키: {dict(chat_request.cookies)}")
        print(f"📄 바디: {body}")
    
    # 사용자 메시지 로깅
    print(f"\n👤 사용자: {message}")
    print("-" * 50)
    
    async def generate():
        # 세션 ID 미리 설정
        if session_id:
            agent_instance.current_session_id = session_id
            print(f"🔗 에이전트에 세션 ID 설정: {session_id}")
        
        try:
            async for chunk in agent_instance.chat(message):
                if chunk.get("type") == "message":
                    content = chunk.get("content", "")
                    if content:
                        response_data = {'content': content}
                        
                        # agent.py에서 전달된 프로필 정보 사용
                        if chunk.get("profile"):
                            response_data['profile'] = chunk.get("profile")
                        
                        yield f"data: {json.dumps(response_data)}\n\n"
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            print(f"\n🤖 응답 완료")
            print("=" * 50)
            
        except Exception as e:
            print(f"❌ 오류: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )

@app.post("/clear-chat")
async def clear_chat(request: Request, response: Response):
    """대화 기록 초기화"""
    if not agent_instance:
        return {"error": "Agent not initialized"}

    # 기존 세션 ID 가져오기
    old_session_id = request.cookies.get("session_id")

    # 새로운 세션 ID 생성
    new_session_id = random_uuid()[:8]

    # 기존 세션 파일은 기록 보존을 위해 삭제하지 않음
    if old_session_id:
        print(f"📂 기존 세션 파일 보존: sessions/{old_session_id}.json")
        print(f"🆕 새로운 세션 시작: {new_session_id}")

    # 에이전트 대화 기록 초기화
    agent_instance.clear_conversation()

    # 새로운 세션 ID를 에이전트에 설정
    agent_instance.current_session_id = new_session_id

    # 새로운 세션 파일 생성
    create_initial_session(new_session_id)

    # 새로운 세션 쿠키 설정
    response.set_cookie(
        key="session_id",
        value=new_session_id,
        max_age=86400,  # 24시간
        httponly=False,  # JavaScript에서 접근 가능하도록 설정
        samesite="lax",
        path="/"  # 모든 경로에서 접근 가능
    )

    print(f"🔄 세션 초기화 완료: {old_session_id} → {new_session_id}")
    print(f"🍪 새로운 세션 쿠키 설정: {new_session_id}")

    return {
        "message": "대화 기록이 초기화되었습니다.",
        "old_session_id": old_session_id,
        "new_session_id": new_session_id,
        "success": True
    }

@app.get("/session-debug")
async def session_debug(request: Request):
    """세션 디버그 정보"""
    session_id = request.cookies.get("session_id")
    return {
        "cookies": dict(request.cookies),
        "session_id": session_id,
        "user_agent": request.headers.get("User-Agent", ""),
        "has_session_cookie": "session_id" in request.cookies
    }


@app.get("/api/curriculum/{session_id}")
async def get_curriculum(session_id: str):
    """세션의 생성된 커리큘럼 데이터 조회"""
    if not agent_instance:
        return {"error": "Agent not initialized"}

    try:
        # MCP 도구를 사용하여 커리큘럼 데이터 조회
        tools = await agent_instance.client.get_tools()
        get_curriculum_tool = next((tool for tool in tools if tool.name == "get_curriculum"), None)

        if not get_curriculum_tool:
            return {"error": "get_curriculum 도구를 찾을 수 없습니다"}

        # 커리큘럼 데이터 조회
        result = await get_curriculum_tool.ainvoke({"user_id": session_id})

        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return {"error": "커리큘럼 데이터 파싱 실패"}

        return result

    except Exception as e:
        print(f"❌ 커리큘럼 조회 오류: {e}")
        return {"error": f"커리큘럼 조회 중 오류가 발생했습니다: {str(e)}"}

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """세션 데이터 조회"""
    try:
        session_file = f"sessions/{session_id}.json"
        if os.path.exists(session_file):
            with open(session_file, 'r', encoding='utf-8') as f:
                session_data = json.load(f)
            return session_data
        else:
            return {"error": "세션을 찾을 수 없습니다"}
    except Exception as e:
        print(f"❌ 세션 조회 오류: {e}")
        return {"error": f"세션 조회 중 오류가 발생했습니다: {str(e)}"}

@app.get("/api/progress/{session_id}")
async def get_curriculum_progress(session_id: str):
    """커리큘럼 생성 진행 상황 조회"""
    try:
        progress_file = f"data/progress/{session_id}.json"

        if os.path.exists(progress_file):
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            return progress_data
        else:
            # 파일이 없으면 초기 상태 반환
            return {
                "session_id": session_id,
                "current_phase": "waiting",
                "step_name": "준비 중",
                "message": "커리큘럼 생성을 준비하고 있습니다",
                "progress_percent": 0,
                "updated_at": datetime.now().isoformat(),
                "phase_info": {
                    "step": 1,
                    "total": 5,
                    "name": "대기 중",
                    "description": "커리큘럼 생성을 준비하고 있습니다"
                }
            }
    except Exception as e:
        print(f"❌ 진행 상황 조회 오류: {e}")
        return {
            "error": f"진행 상황 조회 중 오류가 발생했습니다: {str(e)}",
            "session_id": session_id
        }

@app.post("/api/progress/{session_id}/initialize")
async def initialize_curriculum_progress(session_id: str):
    """커리큘럼 생성 진행 상황 초기화"""
    try:
        progress_dir = "data/progress"
        os.makedirs(progress_dir, exist_ok=True)

        progress_file = f"{progress_dir}/{session_id}.json"

        # 초기 진행 상황 데이터
        initial_progress = {
            "session_id": session_id,
            "current_phase": "parameter_analysis",
            "step_name": "커리큘럼 생성 준비",
            "message": "커리큘럼 생성을 준비하고 있습니다",
            "progress_percent": 0,
            "updated_at": datetime.now().isoformat(),
            "phase_info": {
                "step": 1,
                "total": 5,
                "name": "학습 요구사항 분석",
                "description": "커리큘럼 생성을 준비하고 있습니다"
            }
        }

        # 초기 진행 상황 저장
        with open(progress_file, 'w', encoding='utf-8') as f:
            json.dump(initial_progress, f, ensure_ascii=False, indent=2)

        print(f"📊 진행 상황 초기화 완료: {session_id}")
        return {"status": "initialized", "session_id": session_id}

    except Exception as e:
        print(f"❌ 진행 상황 초기화 오류: {e}")
        return {"error": f"진행 상황 초기화 중 오류가 발생했습니다: {str(e)}", "session_id": session_id}


# Neo4j 데이터셋 지도 API 엔드포인트들

def get_neo4j_connection():
    """Neo4j 연결 헬퍼 함수"""
    try:
        graph = Neo4jGraph(
            url=Config.NEO4J_BASE_URL,
            username=Config.NEO4J_USERNAME,
            password=os.getenv("NEO4J_PASSWORD")
        )
        return graph
    except Exception as e:
        print(f"❌ Neo4j 연결 실패: {e}")
        return None


@app.get("/api/neo4j/graph-data")
async def get_neo4j_graph_data():
    """Neo4j 그래프의 모든 노드와 관계 데이터 조회"""
    try:
        graph = get_neo4j_connection()
        if not graph:
            return {"error": "Neo4j 연결 실패"}

        # 모든 노드와 관계 조회 (Procedure 노드 제외) - 명시적 속성 추출
        query = """
        MATCH (n)-[r]->(m)
        WHERE NOT 'Procedure' IN labels(n) AND NOT 'Procedure' IN labels(m)
        RETURN
            id(n) as source_id, labels(n) as source_labels, properties(n) as source_props,
            id(m) as target_id, labels(m) as target_labels, properties(m) as target_props,
            type(r) as rel_type, properties(r) as rel_props
        LIMIT 500
        """

        result = graph.query(query)

        nodes = []
        edges = []
        node_ids = set()

        for record in result:
            # 새로운 쿼리 구조에서 직접 데이터 추출
            source_id = str(record['source_id'])
            source_labels = record['source_labels'] or []
            source_props = record['source_props'] or {}

            target_id = str(record['target_id'])
            target_labels = record['target_labels'] or []
            target_props = record['target_props'] or {}

            rel_type = record['rel_type'] or 'RELATED'
            rel_props = record['rel_props'] or {}

            # 소스 노드 처리
            if source_id not in node_ids:
                nodes.append({
                    "id": source_id,
                    "label": source_props.get('name', source_props.get('title', f"Node {source_id}")),
                    "group": source_labels[0] if source_labels else 'Unknown',
                    "properties": source_props
                })
                node_ids.add(source_id)

            # 타겟 노드 처리
            if target_id not in node_ids:
                nodes.append({
                    "id": target_id,
                    "label": target_props.get('name', target_props.get('title', f"Node {target_id}")),
                    "group": target_labels[0] if target_labels else 'Unknown',
                    "properties": target_props
                })
                node_ids.add(target_id)

            # 관계 처리
            edges.append({
                "from": source_id,
                "to": target_id,
                "label": rel_type,
                "properties": rel_props
            })

        # 고립된 노드들도 조회 (Procedure 제외) - 명시적 속성 추출
        isolated_query = """
        MATCH (n)
        WHERE NOT (n)--() AND NOT 'Procedure' IN labels(n)
        RETURN id(n) as node_id, labels(n) as node_labels, properties(n) as node_props
        LIMIT 100
        """

        isolated_result = graph.query(isolated_query)
        for record in isolated_result:
            node_id = str(record['node_id'])
            node_labels = record['node_labels'] or []
            node_props = record['node_props'] or {}

            if node_id not in node_ids:
                nodes.append({
                    "id": node_id,
                    "label": node_props.get('name', node_props.get('title', f"Node {node_id}")),
                    "group": node_labels[0] if node_labels else 'Unknown',
                    "properties": node_props
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "total_nodes": len(nodes),
            "total_edges": len(edges)
        }

    except Exception as e:
        print(f"❌ Neo4j 그래프 데이터 조회 오류: {e}")
        import traceback
        traceback.print_exc()
        return {"error": f"그래프 데이터 조회 중 오류가 발생했습니다: {str(e)}"}


@app.get("/api/neo4j/search/{query}")
async def search_neo4j_data(query: str):
    """Neo4j 데이터 검색"""
    try:
        graph = get_neo4j_connection()
        if not graph:
            return {"error": "Neo4j 연결 실패"}

        # 노드 검색 쿼리 (Procedure 제외) - 명시적 속성 추출
        search_query = """
        MATCH (n)
        WHERE (toLower(toString(n.name)) CONTAINS toLower($query)
           OR toLower(toString(n.title)) CONTAINS toLower($query)
           OR toLower(toString(n.description)) CONTAINS toLower($query))
           AND NOT 'Procedure' IN labels(n)
        RETURN id(n) as node_id, labels(n) as node_labels, properties(n) as node_props
        LIMIT 50
        """

        result = graph.query(search_query, {"query": query})

        search_results = []
        for record in result:
            node_id = str(record['node_id'])
            node_labels = record['node_labels'] or []
            node_props = record['node_props'] or {}

            search_results.append({
                "id": node_id,
                "label": node_props.get('name', node_props.get('title', f"Node {node_id}")),
                "group": node_labels[0] if node_labels else 'Unknown',
                "properties": node_props
            })

        return {
            "query": query,
            "results": search_results,
            "count": len(search_results)
        }

    except Exception as e:
        print(f"❌ Neo4j 검색 오류: {e}")
        return {"error": f"검색 중 오류가 발생했습니다: {str(e)}"}


@app.get("/api/neo4j/node/{node_id}")
async def get_neo4j_node_details(node_id: str):
    """특정 노드의 상세 정보 및 연결된 노드들 조회"""
    try:
        graph = get_neo4j_connection()
        if not graph:
            return {"error": "Neo4j 연결 실패"}

        # 노드 상세 정보 및 연결된 노드들 조회 - 명시적 속성 추출
        detail_query = """
        MATCH (n)-[r]-(connected)
        WHERE id(n) = $node_id
        RETURN
            id(n) as center_id, labels(n) as center_labels, properties(n) as center_props,
            type(r) as rel_type,
            id(connected) as conn_id, labels(connected) as conn_labels, properties(connected) as conn_props
        """

        result = graph.query(detail_query, {"node_id": int(node_id)})

        node_info = None
        connections = []

        for record in result:
            if node_info is None:
                center_id = str(record['center_id'])
                center_labels = record['center_labels'] or []
                center_props = record['center_props'] or {}

                node_info = {
                    "id": center_id,
                    "label": center_props.get('name', center_props.get('title', f"Node {center_id}")),
                    "group": center_labels[0] if center_labels else 'Unknown',
                    "properties": center_props
                }

            rel_type = record['rel_type'] or 'RELATED'
            conn_id = str(record['conn_id'])
            conn_labels = record['conn_labels'] or []
            conn_props = record['conn_props'] or {}

            connections.append({
                "relationship": rel_type,
                "node": {
                    "id": conn_id,
                    "label": conn_props.get('name', conn_props.get('title', f"Node {conn_id}")),
                    "group": conn_labels[0] if conn_labels else 'Unknown'
                }
            })

        if node_info is None:
            return {"error": "노드를 찾을 수 없습니다"}

        return {
            "node": node_info,
            "connections": connections,
            "connection_count": len(connections)
        }

    except Exception as e:
        print(f"❌ Neo4j 노드 상세 조회 오류: {e}")
        return {"error": f"노드 조회 중 오류가 발생했습니다: {str(e)}"}


@app.get("/api/neo4j/stats")
async def get_neo4j_stats():
    """Neo4j 데이터베이스 통계 정보"""
    try:
        graph = get_neo4j_connection()
        if not graph:
            return {"error": "Neo4j 연결 실패"}

        # 노드 통계 (Procedure 제외)
        node_stats_query = """
        MATCH (n)
        WHERE NOT 'Procedure' IN labels(n)
        RETURN labels(n) as label, count(n) as count
        ORDER BY count DESC
        """

        # 관계 통계 (Procedure 관련 관계 제외)
        rel_stats_query = """
        MATCH (n)-[r]->(m)
        WHERE NOT 'Procedure' IN labels(n) AND NOT 'Procedure' IN labels(m)
        RETURN type(r) as relationship_type, count(r) as count
        ORDER BY count DESC
        """

        node_result = graph.query(node_stats_query)
        rel_result = graph.query(rel_stats_query)

        node_stats = []
        for record in node_result:
            label_data = record.get('label', [])
            if isinstance(label_data, list) and label_data:
                label = label_data[0]
            elif isinstance(label_data, str):
                label = label_data
            else:
                label = 'Unknown'

            node_stats.append({
                "label": label,
                "count": record.get('count', 0)
            })

        rel_stats = []
        for record in rel_result:
            rel_stats.append({
                "type": record.get('relationship_type', 'Unknown'),
                "count": record.get('count', 0)
            })

        # 전체 통계
        total_nodes = sum(stat['count'] for stat in node_stats)
        total_relationships = sum(stat['count'] for stat in rel_stats)

        return {
            "total_nodes": total_nodes,
            "total_relationships": total_relationships,
            "node_types": node_stats,
            "relationship_types": rel_stats
        }

    except Exception as e:
        print(f"❌ Neo4j 통계 조회 오류: {e}")
        return {"error": f"통계 조회 중 오류가 발생했습니다: {str(e)}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=Config.HOST, port=Config.PORT, access_log=False)
