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

def get_coordinates(cafe_name, cafe_address):
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.location"
    }
    payload = {
        "textQuery": f"{cafe_name} {cafe_address} Melbourne",
        "languageCode": "en"
    }
    
    response = requests.post(search_url, headers=headers, json=payload)
    data = response.json()
    
    places = data.get("places", [])
    if not places:
        return None, None
        
    location = places[0].get("location", {})
    lat = location.get("latitude")
    lng = location.get("longitude")
    
    return lat, lng

def add_coordinates():
    print("Authenticating with Google Sheets...")
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(SPREADSHEET_ID).sheet1
    
    print("Fetching all records...")
    records = sheet.get_all_records()
    
    # We will add Lat and Lng to columns M (13) and N (14)
    # 1. Ensure headers exist
    header_row = sheet.row_values(1)
    if len(header_row) < 13 or header_row[12].lower() != "lat":
        sheet.update_cell(1, 13, "lat")
        sheet.update_cell(1, 14, "lng")
        print("-> Added 'lat' and 'lng' headers to the sheet.")
        
    LAT_COL_INDEX = 13
    LNG_COL_INDEX = 14
    
    updated_count = 0
    for i, row in enumerate(records):
        sheet_row_number = i + 2
        
        cafe_name = row.get("name")
        cafe_address = row.get("address", "")
        
        # Check if already has coordinates to avoid unnecessary API calls
        current_lat = row.get("lat")
        current_lng = row.get("lng")
        
        # Depending on how gspread parses empty cells, it might be an empty string
        if current_lat and str(current_lat).strip() != "" and current_lng and str(current_lng).strip() != "":
            print(f"[{i+1}/{len(records)}] Skipping '{cafe_name}': Coordinates already exist.")
            continue
            
        if not cafe_name:
            continue
            
        print(f"[{i+1}/{len(records)}] Finding coordinates for '{cafe_name}'...")
        lat, lng = get_coordinates(cafe_name, cafe_address)
        
        if lat and lng:
            try:
                sheet.update_cell(sheet_row_number, LAT_COL_INDEX, lat)
                sheet.update_cell(sheet_row_number, LNG_COL_INDEX, lng)
                print(f"  -> Added coordinates: {lat}, {lng}")
                updated_count += 1
            except Exception as e:
                print(f"  -> Error updating cells for '{cafe_name}': {e}")
        else:
            print(f"  -> No exact location found on Google Maps for '{cafe_name}'.")
            
        time.sleep(1) # Sleep to avoid rate limits
        
    print(f"\nMigration complete. Added coordinates for {updated_count} cafes.")

if __name__ == "__main__":
    if not PLACES_API_KEY:
        print("Missing API Keys.")
        exit(1)
    add_coordinates()
