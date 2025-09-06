"""
공식 MultiServerMCPClient로 MCP 도구 테스트
"""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from config import Config

async def test_mcp_tools_official():
    print("=== 공식 MCP 클라이언트 테스트 ===")
    
    # LLM 설정
    llm = ChatOpenAI(
        base_url=Config.LLM_BASE_URL,
        api_key=Config.LLM_API_KEY,
        model=Config.LLM_MODEL,
        temperature=0.0,
    )
    print(f"LLM 모델: {Config.LLM_MODEL}")
    
    # MCP 클라이언트 설정 
    client = MultiServerMCPClient({
        "assessment": {
            "command": "python",
            "args": ["servers/user_assessment.py"],
            "transport": "stdio"
        }
    })
    
    try:
        # 도구 로드
        tools = await client.get_tools()
        print(f"로드된 도구들: {[tool.name for tool in tools]}")
        print(f"도구 설명들:")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        
        if not tools:
            print("❌ 도구가 로드되지 않았습니다!")
            return
        
        # 에이전트 생성 
        agent = create_react_agent(llm, tools)
        print("✅ 에이전트 생성 완료")
        
        # 테스트 메시지들
        test_messages = [
            "나 파이썬 배우고 싶어",
            "Use the user_profiling tool to help me learn Python", 
            "Call user_profiling with my message"
        ]
        
        for test_message in test_messages:
            print(f"\n=== 테스트: {test_message} ===")
            print("-" * 50)
            
            try:
                # 스트리밍으로 실행해서 중간 과정 확인
                async for chunk in agent.astream({"messages": [("user", test_message)]}):
                    print(f"청크: {chunk}")
                    
            except Exception as e:
                print(f"❌ 에러 발생: {e}")
    
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_mcp_tools_official())