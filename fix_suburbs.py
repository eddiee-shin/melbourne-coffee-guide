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

def get_correct_suburb(cafe_name, cafe_address):
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.addressComponents"
    }
    payload = {
        "textQuery": f"{cafe_name} {cafe_address} Melbourne",
        "languageCode": "en"
    }
    
    response = requests.post(search_url, headers=headers, json=payload)
    data = response.json()
    
    places = data.get("places", [])
    if not places:
        return None
        
    components = places[0].get("addressComponents", [])
    
    # Try to find locality first, then sublocality
    locality = None
    sublocality = None
    
    for comp in components:
        types = comp.get("types", [])
        if "locality" in types:
            locality = comp.get("shortText", "")
        if "sublocality" in types or "sublocality_level_1" in types:
            sublocality = comp.get("shortText", "")
            
    # Sublocality is usually more specific (e.g. Southbank instead of Melbourne)
    result = sublocality if sublocality else locality
    
    if result and result.lower() == "melbourne":
        return "CBD"
    return result

def fix_suburbs():
    print("Authenticating with Google Sheets...")
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    
    print("Fetching all records...")
    records = sheet.get_all_records()
    
    # Column C (3rd column) is suburb. Rows are 1-indexed, headers are row 1.
    SUBURB_COL_INDEX = 3
    
    updated_count = 0
    for i, row in enumerate(records):
        sheet_row_number = i + 2
        
        cafe_name = row.get("name")
        cafe_address = row.get("address", "") # Address might not be in Google Sheet, we use name search fallback
        current_suburb = row.get("suburb", "")
        
        if not cafe_name:
            continue
            
        print(f"[{i+1}/{len(records)}] Finding correct suburb for '{cafe_name}'...")
        new_suburb = get_correct_suburb(cafe_name, cafe_address)
        
        if new_suburb:
            if new_suburb != current_suburb:
                try:
                    sheet.update_cell(sheet_row_number, SUBURB_COL_INDEX, new_suburb)
                    print(f"  -> Updated suburb: '{current_suburb}' -> '{new_suburb}'")
                    updated_count += 1
                except Exception as e:
                    print(f"  -> Error updating cell for '{cafe_name}': {e}")
            else:
                print(f"  -> Suburb already correct: '{current_suburb}'")
        else:
            print(f"  -> No exact location component found on Google Maps for '{cafe_name}'.")
            
        time.sleep(1) # Sleep to avoid rate limits
        
    print(f"\nMigration complete. Updated {updated_count} cafes.")

if __name__ == "__main__":
    if not PLACES_API_KEY:
        print("Missing API Keys.")
        exit(1)
    fix_suburbs()
