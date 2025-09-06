"""
Interactive Assessment Client

터미널에서 사용자와 대화하며 학습 평가를 진행하는 클라이언트
"""

import asyncio
import sys
from typing import Optional
from mcp import ClientSession, StdioServerParameters  
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from conversation_controller import ConversationController


class InteractiveAssessmentClient:
    """터미널 기반 대화형 평가 클라이언트"""
    
    def __init__(self):
        self.llm = None
        self.agent = None
        self.controller = None
        self.session_id = None
        
    async def initialize(self):
        """클라이언트 초기화"""
        print("🔧 시스템을 초기화하는 중...")
        
        # LLM 초기화
        self.llm = ChatOpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama", 
            model="midm-2.0:base",
            temperature=0.0,
            max_tokens=8192,
        )
        
        # MCP 서버 연결
        server_params = StdioServerParameters(
            command="python",
            args=["servers/user_assessment.py"],
        )
        
        print("📡 MCP 서버에 연결 중...")
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # MCP 도구 로드
                tools = await load_mcp_tools(session)
                for tool in tools:
                    print(f"✅ {tool}")
                
                print("🤖 에이전트를 생성하는 중...")
                
                try:
                    # 일단 기본 에이전트로 시도
                    self.agent = create_react_agent(self.llm, tools)
                    print("✅ 기본 에이전트 생성 성공")
                    
                except Exception as e:
                    print(f"❌ 기본 에이전트 생성 실패: {e}")
                    print(f"📋 에러 타입: {type(e)}")
                    import traceback
                    traceback.print_exc()
                    return
                
                # 대화 컨트롤러 초기화
                self.controller = ConversationController(self.agent)
                
                # 메인 대화 루프 시작
                await self.run_conversation()
    
    async def run_conversation(self):
        """메인 대화 루프"""
        # 웰컴 메시지 출력
        # self.print_welcome_message()
        
        # 평가 시작
        result = await self.controller.start_assessment()
        if result.get("error"):
            print(f"❌ 오류: {result['error']}")
            print("\n🔧 디버그 정보:")
            print(f"   - 응답 타입: {type(result)}")
            print(f"   - 키들: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            return
            
        self.session_id = result.get("session_id")
        if self.session_id:
            print(f"\n✅ 세션 생성 성공: {self.session_id[:8]}...")
        
        print(f"\n🎯 {result.get('message', '평가를 시작합니다!')}")
        
        # 대화 루프
        while True:
            try:
                # 사용자 입력 받기
                user_input = input("\n👤 > ").strip()
                
                if not user_input:
                    print("💡 무엇인가 입력해주세요!")
                    continue
                    
                # 특수 명령 처리
                if user_input.lower() in ['quit', 'exit', '종료', '나가기']:
                    print("\n👋 평가를 종료합니다. 다음에 또 만나요!")
                    break
                elif user_input.lower() in ['help', '도움', '도움말']:
                    self.show_help()
                    continue
                elif user_input.lower() in ['status', '상태', '진행상황']:
                    print("\n📊 현재 진행 상황을 확인하는 중...")
                    continue
                
                # 사용자 입력 처리
                result = await self.controller.handle_user_input(
                    user_input, self.session_id
                )
                
                if result.get("error"):
                    print(f"\n❌ {result['error']}")
                    continue
                
                # AI 응답 출력
                message = result.get("message", "")
                if message:
                    print(f"\n🤖 {message}")
                
                # 평가 완료 체크
                if result.get("next_action") == "assessment_complete":
                    print("\n🎉 모든 평가가 완료되었습니다!")
                    
                    # 최종 결과 표시
                    final_data = result.get("final_assessment")
                    if final_data:
                        self.display_final_results(final_data)
                    break
                    
                # 진행률 표시
                progress = result.get("progress")
                if progress:
                    self.display_progress(progress)
                    
            except KeyboardInterrupt:
                print("\n\n👋 평가를 중단합니다.")
                break
            except Exception as e:
                print(f"\n❌ 예상치 못한 오류가 발생했습니다: {e}")
                continue
    
    def print_welcome_message(self):
        """웰컴 메시지 출력"""
        print("\n" + "🌟" * 30)
        print("🎯 AI 학습 상담사에 오신 것을 환영합니다!")
        print("🌟" * 30)
        print()
        print("📚 맞춤형 학습 추천을 위한 개인화 평가를 시작합니다.")
        print("💬 자연스럽게 대화하듯 편안하게 답변해주세요.")
        print()
        print("📋 평가 과정:")
        print("   1️⃣ 주제 파악 → 2️⃣ 목표 설정 → 3️⃣ 시간 계획")
        print("   4️⃣ 예산 설정 → 5️⃣ 수준 측정 → 🎉 강의 추천")
        print()
        print("💡 도움말:")
        print("   • 'quit' 또는 'exit': 종료")
        print("   • 'help': 도움말 보기")
        print("   • 'status': 현재 진행 상황 확인")
        print("-" * 60)
    
    def display_progress(self, progress_info):
        """진행률 표시"""
        if not progress_info:
            return
            
        current_step = progress_info.get("current_step", 0)
        total_steps = progress_info.get("total_steps", 5)
        stage_name = progress_info.get("stage_name", "진행 중")
        percentage = progress_info.get("percentage", 0)
        
        # 진행률 바 생성 (더 예쁜 스타일)
        bar_length = 25
        filled_length = int(bar_length * percentage / 100)
        
        # 그라데이션 효과를 위한 바 스타일
        filled_bar = "🟩" * filled_length
        empty_bar = "⬜" * (bar_length - filled_length)
        
        # 단계별 이모지
        stage_emojis = {
            "주제 파악": "📖",
            "목표 설정": "🎯", 
            "시간 계획": "⏰",
            "예산 설정": "💰",
            "수준 측정": "📈"
        }
        
        stage_emoji = stage_emojis.get(stage_name, "📊")
        
        print(f"\n{stage_emoji} [{current_step}/{total_steps}] {stage_name} - {percentage}%")
        print(f"    {filled_bar}{empty_bar}")
        
        # 다음 단계 안내
        if current_step < total_steps:
            next_stages = ["주제 파악", "목표 설정", "시간 계획", "예산 설정", "수준 측정"]
            if current_step < len(next_stages):
                print(f"    💡 다음: {next_stages[current_step]}")
    
    def show_help(self):
        """도움말 표시"""
        print("\n" + "📖" * 20)
        print("            도움말")
        print("📖" * 20)
        print()
        print("🔸 평가 과정:")
        print("   각 단계에서 자연스럽게 대답해주세요!")
        print("   예: '파이썬을 배우고 싶어요', '취업 준비용이에요' 등")
        print()
        print("🔸 유용한 명령어:")
        print("   • help/도움말: 이 도움말 보기")
        print("   • status/상태: 진행 상황 확인")  
        print("   • quit/exit: 평가 종료")
        print()
        print("🔸 답변 팁:")
        print("   • 구체적으로: '프로그래밍' → '파이썬 웹 개발'")
        print("   • 솔직하게: 현재 수준이나 상황을 있는 그대로")
        print("   • 자세하게: 목표나 계획을 상세히 설명")
        print()
        print("💡 언제든 자연스럽게 대화하듯 답변해주세요!")
        print("-" * 60)
    
    def display_final_results(self, assessment_data):
        """최종 평가 결과 표시"""
        print("\n" + "🎉" * 20)
        print("         최종 평가 결과")
        print("🎉" * 20)
        
        # 각 항목별 결과 출력
        stages = [
            ("topic", "📖 학습 주제"),
            ("goal", "🎯 학습 목표"), 
            ("time", "⏰ 학습 시간"),
            ("budget", "💰 학습 예산"),
            ("level", "📈 현재 수준")
        ]
        
        for stage_key, stage_name in stages:
            stage_data = assessment_data.get(stage_key, {})
            if stage_data:
                print(f"\n{stage_name}:")
                # 주요 정보만 간단히 표시
                if stage_key == "topic":
                    print(f"  - {stage_data.get('topic', '미확인')}")
                elif stage_key == "goal":
                    print(f"  - {stage_data.get('goal', '미확인')}")
                elif stage_key == "time":
                    print(f"  - {stage_data.get('time_commitment', '미확인')}")
                elif stage_key == "budget":
                    print(f"  - {stage_data.get('budget_range', '미확인')}")
                elif stage_key == "level":
                    print(f"  - {stage_data.get('level', '미확인')}")
        
        print("\n🚀 이제 이 정보를 바탕으로 맞춤형 강의를 추천해드릴 수 있습니다!")
        print("=" * 60)


async def main():
    """메인 함수"""
    client = InteractiveAssessmentClient()
    
    try:
        await client.initialize()
    except KeyboardInterrupt:
        print("\n\n👋 프로그램을 종료합니다.")
    except Exception as e:
        print(f"\n❌ 시스템 초기화 중 오류가 발생했습니다: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())