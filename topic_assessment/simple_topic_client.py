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
    """다중 Tool 학습 평가 클라이언트"""
    
    def __init__(self):
        self.llm = None
        self.agent = None
        self.session = None
        self.assessment_complete = False
        self.final_assessment = {}
        self.current_stage = "topic"
    
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
                self.session = session
                
                # MCP 도구 로드
                tools = await load_mcp_tools(session)
                print(f"✅ {len(tools)}개 도구 로드: {[tool.name for tool in tools]}")
                
                # 에이전트 생성 (일단 유지, 직접 tool 호출로 변경 예정)
                self.agent = create_react_agent(self.llm, tools)
                print("✅ 에이전트 생성 완료")
                
                # 대화 시작
                await self.run_conversation()
    
    async def run_conversation(self):
        """메인 대화 루프"""
        print("\n" + "🎯" * 20)
        print("   종합 학습 평가 상담사")
        print("🎯" * 20)
        print()
        print("안녕하세요! 학습 계획을 위한 순차적 평가를 진행하겠습니다.")
        print("📚 주제 → 🎯 목적 → ⏰ 시간 → 💰 예산 순으로 차근차근 파악해드릴게요!")
        print("자연스럽게 말씀해 주세요! (종료: quit)")
        print("-" * 60)
        
        while not self.assessment_complete:
            try:
                # 사용자 입력
                user_input = input("\n👤 > ").strip()
                
                if user_input.lower() in ['quit', 'exit', '종료']:
                    print("\n👋 상담을 종료합니다.")
                    break
                
                if not user_input:
                    print("💡 무엇인가 입력해주세요!")
                    continue
                
                # 직접 Tool 호출로 변경
                await self.handle_user_input(user_input)
                
            except KeyboardInterrupt:
                print("\n\n👋 상담을 중단합니다.")
                break
            except Exception as e:
                print(f"\n❌ 오류가 발생했습니다: {e}")
                continue
    
    async def handle_user_input(self, user_input: str):
        """사용자 입력 처리 - 현재 단계에 맞는 tool 호출"""
        try:
            # 1. 현재 상태 조회
            status = await self.get_current_status()
            current_stage = status.get("current_stage", "topic")
            self.current_stage = current_stage
            
            # 2. 확인 대기 상태 체크 (각 카테고리에 값이 있지만 confirmed=False)
            pending_confirmation = None
            for category in ["topic", "goal", "time", "budget"]:
                if (status.get("current_stage") == category and 
                    category in status.get("confirmed_items", {}) == False and
                    self.has_pending_value(category)):
                    pending_confirmation = category
                    break
            
            # 확인 대기 중이면 확인 처리
            if pending_confirmation or self.is_confirmation_response(user_input):
                await self.handle_confirmation_response(user_input, current_stage)
                return
            
            # 3. 수정 요청 확인
            if self.is_correction_request(user_input):
                await self.handle_correction(user_input)
                return
            
            # 4. 현재 단계에 맞는 tool 호출
            if current_stage == "topic":
                result = await self.session.call_tool("assess_topic", {"user_message": user_input})
            elif current_stage == "goal":
                result = await self.session.call_tool("assess_goal", {"user_message": user_input})
            elif current_stage == "time":
                result = await self.session.call_tool("assess_time", {"user_message": user_input})
            elif current_stage == "budget":
                result = await self.session.call_tool("assess_budget", {"user_message": user_input})
            elif current_stage == "complete":
                print("\n🎉 평가가 이미 완료되었습니다!")
                self.assessment_complete = True
                return
            else:
                print(f"\n❌ 알 수 없는 단계: {current_stage}")
                return
            
            # 5. 결과 처리
            await self.process_tool_result(result, user_input)
            
        except Exception as e:
            print(f"\n❌ 처리 중 오류: {e}")
    
    def has_pending_value(self, category: str) -> bool:
        """해당 카테고리에 확인 대기 중인 값이 있는지 확인"""
        # 실제 구현에서는 상태를 조회해서 확인
        # 일단 간단하게 구현
        return True
    
    def is_confirmation_response(self, user_input: str) -> bool:
        """확인 응답인지 판단"""
        confirmation_keywords = ["네", "예", "확정", "맞아", "맞습니다", "좋아", "좋습니다", 
                                "아니", "아니야", "아니요", "틀렸", "다시", "수정", "바꿔"]
        return any(keyword in user_input for keyword in confirmation_keywords)
    
    async def get_current_status(self):
        """현재 평가 상태 조회"""
        try:
            result = await self.session.call_tool("get_assessment_status", {})
            if hasattr(result, 'content') and result.content:
                if isinstance(result.content, list) and len(result.content) > 0:
                    import json
                    return json.loads(result.content[0].text)
            return {"current_stage": "topic"}
        except Exception as e:
            print(f"⚠️ 상태 조회 실패: {e}")
            return {"current_stage": "topic"}
    
    def is_correction_request(self, user_input: str) -> bool:
        """수정 요청인지 확인"""
        correction_keywords = ["아니야", "사실은", "수정", "바꿔", "틀렸어", "다시"]
        return any(keyword in user_input for keyword in correction_keywords)
    
    async def handle_correction(self, user_input: str):
        """수정 요청 처리"""
        print("\n🔧 수정 요청을 처리합니다...")
        # 일단 현재 단계의 tool로 재평가
        await self.handle_user_input(user_input.replace("아니야", "").replace("사실은", "").strip())
    
    async def process_tool_result(self, result, user_input: str):
        """Tool 결과 처리"""
        try:
            # MCP 응답에서 실제 JSON 추출
            if hasattr(result, 'content') and result.content:
                if isinstance(result.content, list) and len(result.content) > 0:
                    import json
                    tool_result = json.loads(result.content[0].text)
                    await self.handle_tool_result(tool_result, user_input)
                else:
                    print(f"\n❌ 예상치 못한 응답 형식: {result.content}")
            else:
                print(f"\n❌ 빈 응답")
                
        except Exception as e:
            print(f"\n❌ Tool 결과 처리 중 오류: {e}")

    async def process_response(self, response, user_input):
        """에이전트 응답 처리"""
        try:
            # 응답에서 도구 결과 찾기
            tool_result = None
            if isinstance(response, dict) and 'messages' in response:
                for msg in response['messages']:
                    if hasattr(msg, 'content') and isinstance(msg.content, str):
                        # 도구 응답이 JSON 형태로 포함되어 있는지 확인
                        if '{' in msg.content:
                            try:
                                import json
                                # JSON 부분 추출
                                json_start = msg.content.find('{')
                                json_end = msg.content.rfind('}') + 1
                                if json_start != -1 and json_end > json_start:
                                    json_str = msg.content[json_start:json_end]
                                    tool_result = json.loads(json_str)
                                    break
                            except Exception as json_e:
                                continue
            
            if tool_result:
                await self.handle_tool_result(tool_result, user_input)
            else:
                print("\n🤖 응답을 처리하는 중 문제가 발생했습니다. 다시 말씀해 주시겠어요?")
                
        except Exception as e:
            print(f"\n❌ 응답 처리 중 오류: {e}")
    
    async def handle_tool_result(self, result, user_input):
        """단순한 JSON 구조에 맞춘 도구 결과 처리"""
        try:
            category = result.get("category", "unknown")
            value = result.get("value")
            confidence = result.get("confidence", 0)
            confirmed = result.get("confirmed", False)
            friendly_response = result.get("friendly_response", "")
            follow_up_question = result.get("follow_up_question", "")
            next_action = result.get("next_action", "")
            
            # 카테고리별 이모지
            category_emoji = {
                "topic": "📚", "goal": "🎯", 
                "time": "⏰", "budget": "💰"
            }
            
            # 친근한 응답 표시
            if friendly_response:
                print(f"\n🤖 {friendly_response}")
            
            # 현재 상태 표시
            emoji = category_emoji.get(category, "❓")
            status_icon = "✅" if confirmed else "🔄" if value else "⏳"
            
            print(f"\n{emoji} {category.upper()}: {value or '미파악'} {status_icon} (확신도: {confidence:.1f})")
            
            # 후속 질문
            if follow_up_question:
                print(f"❓ {follow_up_question}")
            
            # 전체 진행 상태 조회 및 표시
            await self.display_overall_progress()
            
            # 완료 확인
            if next_action == "assessment_complete":
                self.assessment_complete = True
                print("\n🎉 모든 평가가 완료되었습니다!")
            
            # 사용자 확인 필요한 경우
            elif next_action == "need_user_confirmation":
                print("\n⏸️  확인이 필요합니다.")
                
        except Exception as e:
            print(f"\n❌ 결과 처리 중 오류: {e}")
            print(f"📝 원본 결과: {result}")
    
    async def handle_confirmation_response(self, user_input: str, category: str):
        """사용자 확인 응답 처리"""
        try:
            result = await self.session.call_tool("confirm_and_proceed", {
                "category": category, 
                "user_response": user_input
            })
            
            # MCP 응답 처리
            if hasattr(result, 'content') and result.content:
                if isinstance(result.content, list) and len(result.content) > 0:
                    import json
                    confirmation_result = json.loads(result.content[0].text)
                    
                    status = confirmation_result.get("status")
                    message = confirmation_result.get("message", "")
                    
                    if status == "confirmed":
                        print(f"\n✅ {message}")
                        next_stage = confirmation_result.get("next_stage", "unknown")
                        print(f"➡️  다음 단계: {next_stage.upper()}")
                        
                        # 다음 단계 자동 시작
                        await self.start_next_stage(next_stage)
                        
                    elif status == "rejected":
                        print(f"\n🔄 {message}")
                        
                    elif status == "more_info":
                        print(f"\n📝 {message}")
                        # 추가 정보로 해당 카테고리 재분석
                        await self.reanalyze_with_more_info(category, user_input)
                        
        except Exception as e:
            print(f"\n❌ 확인 처리 중 오류: {e}")
    
    async def reanalyze_with_more_info(self, category: str, additional_info: str):
        """추가 정보로 재분석"""
        print(f"\n🔍 {category} 재분석 중...")
        
        if category == "topic":
            result = await self.session.call_tool("assess_topic", {"user_message": additional_info})
        elif category == "goal":
            result = await self.session.call_tool("assess_goal", {"user_message": additional_info})
        elif category == "time":
            result = await self.session.call_tool("assess_time", {"user_message": additional_info})
        elif category == "budget":
            result = await self.session.call_tool("assess_budget", {"user_message": additional_info})
        
        # 결과 처리
        await self.process_tool_result(result, additional_info)
    
    async def start_next_stage(self, stage: str):
        """다음 단계 자동 시작"""
        print(f"\n🔄 {stage.upper()} 단계를 시작합니다...")
        
        # 각 단계별 초기 질문 생성
        if stage == "goal":
            initial_message = "이제 학습 목적에 대해 알아보겠습니다. 왜 이 분야를 공부하고 싶으신가요?"
        elif stage == "time":  
            initial_message = "이제 학습 시간 계획에 대해 알아보겠습니다. 하루에 얼마나 시간을 낼 수 있으신가요?"
        elif stage == "budget":
            initial_message = "마지막으로 학습 예산에 대해 알아보겠습니다. 월 예산이 어느 정도 되시나요?"
        elif stage == "complete":
            initial_message = "🎉 모든 평가가 완료되었습니다! 맞춤형 학습 계획을 제안해드릴 수 있습니다."
            self.assessment_complete = True
        else:
            initial_message = f"{stage} 단계입니다. 관련 정보를 입력해 주세요."
        
        print(f"💬 {initial_message}")
        
        # 상태 갱신 및 진행률 표시
        await self.display_overall_progress()
    
    async def display_overall_progress(self):
        """전체 진행 상황 표시"""
        try:
            status = await self.get_current_status()
            confirmed_items = status.get("confirmed_items", {})
            progress = status.get("overall_progress", 0)
            current_stage = status.get("current_stage", "topic")
            
            print(f"\n📊 전체 진행률: {int(progress*100)}% {'▓'*int(progress*10)}{'░'*(10-int(progress*10))}")
            print(f"📍 현재 단계: {current_stage.upper()}")
            
            # 확정된 항목들 표시
            if confirmed_items:
                print("\n✅ 확정된 정보:")
                for category, info in confirmed_items.items():
                    emoji = {"topic": "📚", "goal": "🎯", "time": "⏰", "budget": "💰"}.get(category, "❓")
                    print(f"   {emoji} {category.upper()}: {info['value']}")
                    
        except Exception as e:
            print(f"⚠️ 진행 상황 표시 실패: {e}")
            
    def display_final_assessment(self):
        """최종 평가 결과 표시"""
        if not self.final_assessment:
            return
            
        print("\n" + "🎉" * 30)
        print("        최종 학습 평가 결과")
        print("🎉" * 30)
        
        for key, emoji in [('topic', '📚 학습 주제'), ('goal', '🎯 학습 목적'), 
                          ('time', '⏰ 학습 시간'), ('budget', '💰 학습 예산')]:
            if key in self.final_assessment:
                item = self.final_assessment[key]
                value = item.get('value', '미파악')
                print(f"{emoji}: {value}")
        
        print("\n🚀 이제 이 정보를 바탕으로 맞춤형 강의를 추천해드릴 수 있습니다!")
        print("="*60)


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