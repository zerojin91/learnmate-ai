# LearnAI Configuration
import os
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class Config:
    # LLM 설정
    # LLM_BASE_URL = "https://api.friendli.ai/serverless/v1"
    # LLM_API_KEY = os.getenv("LLM_API_KEY")
    # LLM_MODEL = "K-intelligence/Midm-2.0-Base-Instruct"
    # LLM_MODEL = "midm-2.0-base-bf16"

    LLM_BASE_URL = "https://api.friendli.ai/dedicated/v1"#"https://5fda9b8efc58.ngrok-free.app/v1"
    LLM_API_KEY = os.getenv("LLM_API_KEY")#"ollama"
    LLM_MODEL = "depnct19r37qy14"
    
    
    LLM_TEMPERATURE = 0.0
    LLM_MAX_TOKENS = 2048  # 응답 생성용 최대 토큰 수
    
    # 채팅 및 대화 설정
    MAX_CONTEXT_TOKENS = 8192  # LLM의 전체 컨텍스트 윈도우
    MAX_CONVERSATION_TOKENS = 6144  # 대화 기록용 토큰 (컨텍스트의 75%)
    CONVERSATION_TOKEN_BUFFER = 2048  # 응답 생성을 위한 여유 토큰
    
    # 서버 설정
    HOST = "0.0.0.0"
    PORT = 8000
    
    # MCP 서버 설정
    MCP_SERVER_HOST = "0.0.0.0"
    MCP_SERVER_PORT = 8005
    DEFAULT_MCP_SERVER = "servers/user_assessment.py"
    
    # 토큰 계산 설정
    AVERAGE_CHARS_PER_TOKEN = 4  # 한국어/영어 혼합 기준 대략적 토큰 계산
    
    @classmethod
    def get_effective_max_tokens(cls):
        """대화 기록에 실제로 사용할 수 있는 토큰 수"""
        return cls.MAX_CONVERSATION_TOKENS
