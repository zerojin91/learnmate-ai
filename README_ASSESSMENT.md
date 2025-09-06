# 🎯 AI 학습 상담 시스템

MCP 기반 터미널 대화형 사용자 평가 시스템

## 📋 시스템 구성

### 핵심 컴포넌트
1. **MCP 서버** (`servers/user_assessment.py`) - 5단계 평가 로직을 MCP 도구로 제공
2. **터미널 클라이언트** (`interactive_assessment_client.py`) - 사용자와의 대화형 인터페이스
3. **대화 컨트롤러** (`conversation_controller.py`) - 대화 플로우 및 상태 관리
4. **평가 엔진** (`servers/assessment_engine/`) - 5개 assessor와 세션 관리

### 평가 단계
1. 📖 **주제 파악** - 학습하고 싶은 분야 식별
2. 🎯 **목표 설정** - 학습 목적 및 목표 확인
3. ⏰ **시간 계획** - 학습 가능한 시간 파악
4. 💰 **예산 설정** - 학습 예산 범위 확인
5. 📈 **수준 측정** - 현재 수준 평가

## 🚀 사용 방법

### 1. 사전 준비
```bash
# Ollama에서 midm-2.0:base 모델 실행 (tool calling 지원)
ollama run midm-2.0:base

# 필요한 패키지 설치 확인
pip install mcp langchain_mcp_adapters langgraph langchain_openai
```

### 2. 시스템 실행
```bash
# 터미널에서 대화형 평가 시작
python interactive_assessment_client.py
```

### 3. 사용법
```
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟
🎯 AI 학습 상담사에 오신 것을 환영합니다!
🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟🌟

📚 맞춤형 학습 추천을 위한 개인화 평가를 시작합니다.
💬 자연스럽게 대화하듯 편안하게 답변해주세요.

📋 평가 과정:
   1️⃣ 주제 파악 → 2️⃣ 목표 설정 → 3️⃣ 시간 계획
   4️⃣ 예산 설정 → 5️⃣ 수준 측정 → 🎉 강의 추천

💡 도움말:
   • 'quit' 또는 'exit': 종료
   • 'help': 도움말 보기  
   • 'status': 현재 진행 상황 확인
------------------------------------------------------------

👤 > 파이썬 웹 개발을 배우고 싶어요

🤖 좋은 선택이세요! 파이썬 웹 개발은 정말 유용한 기술입니다...

📖 [1/5] 주제 파악 - 20%
    🟩🟩🟩🟩🟩⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜
    💡 다음: 목표 설정
```

### 4. 특수 명령어
- `help` / `도움말`: 상세한 도움말 보기
- `status` / `상태`: 현재 진행 상황 확인
- `quit` / `exit` / `종료`: 평가 종료

## 🔧 기술 스택

- **LLM**: Ollama midm-2.0:base (tool calling 지원)
- **MCP Framework**: 도구 호출을 위한 통신 프로토콜
- **LangGraph**: 에이전트 및 대화 플로우 관리
- **Python**: 비동기 처리 및 터미널 UI

## 📁 파일 구조

```
learnmate-ai/
├── interactive_assessment_client.py    # 메인 터미널 클라이언트
├── conversation_controller.py          # 대화 플로우 컨트롤러  
├── servers/
│   ├── user_assessment.py             # MCP 서버 (메인)
│   └── assessment_engine/             # 평가 엔진
│       ├── assessors/                 # 5개 평가기
│       ├── session_manager.py         # 세션 관리
│       ├── models/                    # 데이터 모델
│       └── database/                  # KMOOC DB 연동
└── utils.py                           # LangGraph 유틸리티
```

## 🎨 특징

- ✨ **직관적 UI**: 이모지와 진행률 바를 활용한 사용자 친화적 인터페이스
- 🔄 **상태 기반 대화**: 각 평가 단계에 맞는 맞춤형 질문과 응답
- 🛡️ **안정성**: 오류 처리 및 복구 기능
- 📊 **진행률 표시**: 실시간 평가 진행 상황 확인
- 💬 **자연스러운 대화**: AI가 상담사처럼 친근하게 소통

## 🚨 주의사항

1. **Ollama 서버 실행**: `midm-2.0:base` 모델이 localhost:11434에서 실행 중이어야 함
2. **네트워크 연결**: MCP 서버와의 통신을 위한 네트워크 연결 필요
3. **Python 버전**: Python 3.8+ 권장

## 📞 문제 해결

### 자주 발생하는 문제

1. **"Connection refused" 오류**
   ```bash
   # Ollama 서버 상태 확인
   ollama list
   ollama serve
   ```

2. **"midm-2.0:base not found" 오류**
   ```bash
   # 모델 다운로드
   ollama pull midm-2.0:base
   ```

3. **MCP 연결 실패**
   - `servers/user_assessment.py`가 올바른 경로에 있는지 확인
   - Python 패키지 설치 상태 확인

### 디버그 모드
```bash
# 상세한 로그와 함께 실행
PYTHONPATH=. python -u interactive_assessment_client.py
```