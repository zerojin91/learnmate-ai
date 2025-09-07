# 🎯 MCP 기반 학습 평가 시스템 개발 로그

## 📅 작업 일자: 2024-09-06 → 2025-09-07 (업데이트)

## 🎯 프로젝트 목표
사용자와 대화하며 학습 플랜을 짜는 agent 개발 중, 특히 **사용자 평가** 단계에 집중
- 전체 순서: 사용자 평가 → 학습 DB 기반 커리큘럼 생성
- 현재 단계: MCP(Model Context Protocol) 기반 tool calling 방식으로 구현

## 🔧 사용 기술 스택
- **LLM**: Ollama midm-2.0:base (tool calling 지원)
- **Framework**: MCP + LangChain + LangGraph
- **에이전트**: create_react_agent (ReAct 패턴)
- **통신**: stdio를 통한 MCP 프로토콜

## 📂 프로젝트 구조
```
learnmate-ai/
├── servers/
│   ├── user_assessment.py              # 기존 복잡한 5단계 평가 서버
│   └── assessment_engine/              # 평가 엔진 (topic_assessor, goal_assessor 등)
├── topic_assessment/                   # 🆕 단순화된 주제 파악 시스템
│   ├── topic_mcp_server.py            # MCP 서버 (identify_learning_topic 도구)
│   ├── simple_topic_client.py         # 대화형 클라이언트
│   └── test_topic.py                  # 테스트 스크립트
├── interactive_assessment_client.py    # 기존 복잡한 클라이언트 (문제 있음)
├── conversation_controller.py          # 기존 대화 플로우 컨트롤러
├── mcp_basic_example.py               # MCP 학습용 예제 코드
└── utils.py                           # LangGraph 유틸리티
```

## 🚨 발견된 주요 문제들

### 1. **복잡한 다중 Tool Calling 문제**
- **기존 시스템**: `start_assessment` → `assess_user` → `confirm_and_proceed` (3개 도구)
- **문제점**: 
  - 복잡한 상태 관리 필요
  - 에이전트가 빈 응답(`AIMessageChunk(content='')`) 생성
  - 도구 응답을 자연스러운 텍스트로 변환하는 과정에서 실패

### 2. **에이전트 응답 파싱 이슈**
```python
# 문제: 에이전트가 도구 결과를 받은 후 빈 응답 생성
response = {'node': 'agent', 'content': AIMessageChunk(content='')}

# 원인: ReAct 에이전트의 응답 생성 단계에서 실패
# tools 노드: 정상적인 JSON 응답 ✅
# agent 노드: 빈 content로 응답 ❌
```

### 3. **MCP 응답 구조 파악**
```python
# MCP 도구 직접 호출 결과
result.content = [TextContent(type='text', text='{"topic": "파이썬", ...}')]

# 올바른 파싱 방법
json_text = result.content[0].text  # ✅
json.loads(json_text)

# 잘못된 파싱 (에러 발생)
json.loads(result.content)  # ❌ list 타입
```

## ✅ 해결 과정

### 1단계: MCP 기본 개념 학습
- **파일**: `mcp_basic_example.py` 
- **학습 내용**: 
  - MCP Server ↔ Client ↔ LangChain Agent 구조
  - `@mcp.tool()` 데코레이터 사용법
  - stdio 통신을 통한 MCP 프로토콜

### 2단계: 문제 단순화 - Topic만 파악
- **기존**: 5단계 평가 (topic → goal → time → budget → level)
- **개선**: 주제 파악만 집중하는 단일 도구
- **장점**: 복잡성 제거, 디버깅 용이, 확장성 확보

### 3단계: 단일 Tool 구현
```python
@mcp.tool()
def identify_learning_topic(user_message: str) -> dict:
    """사용자 메시지에서 학습 주제 파악"""
    return {
        "topic": "파이썬 프로그래밍" | null,
        "confidence": 0.8,  # 0.0 ~ 1.0
        "is_clear": true | false,
        "clarification_question": "질문" | null
    }
```

## 🎯 현재 상태 (2025-09-07 업데이트)

### ✅ 완료된 작업

