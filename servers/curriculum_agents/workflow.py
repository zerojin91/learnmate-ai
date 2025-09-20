"""
LangGraph 기반 커리큘럼 생성 워크플로우
"""
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI

from .state import CurriculumState, ProcessingPhase, create_initial_state
from .parameter_analyzer import ParameterAnalyzerAgent
from .learning_path_planner import LearningPathPlannerAgent
from .module_structure_agent import ModuleStructureAgent
from .content_detail_agent import ContentDetailAgent
from .resource_collector import ResourceCollectorAgent
from .validation_agent import ValidationAgent
from .integration_agent import IntegrationAgent


class CurriculumGeneratorWorkflow:
    """LangGraph 기반 커리큘럼 생성 워크플로우"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """워크플로우 구성"""

        # 에이전트 인스턴스 생성
        agents = {
            "parameter_analyzer": ParameterAnalyzerAgent(self.llm),
            "learning_path_planner": LearningPathPlannerAgent(self.llm),
            "module_structure_agent": ModuleStructureAgent(self.llm),
            "content_detail_agent": ContentDetailAgent(self.llm),
            "resource_collector": ResourceCollectorAgent(self.llm),
            "validation_agent": ValidationAgent(self.llm),
            "integration_agent": IntegrationAgent(self.llm)
        }

        # 워크플로우 그래프 생성
        workflow = StateGraph(CurriculumState)

        # 노드 추가
        workflow.add_node("parameter_analysis", agents["parameter_analyzer"].execute)
        workflow.add_node("learning_path_planning", agents["learning_path_planner"].execute)
        workflow.add_node("module_structure_design", agents["module_structure_agent"].execute)
        workflow.add_node("content_detail_generation", agents["content_detail_agent"].execute)
        workflow.add_node("resource_collection", agents["resource_collector"].execute)
        workflow.add_node("validation", agents["validation_agent"].execute)
        workflow.add_node("integration", agents["integration_agent"].execute)
        workflow.add_node("error_handler", self._handle_error)

        # 워크플로우 엣지 정의
        workflow.add_edge(START, "parameter_analysis")
        workflow.add_edge("parameter_analysis", "learning_path_planning")
        workflow.add_edge("learning_path_planning", "module_structure_design")

        # 순차 처리로 변경 (병렬 처리 문제 해결)
        workflow.add_edge("module_structure_design", "content_detail_generation")
        workflow.add_edge("content_detail_generation", "resource_collection")

        workflow.add_edge("resource_collection", "validation")
        workflow.add_edge("validation", "integration")
        workflow.add_edge("integration", END)

        # 에러 처리
        workflow.add_conditional_edges(
            "error_handler",
            self._should_continue_after_error,
            {
                "continue": "integration",
                "stop": END
            }
        )

        return workflow.compile()

    def _handle_error(self, state: CurriculumState) -> CurriculumState:
        """에러 처리 노드"""
        if state["current_phase"] == ProcessingPhase.ERROR:
            print(f"ERROR: Workflow failed with errors: {state['errors']}")

            # 기본 커리큘럼 생성 시도
            try:
                fallback_curriculum = self._create_fallback_curriculum(state)
                state["final_curriculum"] = fallback_curriculum
                state["current_phase"] = ProcessingPhase.COMPLETED
            except Exception as e:
                print(f"ERROR: Fallback curriculum creation also failed: {e}")

        return state

    def _should_continue_after_error(self, state: CurriculumState) -> str:
        """에러 후 계속 진행 여부 결정"""
        if state.get("final_curriculum"):
            return "continue"
        return "stop"

    def _create_fallback_curriculum(self, state: CurriculumState) -> Dict[str, Any]:
        """기본 fallback 커리큘럼 생성"""
        duration_weeks = state.get("duration_weeks") or 4
        weekly_hours = state.get("weekly_hours") or 10
        topic = state.get("topic") or "Programming"

        return {
            "title": f"{topic} Basic Learning Path",
            "level": state.get("level", "beginner"),
            "duration_weeks": duration_weeks,
            "weekly_hours": weekly_hours,
            "modules": [
                {
                    "week": i + 1,
                    "title": f"{topic} 학습 - {i + 1}주차",
                    "description": f"{topic} 기본 개념 학습",
                    "estimated_hours": weekly_hours,
                    "objectives": [f"{topic} 기본 이해"],
                    "resources": {"videos": [], "documents": [], "web_links": []}
                }
                for i in range(duration_weeks)
            ],
            "overall_goal": f"Learn {topic} fundamentals",
            "session_id": state.get("session_id", "unknown"),
            "generated_at": "fallback",
            "fallback": True
        }

    async def generate_curriculum(
        self,
        session_id: str,
        topic: str,
        constraints: str,
        goal: str,
        user_message: str = None
    ) -> Dict[str, Any]:
        """커리큘럼 생성 실행"""

        # 초기 상태 생성
        initial_state = create_initial_state(
            session_id=session_id,
            topic=topic,
            constraints=constraints,
            goal=goal,
            user_message=user_message
        )

        try:
            # 워크플로우 실행
            final_state = await self.workflow.ainvoke(initial_state)

            # 결과 반환
            if final_state.get("final_curriculum"):
                return final_state["final_curriculum"]
            else:
                raise Exception("Workflow completed but no curriculum generated")

        except Exception as e:
            print(f"ERROR: Workflow execution failed: {e}")
            # 최종 fallback
            return self._create_fallback_curriculum(initial_state)


def create_curriculum_workflow(llm: ChatOpenAI) -> CurriculumGeneratorWorkflow:
    """커리큘럼 생성 워크플로우 팩토리 함수"""
    return CurriculumGeneratorWorkflow(llm)