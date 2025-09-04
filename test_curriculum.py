#!/usr/bin/env python3
"""
🎓 커리큘럼 MCP 테스트 스크립트
=================================
이 스크립트는 MCP Agent를 통해 커리큘럼 생성 시스템을 테스트합니다.

사용법: 
    python test_curriculum.py

기능:
- 새로운 사용자 커리큘럼 생성
- 일일 학습 계획 생성  
- 데이터베이스 통계 확인
"""

from agent import MCPAgent
import asyncio

async def test_curriculum():
    # 커리큘럼 MCP 에이전트 생성
    agent = MCPAgent('servers/generate_curriculum.py')
    await agent.initialize()
    
    print("=== 🎓 커리큘럼 MCP 테스트 ===\n")
    
    # 1. 새로운 커리큘럼 생성
    print("1️⃣ 새로운 커리큘럼 생성 중...")
    user_id = "your_user_id"  # 여기에 원하는 사용자 ID 입력
    
    message1 = f'''
    사용자 "{user_id}"를 위한 React 프로그래밍 6주 커리큘럼을 생성해주세요.
    중급자 레벨이고, 상태 관리와 테스팅에 집중하고 싶습니다.
    '''
    
    print("요청:", message1.strip())
    print("\n📝 응답:")
    
    async for chunk in agent.chat_stream(message1):
        if chunk.get('type') == 'message':
            content = chunk.get('content', '')
            print(content, end='')
    
    print("\n" + "="*50)
    
    # 2. 일일 학습 계획 생성
    print("\n2️⃣ 1주차 일일 학습 계획 생성 중...")
    
    message2 = f'''
    사용자 "{user_id}"의 커리큘럼 ID 0번의 1주차에 대한 일일 학습 계획을 생성해주세요.
    '''
    
    print("요청:", message2.strip())
    print("\n📅 응답:")
    
    async for chunk in agent.chat_stream(message2):
        if chunk.get('type') == 'message':
            content = chunk.get('content', '')
            print(content, end='')
    
    print("\n" + "="*50)
    
    # 3. 데이터베이스 통계 확인
    print("\n3️⃣ 데이터베이스 통계 확인 중...")
    
    message3 = "데이터베이스 통계를 보여주세요."
    
    async for chunk in agent.chat_stream(message3):
        if chunk.get('type') == 'message':
            content = chunk.get('content', '')
            print(content, end='')
    
    print("\n\n✅ 테스트 완료!")
    
    await agent.cleanup()

if __name__ == "__main__":
    print("커리큘럼 MCP 시작 중...")
    asyncio.run(test_curriculum())