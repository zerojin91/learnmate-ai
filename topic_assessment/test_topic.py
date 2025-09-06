"""
Topic Assessment 테스트 스크립트

다양한 사용자 입력에 대한 주제 파악 테스트
"""

import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_topic_identification():
    """주제 파악 기능 테스트"""
    
    print("🧪 Topic Assessment 테스트 시작")
    print("=" * 50)
    
    # 테스트 케이스들
    test_cases = [
        "파이썬 프로그래밍을 배우고 싶어요",
        "프로그래밍 배우고 싶어요", 
        "웹개발 공부하려고 해요",
        "뭔가 배우고 싶어요",
        "영어 회화 실력을 늘리고 싶습니다",
        "기계학습에 대해 알고 싶어요",
        "안녕하세요",
        "컴퓨터 관련된 걸 배우고 싶은데..."
    ]
    
    # MCP 서버 연결
    server_params = StdioServerParameters(
        command="python",
        args=["topic_mcp_server.py"]
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            print("✅ MCP 서버 연결 완료")
            print()
            
            # 각 테스트 케이스 실행
            for i, test_input in enumerate(test_cases, 1):
                print(f"🔸 테스트 {i}: {test_input}")
                
                try:
                    # 도구 직접 호출
                    result = await session.call_tool(
                        "identify_learning_topic", 
                        {"user_message": test_input}
                    )
                    
                    print(f"📊 결과: {result.content}")
                    
                    # 결과 해석
                    import json
                    try:
                        # MCP 응답에서 실제 텍스트 추출
                        if isinstance(result.content, list) and len(result.content) > 0:
                            # 첫 번째 TextContent에서 text 추출
                            json_text = result.content[0].text
                        else:
                            json_text = str(result.content)
                            
                        parsed = json.loads(json_text)
                        topic = parsed.get('topic')
                        confidence = parsed.get('confidence', 0)
                        is_clear = parsed.get('is_clear', False)
                        clarification = parsed.get('clarification_question')
                        
                        print(f"   📈 주제: {topic}")
                        print(f"   📊 확신도: {confidence:.2f}")
                        print(f"   ✅ 명확성: {'명확' if is_clear else '불명확'}")
                        if clarification:
                            print(f"   ❓ 추가 질문: {clarification}")
                        
                    except (json.JSONDecodeError, AttributeError, IndexError) as e:
                        print(f"   ❌ JSON 파싱 실패: {e}")
                        print(f"   📝 원본 응답 타입: {type(result.content)}")
                        if hasattr(result.content, '__len__'):
                            print(f"   📏 응답 길이: {len(result.content)}")
                        if isinstance(result.content, list) and len(result.content) > 0:
                            print(f"   📄 첫 번째 항목: {result.content[0]}")
                    
                except Exception as e:
                    print(f"   ❌ 오류: {e}")
                
                print("-" * 30)
                print()


if __name__ == "__main__":
    asyncio.run(test_topic_identification())