"""
LangGraph 커리큘럼 생성 시스템의 상태 정의
"""
from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
from enum import Enum


class ProcessingPhase(str, Enum):
    """처리 단계 정의"""
    PARAMETER_ANALYSIS = "parameter_analysis"
    LEARNING_PATH_PLANNING = "learning_path_planning"
    MODULE_STRUCTURE_DESIGN = "module_structure_design"
    CONTENT_DETAIL_GENERATION = "content_detail_generation"
    RESOURCE_COLLECTION = "resource_collection"
    LECTURE_CONTENT_GENERATION = "lecture_content_generation"
    VALIDATION = "validation"
    INTEGRATION = "integration"
    COMPLETED = "completed"
    ERROR = "error"


class CurriculumState(TypedDict):
    """LangGraph에서 사용할 전체 상태"""
    # 입력 정보
    session_id: str
    topic: str
    constraints: str
    goal: str
    user_message: Optional[str]

    # 추출된 파라미터
    level: Optional[str]
    duration_weeks: Optional[int]
    focus_areas: Optional[List[str]]
    weekly_hours: Optional[int]

    # 처리 상태
    current_phase: ProcessingPhase
    phase_history: List[Dict[str, Any]]
    errors: List[str]

    # 분석 결과
    learning_path_analysis: Optional[str]
    overall_goal: Optional[str]

    # 모듈 구조
    module_structure: Optional[List[Dict[str, Any]]]
    detailed_modules: Optional[List[Dict[str, Any]]]

    # 리소스
    basic_resources: Optional[List[Dict[str, Any]]]
    module_resources: Optional[Dict[str, List[Dict[str, Any]]]]

    # 최종 결과
    final_curriculum: Optional[Dict[str, Any]]
    curriculum_id: Optional[int]

    # 메타데이터
    started_at: datetime
    completed_at: Optional[datetime]
    processing_time: Optional[float]


def create_initial_state(
    session_id: str,
    topic: str,
    constraints: str,
    goal: str,
    user_message: Optional[str] = None
) -> CurriculumState:
    """초기 상태 생성"""
    return CurriculumState(
        session_id=session_id,
        topic=topic,
        constraints=constraints,
        goal=goal,
        user_message=user_message,

        level=None,
        duration_weeks=None,
        focus_areas=None,
        weekly_hours=None,

        current_phase=ProcessingPhase.PARAMETER_ANALYSIS,
        phase_history=[],
        errors=[],

        learning_path_analysis=None,
        overall_goal=None,

        module_structure=None,
        detailed_modules=None,

        basic_resources=None,
        module_resources=None,

        final_curriculum=None,
        curriculum_id=None,

        started_at=datetime.now(),
        completed_at=None,
        processing_time=None
    )


def update_phase(state: CurriculumState, new_phase: ProcessingPhase, message: str = "") -> None:
    """상태의 처리 단계 업데이트"""
    state["phase_history"].append({
        "phase": state["current_phase"],
        "completed_at": datetime.now(),
        "message": message
    })
    state["current_phase"] = new_phase


def add_error(state: CurriculumState, error: str) -> None:
    """에러 추가"""
    state["errors"].append(f"[{datetime.now().isoformat()}] {error}")
    state["current_phase"] = ProcessingPhase.ERROR