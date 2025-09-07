#!/usr/bin/env python3
"""
최적화된 generate_curriculum.py 테스트 스크립트
"""
import asyncio
import sys
import os
sys.path.append('servers')

from generate_curriculum import (
    session_loader,
    generate_curriculum_from_session,
    generate_curriculums_from_all_sessions,
    list_session_topics,
    get_curriculum,
    search_learning_resources
)

async def test_optimized_curriculum():
    """최적화된 커리큘럼 생성 기능 테스트"""
    print("🧪 Testing Optimized Curriculum Generation")
    print("=" * 60)
    
    # 1. 세션 목록 확인
    print("\n1️⃣ Testing session discovery...")
    try:
        topics_result = await list_session_topics()
        print(f"✅ Sessions found: {topics_result['total_sessions']}")
        print(f"✅ Unique topics: {topics_result['unique_topics']}")
        
        if topics_result.get('topics'):
            for topic, count in topics_result['topics'].items():
                print(f"  📚 {topic}: {count} session(s)")
        
        test_sessions = topics_result.get('all_sessions', [])
        print(f"✅ Available sessions: {len(test_sessions)}")
        
    except Exception as e:
        print(f"❌ Session discovery failed: {e}")
        return
    
    # 2. 개별 세션 커리큘럼 생성 테스트
    if test_sessions:
        sample_session = test_sessions[0]
        session_id = sample_session['session_id']
        
        print(f"\n2️⃣ Testing single session curriculum generation...")
        print(f"  Session ID: {session_id}")
        print(f"  Topic: {sample_session['topic']}")
        print(f"  Constraints: {sample_session['constraints']}")
        print(f"  Goal: {sample_session['goal']}")
        
        try:
            curriculum = await generate_curriculum_from_session(session_id)
            
            if "error" in curriculum:
                print(f"❌ Curriculum generation failed: {curriculum['error']}")
            else:
                print(f"✅ Curriculum generated successfully!")
                print(f"  Title: {curriculum.get('title')}")
                print(f"  Level: {curriculum.get('level')}")
                print(f"  Duration: {curriculum.get('duration_weeks')} weeks")
                print(f"  Modules: {len(curriculum.get('modules', []))}")
                print(f"  Resources: {len(curriculum.get('resources', []))}")
                
                # 첫 번째 모듈 정보 출력
                modules = curriculum.get('modules', [])
                if modules:
                    first_module = modules[0]
                    print(f"\n  📖 First Module:")
                    print(f"    Week: {first_module.get('week')}")
                    print(f"    Title: {first_module.get('title')}")
                    print(f"    Hours: {first_module.get('estimated_hours')}")
                    print(f"    Objectives: {len(first_module.get('objectives', []))}")
                
        except Exception as e:
            print(f"❌ Single curriculum generation failed: {e}")
    
    # 3. 배치 커리큘럼 생성 테스트
    print(f"\n3️⃣ Testing batch curriculum generation...")
    try:
        batch_result = await generate_curriculums_from_all_sessions()
        
        print(f"✅ Batch processing completed!")
        print(f"  Sessions processed: {batch_result['sessions_processed']}")
        print(f"  Curriculums generated: {batch_result['curriculums_generated']}")
        print(f"  Success rate: {batch_result['success_rate']}")
        
        if batch_result.get('successful_generations'):
            print(f"\n  ✅ Successful generations:")
            for success in batch_result['successful_generations']:
                print(f"    - {success['session_id']}: {success['topic']}")
        
        if batch_result.get('failed_generations'):
            print(f"\n  ❌ Failed generations:")
            for failure in batch_result['failed_generations']:
                print(f"    - {failure['session_id']}: {failure['error']}")
        
    except Exception as e:
        print(f"❌ Batch generation failed: {e}")
    
    # 4. 커리큘럼 조회 테스트
    if test_sessions:
        session_id = test_sessions[0]['session_id']
        print(f"\n4️⃣ Testing curriculum retrieval...")
        try:
            retrieved = await get_curriculum(session_id, 0)
            
            if "error" in retrieved:
                print(f"⚠️ No curriculum found for {session_id}")
            else:
                print(f"✅ Curriculum retrieved successfully!")
                print(f"  Created: {retrieved.get('created_at')}")
                print(f"  ID: {retrieved.get('id')}")
        
        except Exception as e:
            print(f"❌ Curriculum retrieval failed: {e}")
    
    # 5. 학습 자료 검색 테스트
    print(f"\n5️⃣ Testing resource search...")
    try:
        if test_sessions:
            test_topic = test_sessions[0]['topic']
        else:
            test_topic = "Python"
        
        resources = await search_learning_resources(test_topic, 5)
        
        print(f"✅ Resource search completed!")
        print(f"  Topic: {resources['topic']}")
        print(f"  Resources found: {resources['total_resources']}")
        
        if resources.get('resources'):
            print(f"  📚 Sample resources:")
            for i, resource in enumerate(resources['resources'][:3]):
                print(f"    {i+1}. {resource['title']}")
        
    except Exception as e:
        print(f"❌ Resource search failed: {e}")
    
    print("\n🎉 All tests completed!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_optimized_curriculum())