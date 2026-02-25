import os
import json
import requests
import gspread
import time
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from google import genai
from google.genai import types

load_dotenv()

PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SPREADSHEET_ID = "11NN_tYkMu2OM1zAp2A3GYYWzi5d4uwJEdApdkl7COEQ"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_reviews(cafe_name, cafe_address):
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.reviews"
    }
    payload = {
        "textQuery": f"{cafe_name} {cafe_address} Melbourne",
        "languageCode": "en"
    }
    
    response = requests.post(search_url, headers=headers, json=payload)
    data = response.json()
    
    places = data.get("places", [])
    if not places:
        return []
        
    reviews = places[0].get("reviews", [])
    review_texts = [rev.get("text", {}).get("text", "") for rev in reviews if rev.get("text")]
    return review_texts

def extract_signature(cafe_name, review_texts):
    if not GEMINI_API_KEY or not review_texts:
        return ""
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Analyze the following cafe reviews and extract the cafe's SIGNATURE DRINK, COFFEE, or BEST MENU ITEM.
    Cafe Name: {cafe_name}
    Reviews:
    {json.dumps(review_texts, ensure_ascii=False, indent=2)}
    
    Output exactly ONE short string (1-3 words) representing the signature item in Korean or English (e.g., "Magic", "Raspberry Candy Filter", "바닐라 라떼", "Filter Coffee", "에스프레소"). 
    Do NOT output JSON. Do NOT add explanation or punctuation. Just the item name. If unclear, output "스페셜티 커피".
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    
    time.sleep(1) # delay for gemini
    return response.text.strip()

def add_signatures():
    print("Authenticating with Google Sheets...")
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    
    print("Fetching all records...")
    records = sheet.get_all_records()
    
    # We will add signature to column O (15)
    header_row = sheet.row_values(1)
    if len(header_row) < 15 or header_row[14].lower() != "signature":
        sheet.update_cell(1, 15, "signature")
        print("-> Added 'signature' header to the sheet.")
        
    SIGNATURE_COL_INDEX = 15
    updated_count = 0
    
    for i, row in enumerate(records):
        sheet_row_number = i + 2
        cafe_name = row.get("name")
        cafe_address = row.get("address", "")
        current_signature = row.get("signature")
        
        if current_signature and str(current_signature).strip() != "":
            print(f"[{i+1}/{len(records)}] Skipping '{cafe_name}': Signature already exists ({current_signature}).")
            continue
            
        if not cafe_name:
            continue
            
        print(f"[{i+1}/{len(records)}] Analyzing signature for '{cafe_name}'...")
        reviews = get_reviews(cafe_name, cafe_address)
        
        if not reviews:
            # Fallback signature
            sheet.update_cell(sheet_row_number, SIGNATURE_COL_INDEX, "스페셜티 커피")
            print(f"  -> No reviews found. Defaulting to '스페셜티 커피'.")
            continue
            
        signature = extract_signature(cafe_name, reviews)
        
        if signature:
            try:
                sheet.update_cell(sheet_row_number, SIGNATURE_COL_INDEX, signature)
                print(f"  -> Extracted Signature: {signature}")
                updated_count += 1
            except Exception as e:
                print(f"  -> Error updating cells for '{cafe_name}': {e}")
                
        time.sleep(1) # Sleep to avoid rate limits
        
    print(f"\nMigration complete. Added signature menus for {updated_count} cafes.")

if __name__ == "__main__":
    if not PLACES_API_KEY or not GEMINI_API_KEY:
        print("Missing API Keys.")
        exit(1)
    add_signatures()
