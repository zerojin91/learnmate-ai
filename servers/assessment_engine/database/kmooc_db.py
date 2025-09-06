"""
KMOOC Database Mock - 간단한 버전
평가 시스템에 필요한 최소 기능만 제공
"""

class KMOOCDatabase:
    """KMOOC 강의 데이터베이스 Mock 클래스 - 간단한 버전"""
    
    def __init__(self):
        pass
    
    def get_total_courses_count(self) -> int:
        """전체 강의 수 조회 - Mock 데이터"""
        return 1500  # 가상의 강의 수