"""
LangGraph 기반 커리큘럼 생성 워크플로우
"""
import os
import json
from typing import Dict, Any
from datetime import datetime
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

    def _save_progress(self, session_id: str, phase: ProcessingPhase, step_name: str, message: str = "", progress_percent: int = 0):
        """진행 상황을 파일에 저장"""
        try:
            progress_dir = "data/progress"
            os.makedirs(progress_dir, exist_ok=True)

            progress_file = os.path.join(progress_dir, f"{session_id}.json")

            # 단계별 사용자 친화적 매핑
            phase_mapping = {
                ProcessingPhase.PARAMETER_ANALYSIS: {
                    "step": 1,
                    "total": 5,
                    "name": "학습 요구사항 분석",
                    "description": "사용자의 학습 목표와 조건을 분석하고 있습니다"
                },
                ProcessingPhase.LEARNING_PATH_PLANNING: {
                    "step": 2,
                    "total": 5,
                    "name": "학습 경로 설계",
                    "description": "최적의 학습 경로를 설계하고 있습니다"
                },
                ProcessingPhase.MODULE_STRUCTURE_DESIGN: {
                    "step": 3,
                    "total": 5,
                    "name": "커리큘럼 구조 생성",
                    "description": "주차별 커리큘럼 구조를 생성하고 있습니다"
                },
                ProcessingPhase.CONTENT_DETAIL_GENERATION: {
                    "step": 4,
                    "total": 5,
                    "name": "학습 자료 수집",
                    "description": "학습에 필요한 자료들을 수집하고 있습니다"
                },
                ProcessingPhase.RESOURCE_COLLECTION: {
                    "step": 4,
                    "total": 5,
                    "name": "학습 자료 수집",
                    "description": "학습에 필요한 자료들을 수집하고 있습니다"
                },
                ProcessingPhase.VALIDATION: {
                    "step": 5,
                    "total": 5,
                    "name": "최종 검토 및 완성",
                    "description": "커리큘럼을 검토하고 최종 완성하고 있습니다"
                },
                ProcessingPhase.INTEGRATION: {
                    "step": 5,
                    "total": 5,
                    "name": "최종 검토 및 완성",
                    "description": "커리큘럼을 검토하고 최종 완성하고 있습니다"
                },
                ProcessingPhase.COMPLETED: {
                    "step": 5,
                    "total": 5,
                    "name": "완료",
                    "description": "커리큘럼 생성이 완료되었습니다"
                }
            }

            phase_info = phase_mapping.get(phase, {
                "step": 1,
                "total": 5,
                "name": step_name,
                "description": message
            })

            progress_data = {
                "session_id": session_id,
                "current_phase": phase.value,
                "step_name": step_name,
                "message": message,
                "progress_percent": progress_percent,
                "updated_at": datetime.now().isoformat(),
                "phase_info": phase_info
            }

            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"ERROR: Failed to save progress: {e}")

    def _wrap_agent_execution(self, agent_func, phase: ProcessingPhase, step_name: str):
        """에이전트 실행을 래핑하여 진행 상황 추적"""
        async def wrapped_execution(state: CurriculumState):
            session_id = state.get("session_id", "unknown")

            # 단계 시작 로그
            self._save_progress(session_id, phase, step_name, f"{step_name} 시작",
                             int((phase.value.split('_')[0] if hasattr(phase.value, 'split') else 1) * 20))

            try:
                # 원래 에이전트 실행
                result = await agent_func(state)

                # 단계 완료 로그
                self._save_progress(session_id, phase, step_name, f"{step_name} 완료",
                                 int((phase.value.split('_')[0] if hasattr(phase.value, 'split') else 1) * 20))

                return result
            except Exception as e:
                self._save_progress(session_id, ProcessingPhase.ERROR, step_name,
                                 f"{step_name} 오류: {str(e)}", 0)
                raise e

        return wrapped_execution

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

        # 노드 추가 (진행 상황 추적을 위해 래핑)
        workflow.add_node("parameter_analysis",
                         self._wrap_agent_execution(agents["parameter_analyzer"].execute,
                                                   ProcessingPhase.PARAMETER_ANALYSIS, "학습 요구사항 분석"))
        workflow.add_node("learning_path_planning",
                         self._wrap_agent_execution(agents["learning_path_planner"].execute,
                                                   ProcessingPhase.LEARNING_PATH_PLANNING, "학습 경로 설계"))
        workflow.add_node("module_structure_design",
                         self._wrap_agent_execution(agents["module_structure_agent"].execute,
                                                   ProcessingPhase.MODULE_STRUCTURE_DESIGN, "커리큘럼 구조 생성"))
        workflow.add_node("content_detail_generation",
                         self._wrap_agent_execution(agents["content_detail_agent"].execute,
                                                   ProcessingPhase.CONTENT_DETAIL_GENERATION, "학습 내용 상세화"))
        workflow.add_node("resource_collection",
                         self._wrap_agent_execution(agents["resource_collector"].execute,
                                                   ProcessingPhase.RESOURCE_COLLECTION, "학습 자료 수집"))
        workflow.add_node("validation",
                         self._wrap_agent_execution(agents["validation_agent"].execute,
                                                   ProcessingPhase.VALIDATION, "최종 검토"))
        workflow.add_node("integration",
                         self._wrap_agent_execution(agents["integration_agent"].execute,
                                                   ProcessingPhase.INTEGRATION, "통합 및 완성"))
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

        # 초기 진행 상황 저장
        self._save_progress(session_id, ProcessingPhase.PARAMETER_ANALYSIS, "커리큘럼 생성 시작", "커리큘럼 생성을 시작합니다", 0)

        try:
            # 워크플로우 실행
            final_state = await self.workflow.ainvoke(initial_state)

            # 완료 진행 상황 저장
            self._save_progress(session_id, ProcessingPhase.COMPLETED, "완료", "커리큘럼 생성이 완료되었습니다", 100)

            # 결과 반환
            if final_state.get("final_curriculum"):
                return final_state["final_curriculum"]
            else:
                raise Exception("Workflow completed but no curriculum generated")

        except Exception as e:
            print(f"ERROR: Workflow execution failed: {e}")
            # 에러 진행 상황 저장
            self._save_progress(session_id, ProcessingPhase.ERROR, "오류", f"커리큘럼 생성 중 오류가 발생했습니다: {str(e)}", 0)
            # 최종 fallback
            return self._create_fallback_curriculum(initial_state)


def create_curriculum_workflow(llm: ChatOpenAI) -> CurriculumGeneratorWorkflow:
    """커리큘럼 생성 워크플로우 팩토리 함수"""
    return CurriculumGeneratorWorkflow(llm)