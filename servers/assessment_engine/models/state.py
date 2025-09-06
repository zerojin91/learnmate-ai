"""
User Assessment State Models
사용자 평가 상태 모델들
"""

from dataclasses import dataclass
from typing import Optional, Dict, List
from datetime import datetime


@dataclass
class UserAssessment:
    """사용자 평가 상태를 저장하는 데이터 클래스"""
    
    session_id: str
    current_stage: str = "topic"
    
    # 평가 결과들
    topic: Optional[str] = None
    topic_confidence: Optional[float] = None
    
    goal: Optional[str] = None
    goal_category: Optional[str] = None
    goal_confidence: Optional[float] = None
    
    time_weekly_hours: Optional[int] = None
    time_category: Optional[str] = None
    time_confidence: Optional[float] = None
    
    budget_category: Optional[str] = None
    budget_max_monthly: Optional[int] = None
    budget_confidence: Optional[float] = None
    
    level: Optional[str] = None
    level_confidence: Optional[float] = None
    
    # 메타데이터
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """딕셔너리로 변환"""
        return {
            "session_id": self.session_id,
            "current_stage": self.current_stage,
            "topic": self.topic,
            "topic_confidence": self.topic_confidence,
            "goal": self.goal,
            "goal_category": self.goal_category,
            "goal_confidence": self.goal_confidence,
            "time_weekly_hours": self.time_weekly_hours,
            "time_category": self.time_category,
            "time_confidence": self.time_confidence,
            "budget_category": self.budget_category,
            "budget_max_monthly": self.budget_max_monthly,
            "budget_confidence": self.budget_confidence,
            "level": self.level,
            "level_confidence": self.level_confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }