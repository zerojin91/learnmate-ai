#!/bin/bash
# 커리큘럼 MCP 웹 API 테스트 스크립트

echo "=== 🌐 커리큘럼 MCP 웹 API 테스트 ==="
echo ""

# 서버가 실행 중인지 확인
echo "🔍 서버 상태 확인 중..."
if curl -s http://localhost:8000 > /dev/null; then
    echo "✅ 서버가 실행 중입니다 (http://localhost:8000)"
else
    echo "❌ 서버가 실행되지 않았습니다. 먼저 'python main.py'로 서버를 시작해주세요."
    exit 1
fi

echo ""
echo "1️⃣ 새로운 커리큘럼 생성 요청..."

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "사용자 my_user_123을 위한 JavaScript 4주 커리큘럼을 생성해주세요. 초급자 레벨이고 프론트엔드 개발에 집중하고 싶습니다."
  }' | jq -r '.response'

echo ""
echo "2️⃣ 데이터베이스 통계 확인..."

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me the database statistics"
  }' | jq -r '.response'

echo ""
echo "✅ API 테스트 완료!"