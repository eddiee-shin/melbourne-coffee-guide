import os
import requests
import gspread
import time
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
SPREADSHEET_ID = "11NN_tYkMu2OM1zAp2A3GYYWzi5d4uwJEdApdkl7COEQ"
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def build_photo_url(photo_reference):
    if not photo_reference:
        return ""
    return f"https://places.googleapis.com/v1/{photo_reference}/media?key={PLACES_API_KEY}&maxHeightPx=400&maxWidthPx=400"

def get_photo_reference(cafe_name):
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.photos"
    }
    payload = {
        "textQuery": f"{cafe_name} specialty coffee Melbourne",
        "languageCode": "en"
    }
    
    response = requests.post(search_url, headers=headers, json=payload)
    data = response.json()
    
    places = data.get("places", [])
    if not places:
        return None
        
    photos = places[0].get("photos", [])
    if not photos:
        return None
        
    return photos[0].get("name", "")

def migrate_images():
    print("Authenticating with Google Sheets...")
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    
    print("Fetching all records...")
    records = sheet.get_all_records()
    
    # We need to update column J (10th column). Rows are 1-indexed, headers are row 1.
    IMAGE_COL_INDEX = 10
    
    updated_count = 0
    for i, row in enumerate(records):
        sheet_row_number = i + 2 # +1 for 0-index -> 1-index, +1 to skip header row
        
        cafe_name = row.get("name")
        current_image = row.get("image", "")
        
        if not cafe_name:
            continue
            
        # Already a URL, skip
        if current_image.startswith("http"):
            continue
            
        print(f"[{i+1}/{len(records)}] Finding image for '{cafe_name}'...")
        photo_ref = get_photo_reference(cafe_name)
        
        if photo_ref:
            new_url = build_photo_url(photo_ref)
            try:
                sheet.update_cell(sheet_row_number, IMAGE_COL_INDEX, new_url)
                print(f"  -> Successfully updated image for '{cafe_name}'")
                updated_count += 1
            except Exception as e:
                print(f"  -> Error updating cell for '{cafe_name}': {e}")
        else:
            print(f"  -> No photo found on Google Maps for '{cafe_name}'.")
            
        time.sleep(1) # Sleep to avoid rate limits
        
    print(f"\nMigration complete. Updated {updated_count} cafes.")

if __name__ == "__main__":
    if not PLACES_API_KEY:
        print("Missing API Keys.")
        exit(1)
    migrate_images()