#### 1️⃣ 단일 도구 시스템 → 다중 도구 시스템 진화
- **기존**: `identify_learning_topic` 하나로 모든 평가
- **개선**: 4개 독립 도구로 분리
  - `assess_topic`: 학습 주제 파악
  - `assess_goal`: 학습 목적 파악  
  - `assess_time`: 학습 시간 계획 파악
  - `assess_budget`: 학습 예산 파악

#### 2️⃣ 순차적 평가 시스템 구현
- **상태 관리**: `assessment_state`로 각 단계 confirmed 여부 추적
- **순서 강제**: topic → goal → time → budget 순으로만 진행 가능
- **진행률 표시**: 25% → 50% → 75% → 100% 시각적 피드백

#### 3️⃣ 사용자 확인 시스템 구현
- **문제**: 시스템이 자동으로 다음 단계 진행 (사용자 동의 없이)
- **해결**: `confirm_and_proceed` 도구 + 명시적 사용자 확인 프로세스
- **플로우**: 
  1. 평가 도구가 confidence >= 0.8이면 확정 질문
  2. 사용자가 "네/확정" → `confirm_and_proceed` 호출
  3. 다음 단계 자동 시작

#### 4️⃣ LLM 프롬프트 최적화
- **문제**: confidence >= 0.8인데도 계속 세분화 질문
- **해결**: 강제 확정 규칙 + 금지 단어 명시
  ```
  confidence >= 0.8이면 **무조건** next_action = "need_user_confirmation"
  금지: "구체적으로", "어떤 분야", "마케팅/금융/IT" 등
  ```

### 🔧 테스트 결과 (실제 대화 테스트 완료)
```bash
# TCP 모드 서버 실행
python topic_mcp_server.py --tcp

# 다른 터미널에서 클라이언트 실행  
python tcp_topic_client.py

# 성공적인 대화 플로우:
👤 > 개발자가 되고 싶어
🤖 구체적으로 어떤 개발 분야에 관심이 있으신가요?

👤 > 데이터분석 하고 싶어  
🤖 주제를 '데이터분석'으로 확정하고 다음 단계로 넘어가시겠습니까?

👤 > 좋아
✅ topic 확정 → GOAL 단계 자동 시작

👤 > 취업하고 싶어
❌ 문제 발견: confidence 0.9인데 세분화 질문 발생 (수정 완료)
```

### 🐛 발견 및 해결된 문제들

#### 1️⃣ 자동 확정 문제
- **문제**: 시스템이 사용자 동의 없이 자동으로 다음 단계 진행
- **해결**: 명시적 사용자 확인 후에만 `confirmed = true` 설정

#### 2️⃣ 무한 세분화 질문 루프
- **문제**: LLM이 confidence >= 0.8인데도 계속 "더 구체적으로" 질문
- **해결**: 프롬프트에 강제 규칙 + 예시 강화

#### 3️⃣ 다음 단계 자동 시작 문제  
- **문제**: topic 확정 후 goal 단계가 빈 화면
- **해결**: `start_next_stage()` 메서드로 자동 질문 생성

#### 4️⃣ 일관성 없는 확정 로직
- **문제**: assess_topic만 확정 로직, 나머지는 구 버전
- **해결**: 모든 도구를 통일된 확정 패턴으로 업데이트

## 💡 핵심 학습 내용

### MCP의 핵심 개념
```python
# 1. 서버: 도구 제공
@mcp.tool()
def my_tool(param: str) -> dict:
    return {"result": "value"}

# 2. 클라이언트: 도구 사용  
result = await session.call_tool("my_tool", {"param": "value"})

# 3. LangChain 통합: 에이전트가 자동으로 도구 선택
tools = await load_mcp_tools(session)
agent = create_react_agent(llm, tools)
```

### 디버깅 팁
1. **MCP 응답 구조**: `result.content[0].text`로 실제 텍스트 추출
2. **에이전트 vs 직접 호출**: 문제 격리를 위해 도구 직접 호출로 테스트
3. **JSON 파싱**: MCP 응답이 리스트 형태임을 고려

## 🚀 다음 단계 계획

