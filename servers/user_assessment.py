from mcp.server.fastmcp import FastMCP
import logging

mcp = FastMCP(
    "Profiling",  # Name of the MCP server
    instructions="사용자가 새로운 학습을 시작하려고 할 때 개인화된 학습 계획을 위한 프로필 정보를 수집합니다.",  # Instructions for the LLM on how to use this tool
    host="0.0.0.0",  # Host address (0.0.0.0 allows connections from any IP)
    port=8005,  # Port number for the server
)

@mcp.tool()
async def user_profiling(message: str) -> str:
    """
    Call this tool when a user wants to learn something new or asks about studying/learning.
    
    Use this tool if the user mentions:
    - "배우고 싶다" (want to learn)
    - "공부하고 싶다" (want to study) 
    - "시작하고 싶다" (want to start)
    - Any learning-related keywords
    
    Always call this tool first when user shows learning intent.
    
    Args:
        message: The user's message about learning
        
    Returns:
        str: Profiling questions for the user
    """

    # 툴 호출 로깅
    logger.info(f"=== user_profiling 툴 호출됨 ===")
    logger.info(f"입력 메시지: {message}")
    
    # 메시지에서 학습 주제 추출
    learning_topic = ""
    if "파이썬" in message.lower() or "python" in message.lower():
        learning_topic = "Python 프로그래밍"
    elif "영어" in message:
        learning_topic = "영어"
    elif "자바스크립트" in message.lower() or "javascript" in message.lower():
        learning_topic = "JavaScript"
    else:
        # 일반적인 키워드 추출 시도
        keywords = ["배우", "공부", "익히", "시작"]
        for keyword in keywords:
            if keyword in message:
                # 간단한 주제 추출 로직
                words = message.split()
                for i, word in enumerate(words):
                    if keyword in word and i > 0:
                        learning_topic = words[i-1]
                        break
    
    if not learning_topic:
        learning_topic = "해당 주제"
    
    # 프로필링 질문 생성
    profiling_questions = f"""
{learning_topic}에 관심이 있으시군요! 맞춤형 학습 계획을 세우기 위해 몇 가지 질문드리겠습니다.

1. **현재 수준**: {learning_topic}에 대한 경험이 있으신가요? (완전 초보자, 조금 알고 있음, 어느 정도 할 수 있음)

2. **학습 목적**: 어떤 목적으로 {learning_topic}을 배우고 싶으신가요? (취업, 업무, 취미, 학업 등)

3. **시간 투자**: 일주일에 몇 시간 정도 학습에 투자할 수 있으신가요?

4. **구체적 목표**: {learning_topic}을 통해 무엇을 할 수 있게 되고 싶으신가요?

하나씩 답변해주시면 더 정확한 학습 계획을 만들어드릴 수 있습니다!
    """.strip()
  
    return profiling_questions

if __name__ == "__main__":
    mcp.run(transport="stdio")