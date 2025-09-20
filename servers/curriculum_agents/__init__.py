"""
Curriculum Agents Package
"""
from .state import CurriculumState, ProcessingPhase, create_initial_state
from .base_agent import BaseAgent
from .parameter_analyzer import ParameterAnalyzerAgent
from .learning_path_planner import LearningPathPlannerAgent
from .module_structure_agent import ModuleStructureAgent
from .content_detail_agent import ContentDetailAgent
from .resource_collector import ResourceCollectorAgent
from .validation_agent import ValidationAgent
from .integration_agent import IntegrationAgent
from .workflow import CurriculumGeneratorWorkflow, create_curriculum_workflow

__all__ = [
    'CurriculumState',
    'ProcessingPhase',
    'create_initial_state',
    'BaseAgent',
    'ParameterAnalyzerAgent',
    'LearningPathPlannerAgent',
    'ModuleStructureAgent',
    'ContentDetailAgent',
    'ResourceCollectorAgent',
    'ValidationAgent',
    'IntegrationAgent',
    'CurriculumGeneratorWorkflow',
    'create_curriculum_workflow'
]