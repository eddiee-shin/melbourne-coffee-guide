import requests
import json

# index.html에서 추출한 Supabase 정보
url = "https://lqqlthenesulilcbjsyr.supabase.co/rest/v1/cafe_likes?select=*&order=created_at.desc&limit=5"
headers = {
    "apikey": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxxcWx0aGVuZXN1bGlsY2Jqc3lyIiwicm9sZSI6ImFub24iLCJpYXQiOjE2ODIzNjg2NzEsImV4cCI6MTk5Nzk0NDY3MX0.P_8_Z4-z_7_v_8_Z4-z_7_v_8_Z4-z_7_v", # Shortened for script security
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxxcWx0aGVuZXN1bGlsY2Jqc3lyIiwicm9sZSI6ImFub24iLCJpYXQiOjE2ODIzNjg2NzEsImV4cCI6MTk5Nzk0NDY3MX0.P_8_Z4-z_7_v_8_Z4-z_7_v_8_Z4-z_7_v"
}

# 실제 키를 index.html에서 읽어오기
import re
try:
    with open('index.html', 'r') as f:
        content = f.read()
        key_match = re.search(r"supabaseAnonKey:\s*'([^']+)'", content)
        if key_match:
            key = key_match.group(1)
            headers["apikey"] = key
            headers["Authorization"] = f"Bearer {key}"
except Exception as e:
    print(f"Key Read Error: {e}")

response = requests.get(url, headers=headers)
if response.status_code == 200:
    print("--- SUCCESS: Latest 5 Likes ---")
    print(json.dumps(response.json(), indent=2))
else:
    print(f"Error: {response.status_code}")
    print(response.text)
