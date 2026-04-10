import requests
import json
import re

# index.html에서 키 추출
key = ""
try:
    with open('index.html', 'r') as f:
        content = f.read()
        key_match = re.search(r"supabaseAnonKey:\s*'([^']+)'", content)
        if key_match:
            key = key_match.group(1)
except Exception as e:
    print(f"Key Read Error: {e}")

if not key:
    print("API Key not found!")
    exit(1)

# RPC가 비활성화되어 있을 수 있으므로, 간접적으로 정보를 유추하기 위해
# 빈 INSERT를 시도하여 발생하는 에러 메시지를 통해 권한을 유추하거나
# pg_catalog 조회가 가능한지 확인 (보통 anon은 막혀있으므로 테스트 용도)

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json",
    "Prefer": "return=minimal"
}

# 1. 좋아요 테이블에 아주 이상한 데이터를 INSERT 시도 (에러 메시지 확인용)
print("--- Testing INSERT on cafe_likes ---")
test_data = {"cafe_id": "00000000-0000-0000-0000-000000000000", "viewer_id": "test_diagnose"}
res = requests.post("https://lqqlthenesulilcbjsyr.supabase.co/rest/v1/cafe_likes", headers=headers, json=test_data)
print(f"Status: {res.status_code}")
print(f"Response: {res.text}")

# 2. 댓글 테이블 테스트
print("\n--- Testing INSERT on cafe_comments ---")
res = requests.post("https://lqqlthenesulilcbjsyr.supabase.co/rest/v1/cafe_comments", headers=headers, json={})
print(f"Status: {res.status_code}")
print(f"Response: {res.text}")
