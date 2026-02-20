import os
import requests
import json
import traceback
import gspread
from dotenv import load_dotenv
from google import genai
from google.genai import types
from oauth2client.service_account import ServiceAccountCredentials

# Load environment variables from .env file
load_dotenv()

PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
# SPREADSHEET_ID from the URL provided earlier
SPREADSHEET_ID = "11NN_tYkMu2OM1zAp2A3GYYWzi5d4uwJEdApdkl7COEQ"

def get_existing_cafe_names():
    print("Fetching existing cafe list from Google Sheets...")
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(SPREADSHEET_ID).sheet1
        names = sheet.col_values(1) # Assuming 'name' is in column A (1)
        # Skip header row
        if names and names[0].lower() == 'name':
            names = names[1:]
        print(f"-> Found {len(names)} existing cafes in database.")
        return names, sheet
    except Exception as e:
        print(f"Failed to connect to Google Sheets: {e}")
        return [], None

def build_photo_url(photo_reference):
    if not photo_reference:
        return ""
    return f"https://places.googleapis.com/v1/{photo_reference}/media?key={PLACES_API_KEY}&maxHeightPx=400&maxWidthPx=400"

def search_cafes(query):
    print(f"\nSearching Google Maps for: '{query}'...")
    
    search_url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": PLACES_API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.rating,places.userRatingCount,places.formattedAddress,places.reviews,places.photos"
    }
    payload = {
        "textQuery": query,
        "languageCode": "ko"
    }
    
    response = requests.post(search_url, headers=headers, json=payload)
    data = response.json()
    
    if "error" in data:
        print(f"Error searching: {data['error'].get('message')}")
        return []
        
    places = data.get("places", [])
    if not places:
        print("No cafes found.")
        return []
        
    results = []
    for place in places:
        name = place.get("displayName", {}).get("text", "Unknown")
        
        # Safely extract text from reviews
        raw_reviews = place.get("reviews", [])
        review_texts = []
        for r in raw_reviews:
            text = r.get("text", {}).get("text", "")
            if text: review_texts.append(text)
            
        # Extract Photo Reference
        photos = place.get("photos", [])
        photo_ref = photos[0].get("name", "") if photos else ""
        
        if not review_texts:
            print(f"  -> Skipping '{name}' (No reviews available for AI analysis)")
            continue
            
        results.append({
            "name": name,
            "address": place.get("formattedAddress", ""),
            "rating": place.get("rating", 0),
            "reviews": place.get("userRatingCount", 0),
            "review_texts": review_texts,
            "photo_reference": photo_ref
        })

    print(f"-> Found {len(results)} candidate cafes with reviews from Google Maps.")
    return results

