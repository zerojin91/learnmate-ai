"""
Simple Topic Assessment Client

사용자와 대화하며 학습 주제만 파악하는 간단한 클라이언트
"""

import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI


class SimpleTopicClient:
    """주제 파악 전용 클라이언트"""
    
    def __init__(self):
        self.llm = None
        self.agent = None
        self.topic_found = False
        self.final_topic = None
    
    async def initialize(self):
        """클라이언트 초기화"""
        print("🔧 Topic Assessment 클라이언트 초기화 중...")
        
        # LLM 초기화
        self.llm = ChatOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
            model="midm-2.0:base", 
            temperature=0.0,
            max_tokens=1024
        )
        
        # MCP 서버 연결 설정
        server_params = StdioServerParameters(
            command="python",
            args=["topic_mcp_server.py"]
        )
        
        print("📡 Topic MCP 서버에 연결 중...")
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # MCP 도구 로드
                tools = await load_mcp_tools(session)
                print(f"✅ {len(tools)}개 도구 로드: {[tool.name for tool in tools]}")
                
                # 에이전트 생성
                self.agent = create_react_agent(self.llm, tools)
                print("✅ 에이전트 생성 완료")
                
                # 대화 시작
                await self.run_conversation()
    
    async def run_conversation(self):
        """메인 대화 루프"""
        print("\n" + "🎯" * 20)
        print("     주제 파악 상담사")
        print("🎯" * 20)
        print()
        print("안녕하세요! 어떤 것을 배우고 싶으신지 알아보겠습니다.")
        print("자연스럽게 말씀해 주세요! (종료: quit)")
        print("-" * 50)
        
        while not self.topic_found:
            try:
                # 사용자 입력
                user_input = input("\n👤 > ").strip()
                
                if user_input.lower() in ['quit', 'exit', '종료']:
                    print("\n👋 상담을 종료합니다.")
                    break
                
                if not user_input:
                    print("💡 무엇인가 입력해주세요!")
                    continue
                
                # 에이전트에게 주제 파악 요청
                response = await self.agent.ainvoke({
                    "messages": f"identify_learning_topic 도구를 사용해서 다음 사용자 메시지에서 학습 주제를 파악해주세요: '{user_input}'"
                })
                
                # 응답 처리
                await self.process_response(response, user_input)
                
            except KeyboardInterrupt:
                print("\n\n👋 상담을 중단합니다.")
                break
            except Exception as e:
                print(f"\n❌ 오류가 발생했습니다: {e}")
                continue
    
    async def process_response(self, response, user_input):
        """에이전트 응답 처리"""
        try:
            # 응답에서 도구 결과 찾기
            tool_result = None
            if isinstance(response, dict) and 'messages' in response:
                for msg in response['messages']:
                    if hasattr(msg, 'content') and isinstance(msg.content, str):
                        # 도구 응답이 JSON 형태로 포함되어 있는지 확인
                        if 'topic' in msg.content and '{' in msg.content:
                            try:
                                import json
                                # JSON 부분 추출
                                json_start = msg.content.find('{')
                                json_end = msg.content.rfind('}') + 1
                                if json_start != -1 and json_end > json_start:
                                    json_str = msg.content[json_start:json_end]
                                    tool_result = json.loads(json_str)
                                    break
                            except:
                                continue
            
            if tool_result:
                await self.handle_tool_result(tool_result, user_input)
            else:
                print("\n🤖 주제를 파악하는 중입니다... 좀 더 구체적으로 말씀해 주시겠어요?")
                
        except Exception as e:
            print(f"\n❌ 응답 처리 중 오류: {e}")
    
    async def handle_tool_result(self, result, user_input):
        """도구 결과 처리"""
        print(f"\n📊 분석 결과: {result}")
        
        confidence = result.get('confidence', 0)
        is_clear = result.get('is_clear', False)
        topic = result.get('topic')
        clarification_question = result.get('clarification_question')
        
        if is_clear and confidence >= 0.7 and topic:
            # 주제가 명확하게 파악됨
            self.final_topic = topic
            self.topic_found = True
            print(f"\n🎉 훌륭합니다! '{topic}'에 관심이 있으시는군요!")
            print("주제 파악이 완료되었습니다.")
            
        elif clarification_question:
            # 명료화 질문 필요
            print(f"\n🤖 {clarification_question}")
            
        else:
            # 일반적인 응답
            print(f"\n🤖 말씀하신 내용을 바탕으로 보면, 학습 주제를 좀 더 구체적으로 알려주시면 도움이 될 것 같습니다.")


async def main():
    """메인 함수"""
    client = SimpleTopicClient()
    
    try:
        await client.initialize()
    except KeyboardInterrupt:
        print("\n\n👋 프로그램을 종료합니다.")
    except Exception as e:
        print(f"\n❌ 시스템 초기화 중 오류: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🎯 Simple Topic Assessment 시작!")
    asyncio.run(main())