"""
Topic Assessment MCP Server

사용자의 학습 주제만 파악하는 단순한 MCP 서버
"""

from mcp.server.fastmcp import FastMCP
from langchain_openai import ChatOpenAI
import json

# FastMCP 서버 생성
mcp = FastMCP(
    "TopicAssessment",
    instructions="사용자의 학습 주제를 파악하는 도구를 제공합니다."
)

# LLM 초기화
llm = ChatOpenAI(
    base_url="http://localhost:11434/v1",
    api_key="ollama", 
    model="midm-2.0:base",
    temperature=0.0,
    max_tokens=1024
)

print(f"🎯 Topic Assessment MCP 서버 초기화 완료")
print(f"🤖 사용 중인 LLM: {llm.model_name}")


@mcp.tool()
def identify_learning_topic(user_message: str) -> dict:
    """
    사용자 메시지에서 학습 주제를 파악합니다.
    
    Args:
        user_message: 사용자가 입력한 메시지
        
    Returns:
        dict: 주제 파악 결과
    """
    print(f"📝 주제 파악 요청: {user_message}")
    
    try:
        # 주제 파악을 위한 시스템 프롬프트
        system_prompt = """당신은 사용자가 학습하고 싶어하는 주제를 파악하는 전문가입니다.

사용자 메시지를 분석해서 다음 JSON 형식으로 응답해주세요:

{
    "topic": "구체적인 주제명 (예: 파이썬 프로그래밍, 영어회화, 데이터분석)" 또는 null,
    "confidence": 0.0~1.0 사이의 확신도,
    "is_clear": true/false (주제가 명확한지 여부),
    "clarification_question": "명료화가 필요할 때 할 질문" 또는 null
}

판단 기준:
1. 구체적인 주제 (예: "파이썬 배우고 싶어요") → confidence 0.7 이상, is_clear: true
2. 모호한 주제 (예: "프로그래밍 배우고 싶어요") → confidence 0.3-0.7, is_clear: false, 명료화 질문 제공
3. 주제 불명확 (예: "뭔가 배우고 싶어요") → confidence 0.3 미만, is_clear: false

반드시 JSON 형식으로만 응답하세요."""

        # LLM 호출
        response = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"사용자 메시지: {user_message}"}
        ])
        
        # JSON 응답 파싱
        try:
            result = json.loads(response.content)
            print(f"✅ 주제 파악 완료: {result}")
            return result
            
        except json.JSONDecodeError:
            print(f"❌ JSON 파싱 실패. 원본 응답: {response.content}")
            # fallback 응답
            return {
                "topic": None,
                "confidence": 0.1,
                "is_clear": False,
                "clarification_question": "어떤 분야를 공부하고 싶으신지 좀 더 구체적으로 알려주세요."
            }
            
    except Exception as e:
        print(f"❌ 주제 파악 중 오류: {str(e)}")
        return {
            "topic": None,
            "confidence": 0.0,
            "is_clear": False,
            "clarification_question": "죄송합니다. 다시 말씀해 주시겠어요?"
        }


if __name__ == "__main__":
    print("🚀 Topic Assessment MCP Server를 시작합니다...")
    print("💡 제공하는 도구:")
    print("   - identify_learning_topic: 사용자 메시지에서 학습 주제 파악")
    print()
    
    mcp.run(transport="stdio")