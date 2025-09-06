# 🎯 MCP 기반 학습 평가 시스템 개발 로그

## 📅 작업 일자: 2024-09-06

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

## 🎯 현재 상태

### ✅ 완료된 작업
1. **MCP 서버**: `topic_mcp_server.py` - 주제 파악 도구 제공
2. **테스트 스크립트**: `test_topic.py` - 도구 직접 호출 테스트 (정상 작동)
3. **클라이언트**: `simple_topic_client.py` - 대화형 인터페이스

### 🔧 테스트 결과
```bash
# 직접 도구 호출 테스트 (성공)
cd topic_assessment
python test_topic.py

# 결과 예시:
# 📈 주제: 파이썬 프로그래밍
# 📊 확신도: 1.00
# ✅ 명확성: 명확
```

### ❓ 남은 작업
1. **대화형 클라이언트 테스트**: `simple_topic_client.py` 검증
2. **에이전트 시스템 프롬프트 개선**: 빈 응답 문제 해결
3. **확장**: goal, time, budget, level 도구 추가

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

### 단기 목표 (내일)
1. `simple_topic_client.py` 완전 테스트
2. 에이전트 빈 응답 문제 해결
3. goal 파악 도구 추가 구현

### 중기 목표
1. 5단계 평가 시스템을 단순한 단일 도구들로 재구성
2. 각 단계별 독립적인 MCP 도구 완성
3. 통합된 클라이언트로 전체 플로우 구현

## 📝 중요한 명령어

### 환경 설정
```bash
conda activate TK
cd /Users/lgrnd/learnmate-ai/topic_assessment
```

### 테스트 실행
```bash
# 도구 직접 테스트
python test_topic.py

# 대화형 클라이언트 테스트  
python simple_topic_client.py

# MCP 기본 예제 학습
cd .. && python mcp_basic_example.py
```

### Ollama 서버 확인
```bash
ollama list  # 모델 확인
ollama run midm-2.0:base  # 모델 실행 (tool calling 지원)
```

---

## 📌 메모
- MCP는 LLM과 외부 도구 간의 표준 프로토콜
- ReAct 에이전트는 때로 도구 결과를 제대로 변환하지 못함 
- 복잡한 시스템보다는 단순한 도구들의 조합이 더 안정적
- 디버깅 시 도구 직접 호출로 문제 범위 좁히기