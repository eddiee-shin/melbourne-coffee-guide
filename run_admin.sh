#!/bin/bash

# 멜번 커피 가이드 - 관리자 서버 통합 실행 스크립트

echo "🚀 관리자 서버를 시작합니다..."

# 1. 포트 확인 (8001번이 이미 사용 중인지 체크)
PORT=8001
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️  알림: $PORT번 포트가 이미 사용 중입니다. 기존 프로세스를 종료하거나 해당 페이지를 새로고침 하세요."
    echo "현재 실행 중인 서버로 계속 진행합니다..."
else
    # 2. 실행
    echo "🔗 접속 주소: http://127.0.0.1:$PORT/admin.html"
    python3 scripts/admin_server.py
fi
