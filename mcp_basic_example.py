"""
MCP (Model Context Protocol) 기초 예제

핵심 개념:
1. MCP 서버: 도구(함수)들을 제공
2. MCP 클라이언트: 서버의 도구들을 사용
3. LangChain 통합: MCP 도구를 LangChain 에이전트에서 사용
"""

import asyncio
from mcp.server.fastmcp import FastMCP

# ====== 1. MCP 서버 생성 (도구 제공자) ======

# 간단한 MCP 서버 만들기
mcp_server = FastMCP("BasicCalculator")

@mcp_server.tool()
def add_numbers(a: int, b: int) -> int:
    """두 숫자를 더합니다."""
    result = a + b
    print(f"서버에서 계산: {a} + {b} = {result}")
    return result

@mcp_server.tool()
def multiply_numbers(a: int, b: int) -> int:
    """두 숫자를 곱합니다."""
    result = a * b
    print(f"서버에서 계산: {a} × {b} = {result}")
    return result


# ====== 2. MCP 클라이언트 + LangChain 통합 ======

async def simple_mcp_client():
    """간단한 MCP 클라이언트 예제"""
    
    # MCP 서버와 클라이언트 연결
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools
    from langchain_openai import ChatOpenAI
    from langgraph.prebuilt import create_react_agent
    
    # 1단계: 서버 연결 파라미터 설정
    server_params = StdioServerParameters(
        command="python",
        args=["-c", """
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('Calculator')

@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    return a + b

@mcp.tool() 
def multiply_numbers(a: int, b: int) -> int:
    return a * b

if __name__ == '__main__':
    mcp.run(transport='stdio')
"""]
    )
    
    # 2단계: LLM 설정
    llm = ChatOpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        model="midm-2.0:base",
        temperature=0.0
    )
    
    print("🔧 MCP 서버 연결 중...")
    
    # 3단계: MCP 클라이언트 연결
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 4단계: MCP 도구를 LangChain 도구로 변환
            tools = await load_mcp_tools(session)
            print(f"✅ {len(tools)}개 도구 로드: {[tool.name for tool in tools]}")
            
            # 5단계: 에이전트 생성
            agent = create_react_agent(llm, tools)
            print("✅ 에이전트 생성 완료")
            
            # 6단계: 에이전트 사용
            print("\n🤖 에이전트에게 계산 요청...")
            
            # 간단한 계산 요청
            response = await agent.ainvoke({
                # "messages": "5와 3을 더한 다음, 그 결과에 2를 곱해주세요."
                "messages": "add 5 and 3 and multiply by 2"
            })
            
            # 결과 출력
            print("\n📊 최종 결과:")

            print("response : ", response)


            # 응답 구조 확인
            print(f"📋 Response 타입: {type(response)}")
            print(f"📋 Response 키들: {list(response.keys()) if isinstance(response, dict) else 'Not a dict'}")
            
            # 올바른 방식으로 최종 메시지 추출
            if isinstance(response, dict) and 'messages' in response:
                messages = response['messages']
                print(f"📋 총 메시지 수: {len(messages)}")
                
                # 마지막 AI 메시지 찾기
                last_ai_message = None
                for msg in reversed(messages):
                    if hasattr(msg, 'content') and type(msg).__name__ == 'AIMessage':
                        last_ai_message = msg
                        break
                
                if last_ai_message and last_ai_message.content:
                    print(f"🎯 최종 AI 답변: {last_ai_message.content}")
                else:
                    print("❌ 최종 AI 답변을 찾을 수 없습니다.")
            else:
                print("❌ 예상과 다른 응답 구조입니다.")


# ====== 3. 더욱 간단한 직접 호출 예제 ======

async def direct_mcp_call():
    """MCP 도구를 직접 호출하는 예제 (에이전트 없이)"""
    
    print("\n" + "="*50)
    print("🔧 직접 MCP 도구 호출 예제")
    print("="*50)
    
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    
    # 간단한 인라인 서버
    server_params = StdioServerParameters(
        command="python", 
        args=["-c", """
from mcp.server.fastmcp import FastMCP
mcp = FastMCP('SimpleCalc')

@mcp.tool()
def add_numbers(a: int, b: int) -> int:
    return a + b

if __name__ == '__main__':
    mcp.run(transport='stdio')
"""]
    )
    
    # MCP 클라이언트로 직접 도구 호출
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 사용 가능한 도구 목록 확인
            tools_result = await session.call_tool("add_numbers", {"a": 10, "b": 20})
            print(f"💡 10 + 20 = {tools_result.content}")


# ====== 4. 실행 ======

async def main():
    print("🚀 MCP 기초 예제 시작!")
    print("📚 MCP = Model Context Protocol")
    print("💡 서버(도구 제공) ↔ 클라이언트(도구 사용)")
    print()
    
    try:
        
        # 방법 2: LangChain 에이전트와 통합
        print("\n" + "="*50)
        print("🤖 LangChain 에이전트 통합 예제")
        print("="*50)
        await simple_mcp_client()
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("🎯 MCP 핵심 개념 학습")
    print("=" * 60)
    asyncio.run(main())