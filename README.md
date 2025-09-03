# LearnAI - MCP 기반 개인화 학습 멘토 시스템

## 프로젝트 개요

LearnAI는 Model Control Protocol(MCP)을 활용하여 사용자의 관심 주제에 맞춤형 학습 커리큘럼을 제공하고, 일별 학습 계획을 관리하며, AI 멘토 역할을 수행하는 개인화 학습 지원 시스템입니다.

### 서비스 목표
- 사용자별 맞춤형 학습 커리큘럼 생성
- 일별 학습 계획 및 진도 관리
- 실시간 AI 멘토링 및 학습 상담
- 학습 기록 추적 및 분석

## 현재 개발 현황

### 완료된 기능
1. **MCP Agent 시스템**
   - MCP 서버와 LangGraph 에이전트 통합
   - 모듈화된 에이전트 관리 (`agent.py`)
   - 동적 서버 전환 기능

2. **웹 기반 채팅 인터페이스**
   - FastAPI 기반 백엔드 API
   - HTML/CSS/JavaScript 프론트엔드
   - 실시간 채팅 기능

3. **기본 인프라**
   - 로컬 및 네트워크 접근 지원
   - 템플릿 기반 UI 구조
   - 모듈화된 코드 아키텍처

## 기술 스택

### Backend
- **FastAPI**: 웹 프레임워크 및 API 서버
- **Python 3.11**: 메인 개발 언어
- **MCP (Model Control Protocol)**: AI 에이전트 통신
- **LangGraph**: AI 워크플로우 관리
- **LangChain**: AI 애플리케이션 프레임워크

### Frontend
- **HTML5/CSS3**: 기본 웹 구조 및 스타일링
- **Vanilla JavaScript**: 클라이언트 사이드 로직
- **Jinja2**: 서버사이드 템플릿 엔진

### AI/ML
- **Ollama**: 로컬 LLM 실행 환경
- **midm-2.0-base-q8**: 메인 언어 모델
- **ChatOpenAI**: OpenAI API 호환 인터페이스

## LearnAI 학습 플로우

### 1단계: 사용자 초기 평가 (user_assessment.py)
사용자가 처음 LearnAI에 접속하면 AI 에이전트와의 대화를 통해 다음 정보를 수집합니다:

- **학습 목표**: 무엇을 배우고 싶은지, 왜 배우려고 하는지
- **학습 제약조건**: 시간, 예산, 환경적 제약
- **최종 목표**: 구체적이고 측정 가능한 학습 목표 설정

### 2단계: 맞춤형 커리큘럼 생성 (generate_curriculum.py)
1단계에서 수집된 정보를 바탕으로 개인화된 학습 로드맵을 생성합니다.

### 3단계: 일별 학습 관리 및 멘토링 (evaluate_user.py)
학습 진행 상황을 모니터링하고 필요에 따라 계획을 조정합니다.

```
learnai/
├── main.py              # FastAPI 메인 애플리케이션
├── agent.py             # MCP 에이전트 모듈
├── utils.py             # 개발/디버깅 유틸리티
├── templates/
│   └── index.html       # 메인 채팅 UI
├── servers/             # MCP 서버들
│   ├── user_assessment.py    # 사용자 진단 서버 (현재: 날씨 데모)
│   ├── generate_curriculum.py # 커리큘럼 생성 서버 (개발 예정)
│   └── evaluate_user.py      # 사용자 평가 서버 (개발 예정)
└── agent.ipynb         # 프로토타이핑 노트북
```

## 설치 및 실행

### 1. 의존성 설치
```bash
pip install fastapi uvicorn jinja2 python-multipart aiofiles
pip install langchain langchain-openai langgraph mcp langchain-mcp-adapters
```

### 2. Ollama 서버 실행
```bash
ollama serve
ollama pull midm-2.0-base-q8  # 모델 다운로드 (필요시)
```

### 3. 애플리케이션 실행
```bash
python main.py
```

### 4. 접속
- 로컬: http://127.0.0.1:8000
- 네트워크: http://[표시된_IP]:8000

## API 엔드포인트

- `GET /`: 메인 채팅 UI
- `POST /chat`: 채팅 메시지 처리
- `GET /docs`: API 문서 (Swagger UI)

## 개발 예정 기능

### Phase 1: 데이터베이스 및 사용자 관리
- [ ] PostgreSQL/SQLite 데이터베이스 연동
- [ ] 사용자 인증 및 회원가입 시스템
- [ ] 세션 관리 및 대화 기록 저장
- [ ] 사용자 프로필 관리

### Phase 2: 학습 커리큘럼 시스템
- [ ] 사용자 진단 MCP 서버 (`user_assessment.py`)
- [ ] 사용자 학습 수준 평가 MCP 서버 (`evaluate_user.py`)
- [ ] 맞춤형 커리큘럼 생성 MCP 서버 (`generate_curriculum.py`)
- [ ] 일별 학습 계획 생성 및 관리
- [ ] 학습 진도 추적 시스템

### Phase 3: UI/UX 개선
- [ ] 반응형 웹 디자인
- [ ] 대시보드 및 학습 현황 시각화
- [ ] 모바일 친화적 인터페이스
- [ ] 다크모드 지원

### Phase 4: 고급 기능
- [ ] 실시간 알림 시스템
- [ ] 학습 분석 및 리포트
- [ ] 소셜 학습 기능 (스터디 그룹)
- [ ] 외부 학습 자료 연동

### Phase 5: 배포 및 운영
- [ ] Docker 컨테이너화
- [ ] 클라우드 배포 (AWS/GCP/Heroku)
- [ ] CI/CD 파이프라인 구축
- [ ] 모니터링 및 로깅 시스템
- [ ] 성능 최적화 및 스케일링

## 아키텍처 특징

### 모듈화된 설계
- MCP 서버별 독립적인 기능 구현
- 에이전트와 웹 서버의 명확한 분리
- 재사용 가능한 유틸리티 함수

### 확장 가능한 구조
- 새로운 MCP 서버 추가 용이
- 서버 타입별 동적 전환 지원
- 플러그인 방식의 기능 확장

### 개발 친화적 환경
- 핫 리로드 지원 (개발 모드)
- API 문서 자동 생성
- 프로토타이핑을 위한 Jupyter 노트북 지원

## 기여 방법

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 라이선스

MIT License

## 문의사항

프로젝트 관련 문의사항이나 버그 리포트는 이슈 트래커를 이용해 주세요.