"""
Session Manager
세션 및 대화 상태 관리
"""

import uuid
import json
from datetime import datetime
from typing import Dict, List, Optional


class SessionManager:
    """학습 평가 세션 관리 클래스"""
    
    def __init__(self):
        self.sessions: Dict[str, dict] = {}
        self.assessment_stages = ["topic", "goal", "time", "budget", "level", "completed"]
    
    def create_session(self) -> str:
        """새로운 세션 생성"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "current_stage": "topic",
            "stage_index": 0,
            "conversation_history": [],
            "assessment_data": {
                "topic": None,
                "goal": None, 
                "time": None,
                "budget": None,
                "level": None
            },
            "is_completed": False
        }
        return session_id
    
    def get_session(self, session_id: str) -> Optional[dict]:
        """세션 정보 조회"""
        return self.sessions.get(session_id)
    
    def get_current_stage(self, session_id: str) -> str:
        """현재 평가 단계 조회"""
        session = self.get_session(session_id)
        if not session:
            return "topic"  # 기본값
        return session["current_stage"]
    
    def update_stage(self, session_id: str, stage: str) -> bool:
        """평가 단계 업데이트"""
        session = self.get_session(session_id)
        if not session:
            return False
            
        if stage in self.assessment_stages:
            session["current_stage"] = stage
            session["stage_index"] = self.assessment_stages.index(stage)
            if stage == "completed":
                session["is_completed"] = True
            return True
        return False
    
    def next_stage(self, session_id: str) -> str:
        """다음 단계로 이동"""
        session = self.get_session(session_id)
        if not session:
            return "topic"
            
        current_index = session["stage_index"]
        if current_index < len(self.assessment_stages) - 1:
            next_index = current_index + 1
            next_stage = self.assessment_stages[next_index]
            self.update_stage(session_id, next_stage)
            return next_stage
        return session["current_stage"]
    
    def add_conversation(self, session_id: str, message: str, role: str = "user") -> bool:
        """대화 기록 추가"""
        session = self.get_session(session_id)
        if not session:
            return False
            
        session["conversation_history"].append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "message": message,
            "stage": session["current_stage"]
        })
        return True
    
    def get_conversation_history(self, session_id: str, limit: int = 10) -> List[dict]:
        """대화 기록 조회"""
        session = self.get_session(session_id)
        if not session:
            return []
        return session["conversation_history"][-limit:]
    
    def update_assessment_data(self, session_id: str, stage: str, data: dict) -> bool:
        """평가 데이터 업데이트"""
        session = self.get_session(session_id)
        if not session:
            return False
            
        if stage in session["assessment_data"]:
            session["assessment_data"][stage] = data
            return True
        return False
    
    def get_assessment_data(self, session_id: str) -> dict:
        """평가 데이터 조회"""
        session = self.get_session(session_id)
        if not session:
            return {}
        return session["assessment_data"]
    
    def get_completion_progress(self, session_id: str) -> dict:
        """완료 진행률 조회"""
        session = self.get_session(session_id)
        if not session:
            return {"progress": 0, "current_stage": "topic", "completed_stages": []}
            
        completed_stages = []
        for stage in self.assessment_stages[:-1]:  # "completed" 제외
            if session["assessment_data"][stage] is not None:
                completed_stages.append(stage)
        
        progress = len(completed_stages) / (len(self.assessment_stages) - 1) * 100
        
        return {
            "progress": round(progress, 1),
            "current_stage": session["current_stage"],
            "completed_stages": completed_stages,
            "total_stages": len(self.assessment_stages) - 1
        }
    
    def get_active_sessions_count(self) -> int:
        """활성 세션 수 조회"""
        return len([s for s in self.sessions.values() if not s["is_completed"]])
    
    def cleanup_old_sessions(self, hours: int = 24) -> int:
        """오래된 세션 정리"""
        from datetime import timedelta
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        old_sessions = []
        for session_id, session in self.sessions.items():
            created_at = datetime.fromisoformat(session["created_at"])
            if created_at < cutoff_time:
                old_sessions.append(session_id)
        
        for session_id in old_sessions:
            del self.sessions[session_id]
            
        return len(old_sessions)