def analyze_cafe_with_ai(cafe_data, existing_names):
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not found in .env. Skipping AI analysis.")
        return None
        
    print(f"\n[AI] Analyzing reviews for '{cafe_data['name']}'...")
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    prompt = f"""
    Analyze the following cafe based on its name, address, and Google reviews.
    Cafe Name: {cafe_data['name']}
    Address: {cafe_data['address']}
    
    Here is a list of cafes ALREADY in our database (some might be in English, some in Korean):
    {json.dumps(existing_names, ensure_ascii=False)}
    
    Reviews:
    {json.dumps(cafe_data['review_texts'], ensure_ascii=False, indent=2)}
    
    Please output a JSON object with EXACTLY these keys:
    - "isDuplicate": boolean (true/false). Set to true ONLY if this cafe conceptually already exists in the provided list. Be extremely smart about English/Korean translations (e.g. "듁스 커피 로스터스" is the same as "Dukes Coffee Roasters").
    - "location": string. Strictly map the address to ONE of these exactly: ["CBD", "North Melbourne", "South Melbourne", "Fitzroy/Collingwood", "Brunswick", "Others"].
    - "spectrum": integer from 1 to 5. 1=Very Fruity/Acidic, 3=Balanced, 5=Very Nutty/Chocolatey/Comforting.
    - "price": integer from 1 to 5. (1=Cheap, 5=Very Expensive).
    - "atmosphere": Array of 1 to 2 strings from this list exactly: ["modern", "cozy", "unique", "lively"]
    - "desc": A 1-2 sentence description in Korean about the vibe and coffee taste.
    - "oneLiner": A catchy, short one-liner in Korean (subtitle style).
    - "tags": Array of 2 strings. The 1st string MUST be exactly one of: ["Acidity ⭐⭐⭐⭐⭐", "Acidity ⭐⭐⭐⭐", "Balance ⭐⭐⭐⭐⭐", "Balance ⭐⭐⭐", "Nutty ⭐⭐⭐⭐⭐", "Nutty ⭐⭐⭐⭐"] matching the spectrum. The 2nd string is a short English catchy word (e.g. "Signature", "Hipster").
    
    Return ONLY JSON.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    
    try:
        result = json.loads(response.text)
        
        if result.get("isDuplicate", False):
            print(f"  -> AI DETECTED DUPLICATE: '{cafe_data['name']}' is already in the database under a different name/language. Skipping.")
            return None
            
        # Merge basic data + AI data + constructed image URL
        merged = {
            "name": cafe_data["name"],
            "location": result.get("location", "Others"), 
            "suburb": cafe_data["address"].split(",")[0].split(" ")[-1] if "," in cafe_data["address"] else "Melbourne",
            "spectrum": result.get("spectrum", 3),
            "price": result.get("price", 3),
            "atmosphere": result.get("atmosphere", ["cozy"]),
            "desc": result.get("desc", ""),
            "oneLiner": result.get("oneLiner", ""),
            "tags": result.get("tags", []),
            "image": build_photo_url(cafe_data["photo_reference"]),  # Hotlink URL mapped directly
            "rating": cafe_data["rating"],
            "reviews": cafe_data["reviews"]
        }
        return merged
    except Exception as e:
        print(f"Error parsing Gemini response: {e}")
        return None

def append_to_sheet(sheet, cafe_json):
    row = [
        cafe_json.get('name', ''),
        cafe_json.get('location', 'Others'),
        cafe_json.get('suburb', ''),
        cafe_json.get('spectrum', 3),
        cafe_json.get('price', 3),
        "|".join(cafe_json.get('atmosphere', [])),
        cafe_json.get('desc', ''),
        cafe_json.get('oneLiner', ''),
        "|".join(cafe_json.get('tags', [])),
        cafe_json.get('image', ''),
        cafe_json.get('rating', 0),
        cafe_json.get('reviews', 0)
    ]
    try:
        sheet.append_row(row)
        print(f"  [+] Saved '{cafe_json['name']}' to Google Sheets!")
    except Exception as e:
        print(f"  [!] Failed to save '{cafe_json['name']}': {e}")

if __name__ == "__main__":
    if not PLACES_API_KEY or not GEMINI_API_KEY:
        print("ERROR: Missing API Keys in .env file.")
        exit(1)
        
    print("=== Melbourne Coffee Bulk Automation Bot ===")
    
    # 1. Get existing DB
    existing_names, sheet = get_existing_cafe_names()
    if sheet is None:
        exit(1)
        
    # 2. Search for cafes generically
    query = "best specialty coffee in Melbourne CBD"
    candidates = search_cafes(query)
    
    # 3. Filter Duplicates & Process
    added_count = 0
    for cafe in candidates:
        if cafe['name'] in existing_names:
            print(f"  -> Skipping '{cafe['name']}' (Already in Google Sheet)")
            continue
            
        # 4. Analyze & Save new cafes (AI handles cross-language dupes and location)
        analyzed = analyze_cafe_with_ai(cafe, existing_names)
        if analyzed:
            append_to_sheet(sheet, analyzed)
            added_count += 1
            existing_names.append(analyzed['name']) # Add to local list to prevent dupes in same run
            
            # Optional: To prevent hitting API rate limits or spamming everything at once,
            # you can limit it to process only a few at a time during this test run.
            if added_count >= 3:
                print("\nReached limit of 3 bulk additions for this test run.")
                break
                
    print(f"\nDone! Added {added_count} new cafe(s) to the database.")
