# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

LearnMate AI는 Model Control Protocol (MCP) 기반의 개인 맞춤형 학습 멘토 시스템입니다. 다중 에이전트 아키텍처를 사용하여 사용자를 평가하고, 맞춤형 커리큘럼을 생성하며, 웹 인터페이스를 통해 AI 기반 멘토링을 제공합니다.

## 주요 명령어

### 애플리케이션 실행
```bash
# 메인 웹 서버 시작
python main.py
# http://localhost:8000 에서 접속

# 개별 MCP 서버 실행 (테스트용)
python servers/user_assessment.py
python servers/generate_curriculum.py
```

### 테스트
```bash
# 커리큘럼 생성 테스트
python test_optimized_curriculum.py

# Python 스크립트로 직접 테스트
python tool1.py  # 커리큘럼 생성 직접 테스트
```

### 의존성 관리
```bash
# 패키지 설치
pip install -r requirements.txt

# 주요 의존성: fastapi, uvicorn, langchain, langchain-openai, langgraph, mcp
```

## 아키텍처 개요

### 다중 에이전트 시스템 흐름
1. **웹 인터페이스** (`main.py`) → SSE 스트리밍이 있는 FastAPI 서버
2. **에이전트 오케스트레이터** (`agent.py`) → 의도 분류 및 MCP 서버 라우팅
3. **MCP 서버** (`servers/`) → 작업별 특화 서비스:
   - `user_assessment.py`: 사용자 프로파일링을 위한 상태 기반 LangGraph 워크플로우
   - `generate_curriculum.py`: 리소스 검색이 포함된 AI 기반 커리큘럼 생성

### 의도 분류 시스템
시스템이 사용자 메시지를 의도에 따라 자동 라우팅:
- `general_chat`: 일반 대화 및 멘토링
- `user_profiling`: 구조화된 데이터 수집 (주제, 제약사항, 목표)
- `generate_curriculum`: 프로필 완성 시 커리큘럼 생성

### 데이터 저장 구조
- **세션 데이터**: `sessions/{session_id}.json`에 개별 JSON 파일
- **커리큘럼**: `data/curriculums.json`에 중앙 집중식 저장
- **진행 상황 추적**: `data/progress.json` 및 `data/daily_plans.json`

### LangGraph 워크플로우 (사용자 평가)
사용자 평가 서버는 정교한 상태 머신 사용:
1. **추출 에이전트**: 구조화된 출력으로 엄격한 정보 추출
2. **응답 에이전트**: 누락된 정보 기반 동적 질문 생성
3. **상태 지속성**: 각 상호작용 후 자동 세션 저장

### 주요 설정 사항
- **LLM 설정** (`config.py`): midm-2.0-mini-q4 모델과 함께 Ollama 사용
- **서버 포트**: 메인 앱 (8000), 사용자 평가 (8001), 커리큘럼 (8002)
- **토큰 제한**: MAX_TOKENS = 30000, TRUNCATION_THRESHOLD = 25000

## 개발 가이드라인

### 다중 에이전트 시스템 수정 시
- 의도 분류 로직은 `agent.py:_classify_intent()`에 위치
- 분류 프롬프트와 핸들러 로직을 업데이트하여 새 의도 추가
- 세션 관리는 `session_id`를 통해 자동 처리

### MCP 서버 작업 시
- 각 서버는 적절한 도구 등록과 함께 MCP 프로토콜 구현 필요
- 새 기능은 `@server.tool()` 데코레이터 사용
- 세션 상태는 `sessions/` 내 파일 기반 저장소로 관리

### 커리큘럼 생성 업데이트 시
- 주요 로직은 `servers/generate_curriculum.py:generate_curriculum_tool()`에 위치
- 파라미터 추출은 구조화된 출력 실패 시 정규식 폴백 사용
- 리소스 검색은 학습 자료를 위해 DuckDuckGo와 통합

### 테스트 고려사항
- 커리큘럼 생성은 항상 `test_optimized_curriculum.py`로 테스트
- 세션 검색은 `/discover_sessions` 엔드포인트로 테스트 가능
- 전체 워크플로우의 엔드투엔드 테스트는 웹 인터페이스 사용