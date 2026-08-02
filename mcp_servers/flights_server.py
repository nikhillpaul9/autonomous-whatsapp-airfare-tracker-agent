import os
import sys
import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# 1. Bulletproof .env loading using absolute paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
load_dotenv(os.path.join(project_root, ".env"))

mcp = FastMCP("GoogleFlightsServer")

@mcp.tool()
def search_flights(departure_id: str, arrival_id: str, date: str, stops: str = "Any") -> dict:
    """Searches Google Flights for the best and cheapest flights."""
    
    api_key = os.getenv("SERPAPI_KEY")
    
    print("\n" + "="*40, file=sys.stderr)
    print("🚀 MCP TOOL EXECUTING: search_flights", file=sys.stderr)
    print(f"📍 Route: {departure_id} -> {arrival_id} on {date} | Stops: {stops}", file=sys.stderr)
    print(f"🔑 API Key Found: {bool(api_key)} (Length: {len(api_key) if api_key else 0})", file=sys.stderr)
    
    if not api_key:
        error_msg = "FATAL ERROR: SERPAPI_KEY is missing."
        print(error_msg, file=sys.stderr)
        return {"error": error_msg}

    # Map the natural language stops to Google Flights parameter
    stops_mapping = {
        "direct": "1",
        "nonstop": "1",
        "1 stop": "2",
        "2 stops": "3"
    }
    stops_param = stops_mapping.get(stops.lower(), "0")

    params = {
        "engine": "google_flights",
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": date,
        "currency": "INR",
        "hl": "en",
        "type": "2",  # One-Way flight
        "api_key": api_key
    }
    
    # Only inject the stops parameter if a specific restriction was requested
    if stops_param != "0":
        params["stops"] = stops_param
    
    try:
        print("⏳ Sending HTTP request to SerpApi...", file=sys.stderr)
        
        response = requests.get("https://serpapi.com/search", params=params)
        response.raise_for_status()
        results = response.json()
        
        best_flights = results.get("best_flights", [])
        other_flights = results.get("other_flights", [])
        all_flights = best_flights + other_flights
        
        search_url = results.get("search_metadata", {}).get("google_flights_url", "https://www.google.com/flights")
        price_insights = results.get("price_insights", {})
        
        # Process historical price points as structured objects
        import datetime
        price_history_raw = price_insights.get("price_history", [])
        history_list = []
        if price_history_raw:
            # Grab up to 10 key data points across the 15-day window
            for ts, price in price_history_raw[-10:]:
                date_str = datetime.datetime.fromtimestamp(ts).strftime('%b %d')
                history_list.append({"date": date_str, "price": int(price)})
                
        price_insights['history_list'] = history_list
            
        print(f"✅ Success! Found {len(all_flights)} total direct flights.", file=sys.stderr)
        print("="*40 + "\n", file=sys.stderr)
        
        return {
            "search_url": search_url,
            "price_insights": price_insights,
            "flights": all_flights[:10]
        }
        
    except Exception as e:
        print(f"❌ SerpApi Error: {str(e)}", file=sys.stderr)
        print("="*40 + "\n", file=sys.stderr)
        return {"error": str(e)}

if __name__ == "__main__":
    mcp.run()