### ✅ 완료된 목표들 (2025-09-07)
1. ~~`simple_topic_client.py` 완전 테스트~~ → `tcp_topic_client.py`로 TCP 모드 테스트 완료
2. ~~에이전트 빈 응답 문제 해결~~ → 다중 도구 시스템으로 해결
3. ~~goal 파악 도구 추가 구현~~ → 4개 독립 도구 모두 완성
4. ~~5단계 평가 시스템을 단순한 단일 도구들로 재구성~~ → 완료
5. ~~각 단계별 독립적인 MCP 도구 완성~~ → 완료
6. ~~통합된 클라이언트로 전체 플로우 구현~~ → 완료

### 🔄 다음 작업 우선순위 (내일부터)

#### 1️⃣ 즉시 테스트 (최우선)
- **Goal**: 수정된 assess_goal 프롬프트 테스트
- **확인사항**: "취업하고 싶어" → confidence 0.9 → 확정 질문 (세분화 질문 X)
- **명령어**: 
  ```bash
  cd topic_assessment
  python topic_mcp_server.py --tcp  # 터미널 1
  python tcp_topic_client.py       # 터미널 2
  ```

#### 2️⃣ 전체 플로우 검증  
- **시나리오**: Topic → Goal → Time → Budget 전체 대화 완주
- **확인사항**: 각 단계에서 올바른 확정 질문 생성 여부

#### 3️⃣ 시스템 완성도 향상
1. **에러 처리 강화**: JSON 파싱 실패, 네트워크 오류 등
2. **사용자 경험 개선**: 더 자연스러운 대화 흐름
3. **로깅 시스템**: 디버깅을 위한 상세 로그

#### 4️⃣ 확장 및 통합  
1. **레벨 평가 추가**: assess_level 도구 구현
2. **학습 계획 생성**: 평가 완료 후 커리큘럼 제안
3. **데이터베이스 연동**: 평가 결과 저장 및 관리

## 📝 중요한 명령어

### 환경 설정
```bash
conda activate TK
cd /Users/lgrnd/learnmate-ai/topic_assessment
```

### 테스트 실행 (2025-09-07 업데이트)
```bash
# 📝 단일 도구 직접 테스트 (구버전)
python test_topic.py

# 🚀 TCP 모드 다중 도구 테스트 (현재 주력)
python topic_mcp_server.py --tcp    # 터미널 1: 서버 실행
python tcp_topic_client.py          # 터미널 2: 클라이언트 실행

# 📚 stdio 모드 다중 도구 테스트
python simple_topic_client.py       # 내장 서버 자동 실행

# 🎓 MCP 기본 예제 학습
cd .. && python mcp_basic_example.py
```

### Ollama 서버 확인
```bash
ollama list  # 모델 확인
ollama run midm-2.0:base  # 모델 실행 (tool calling 지원)
```

---

## 📌 핵심 메모 (2025-09-07 업데이트)

### 🎯 설계 철학
- **단순함이 최고**: 복잡한 단일 도구보다 단순한 다중 도구가 안정적
- **사용자 중심**: 시스템이 자동 판단하지 않고 반드시 사용자 확인 요청
- **순차적 진행**: 각 단계가 완전히 확정된 후에만 다음 단계 진행
- **명확한 피드백**: 진행률, 확정 상태 등 시각적 표시

### 🔧 기술적 교훈
- **MCP 프로토콜**: LLM과 외부 도구 간의 표준 통신 방식
- **상태 관리**: `assessment_state`로 전역 상태 추적의 중요성  
- **LLM 제어**: 강력한 프롬프트 규칙과 예시로 LLM 행동 통제
- **디버깅**: TCP 모드로 서버 로그 실시간 확인 가능

### 🚨 주요 함정들
1. **자동 확정 함정**: 시스템 편의 vs 사용자 통제권의 균형
2. **LLM 고집**: confidence 높아도 계속 세분화하려는 경향
3. **상태 동기화**: 여러 도구 간 상태 일관성 유지 필요
4. **에러 전파**: 한 단계 실패가 전체 플로우 중단으로 이어짐

### 💡 성공 요인
- **점진적 개선**: 단일 도구 → 다중 도구 → 사용자 확인 단계별 진화
- **실제 테스트**: 실제 대화 시나리오로 문제 발견 및 해결
- **명확한 규칙**: LLM이 따라야 할 절대 규칙 명시
- **시각적 피드백**: 사용자가 현재 상황을 쉽게 파악 가능