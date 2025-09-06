"""
Conversation Controller

대화 플로우와 MCP 도구 호출을 관리하는 컨트롤러
"""

from typing import Dict, Any, Optional
from utils import astream_graph


class ConversationController:
    """대화 플로우 컨트롤러"""
    
    def __init__(self, agent):
        """
        Args:
            agent: LangGraph 에이전트 인스턴스
        """
        self.agent = agent
        self.stage_order = ["topic", "goal", "time", "budget", "level", "completed"]
        self.stage_names = {
            "topic": "주제 파악",
            "goal": "목표 설정", 
            "time": "시간 계획",
            "budget": "예산 설정",
            "level": "수준 측정",
            "completed": "평가 완료"
        }
        
    async def start_assessment(self) -> Dict[str, Any]:
        """평가 시작"""
        try:
            # start_assessment 도구 호출
            response = await astream_graph(
                self.agent, 
                {"messages": "start_assessment 도구를 사용해서 새로운 학습 평가를 시작해주세요."}
            )
            print("response : ", response)
            
            # 개선된 응답 파싱
            parsed_result = self.parse_agent_response(response)
            print("parsed_result : ", parsed_result)
            
            # 파싱 결과 확인
            session_id = parsed_result.get("session_id")
            print("session_id : ", session_id)

            if session_id:
                return {
                    "session_id": session_id,
                    "message": "안녕하세요! 🎯 맞춤형 학습 추천을 위해 간단한 평가를 진행하겠습니다.\n\n편안하게 대화하듯 답변해주시면 됩니다! 😊\n\n그럼 시작해볼까요? 어떤 주제를 공부하고 싶으신가요?",
                    "progress": self.calculate_progress("topic")
                }
            
            # 응답 내용에서 직접 session_id 추출 시도
            content = response.get("content", {})
            print("content : ", content)
            if hasattr(content, "messages") and content.messages:
                last_message = content.messages[-1]
                print("last_message : ", last_message)
                if hasattr(last_message, "content"):
                    message_text = str(last_message.content)
                    print("message_text : ", message_text)
                    # JSON 형태 응답에서 session_id 추출
                    import re
                    session_match = re.search(r'"session_id":\s*"([^"]+)"', message_text)
                    if session_match:
                        session_id = session_match.group(1)
                        return {
                            "session_id": session_id,
                            "message": "안녕하세요! 🎯 맞춤형 학습 추천을 위해 간단한 평가를 진행하겠습니다.\n\n편안하게 대화하듯 답변해주시면 됩니다! 😊\n\n그럼 시작해볼까요? 어떤 주제를 공부하고 싶으신가요?",
                            "progress": self.calculate_progress("topic")
                        }
            
            return {"error": f"평가 시작에 실패했습니다. 응답: {str(response)[:200]}..."}
            
        except Exception as e:
            return {"error": f"평가 시작 중 오류 발생: {str(e)}"}
    
    async def handle_user_input(self, user_input: str, session_id: str) -> Dict[str, Any]:
        """사용자 입력 처리"""
        try:
            # assess_user 도구 호출
            tool_message = f"assess_user 도구를 사용해서 session_id는 '{session_id}', user_input은 '{user_input}'로 사용자 평가를 진행해주세요."
            
            response = await astream_graph(self.agent, {"messages": tool_message})
            
            # 응답 파싱
            result = self.parse_agent_response(response)
            
            # 확인이 필요한 경우 처리
            if result.get("status") == "confirmation_needed":
                return result
            
            # 명료화가 필요한 경우
            if result.get("status") == "clarification_needed":
                return result
            
            # 다음 단계로 자동 진행 (확신도가 높은 경우)
            if result.get("status") in ["confirmation_needed"] and result.get("confidence", 0) >= 0.8:
                # 자동으로 확인 및 다음 단계 진행
                confirm_result = await self.auto_confirm_and_proceed(session_id)
                return confirm_result
            
            return result
            
        except Exception as e:
            return {"error": f"사용자 입력 처리 중 오류: {str(e)}"}
    
    async def auto_confirm_and_proceed(self, session_id: str) -> Dict[str, Any]:
        """자동으로 확인하고 다음 단계로 진행"""
        try:
            tool_message = f"confirm_and_proceed 도구를 사용해서 session_id는 '{session_id}', confirmed는 true로 설정해서 다음 단계로 진행해주세요."
            
            response = await astream_graph(self.agent, {"messages": tool_message})
            
            result = self.parse_agent_response(response)
            return result
            
        except Exception as e:
            return {"error": f"단계 진행 중 오류: {str(e)}"}
    
    def parse_agent_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """에이전트 응답 파싱"""
        try:
            content = response.get("content", {})
            
            if hasattr(content, "messages") and content.messages:
                last_message = content.messages[-1]
                if hasattr(last_message, "content"):
                    message_text = str(last_message.content)
                    
                    # 도구 호출 결과에서 정보 추출
                    result = {
                        "message": self.extract_message(message_text),
                        "stage": self.extract_field(message_text, "stage"),
                        "status": self.extract_field(message_text, "status"), 
                        "next_action": self.extract_field(message_text, "next_action"),
                        "session_id": self.extract_field(message_text, "session_id"),
                        "confidence": self.extract_confidence(message_text)
                    }
                    
                    # 최종 평가 데이터 추출
                    if "final_assessment" in message_text or "assessment_complete" in message_text:
                        result["next_action"] = "assessment_complete"
                        result["final_assessment"] = self.extract_assessment_data(message_text)
                    
                    # 진행률 계산
                    current_stage = result.get("stage", "topic")
                    result["progress"] = self.calculate_progress(current_stage)
                    
                    return result
            
            return {"error": "응답을 파싱할 수 없습니다."}
            
        except Exception as e:
            return {"error": f"응답 파싱 중 오류: {str(e)}"}
    
    def extract_message(self, text: str) -> str:
        """메시지 추출 - 개선된 버전"""
        try:
            # JSON 형태의 응답에서 message 필드 찾기
            import re
            
            # message 필드를 찾는 정규표현식
            message_patterns = [
                r'"message":\s*"([^"]*)"',
                r"'message':\s*'([^']*)'",
                r'"message":\s*"([^"]*?)"',
                r'message":\s*"([^"]*?)"'
            ]
            
            for pattern in message_patterns:
                matches = re.findall(pattern, text, re.DOTALL)
                if matches:
                    # 이스케이프 문자 처리
                    message = matches[0].replace('\\n', '\n').replace('\\"', '"')
                    if message.strip():
                        return message.strip()
            
            # 패턴 매치 실패 시 간단한 텍스트 추출
            lines = text.split('\n')
            clean_lines = []
            
            for line in lines:
                line = line.strip()
                # 시스템 메시지나 JSON 구조 제외
                if (line and 
                    not line.startswith('{') and 
                    not line.startswith('}') and
                    not line.startswith('"') and
                    'session_id' not in line.lower() and
                    'stage' not in line.lower() and
                    'tool' not in line.lower()):
                    clean_lines.append(line)
            
            if clean_lines:
                return '\n'.join(clean_lines)
                
            return "평가를 계속 진행하겠습니다."
            
        except Exception as e:
            return f"응답 처리 중 오류가 발생했습니다: {str(e)}"
    
    def extract_field(self, text: str, field_name: str) -> Optional[str]:
        """특정 필드 값 추출 - 개선된 정규표현식 사용"""
        import re
        
        # 다양한 JSON 패턴에 대응
        patterns = [
            rf'"{field_name}":\s*"([^"]*)"',
            rf"'{field_name}':\s*'([^']*)'", 
            rf'"{field_name}":\s*"([^"]*?)"',
            rf'{field_name}":\s*"([^"]*)"'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            if matches:
                return matches[0].strip()
        
        return None
    
    def extract_confidence(self, text: str) -> float:
        """신뢰도 추출"""
        try:
            if '"confidence":' in text:
                start = text.find('"confidence":') + 13
                end = text.find(',', start)
                if end == -1:
                    end = text.find('}', start)
                if end != -1:
                    confidence_str = text[start:end].strip()
                    return float(confidence_str)
        except:
            pass
        return 0.0
    
    def extract_assessment_data(self, text: str) -> Dict[str, Any]:
        """최종 평가 데이터 추출"""
        # 간단한 구현 - 실제로는 더 정교한 파싱 필요
        return {
            "topic": {"topic": "파악된 주제"},
            "goal": {"goal": "설정된 목표"},
            "time": {"time_commitment": "계획된 시간"},
            "budget": {"budget_range": "설정된 예산"},
            "level": {"level": "측정된 수준"}
        }
    
    def calculate_progress(self, current_stage: str) -> Dict[str, Any]:
        """진행률 계산"""
        try:
            stage_index = self.stage_order.index(current_stage)
            total_steps = len(self.stage_order) - 1  # completed 제외
            percentage = int((stage_index / total_steps) * 100) if total_steps > 0 else 0
            
            return {
                "current_step": stage_index + 1,
                "total_steps": total_steps,
                "stage_name": self.stage_names.get(current_stage, current_stage),
                "percentage": min(percentage, 100)
            }
        except ValueError:
            return {
                "current_step": 1,
                "total_steps": 5,
                "stage_name": "진행 중",
                "percentage": 0
            }