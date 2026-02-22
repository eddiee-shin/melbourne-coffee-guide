import json
import csv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SPREADSHEET_ID = "11NN_tYkMu2OM1zAp2A3GYYWzi5d4uwJEdApdkl7COEQ"

print("Connecting to Google Sheets...")
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

print("Fetching all records...")
records = sheet.get_all_records()

print(f"Fetched {len(records)} records. Writing to data.json...")
with open("data.json", "w", encoding="utf-8") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

print("Writing to data.csv...")
if records:
    with open("data.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

print("Done sync!")
