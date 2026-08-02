import os
import sys
import asyncio
import json
import uuid
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt, Command
from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.state import GraphState, FlightSummary
from app.services.twilio_client import send_whatsapp_message
from app.services.gemini_client import generate_destination_image
from app.services.pdf_generator import generate_itinerary_pdf

load_dotenv()

# Deterministic outputs for data extraction and reasoning
llm = ChatOpenAI(model="gpt-4o", temperature=0)

async def extract_flights_node(state: GraphState):
    print("\n" + "="*50)
    print("🔍 1. SPUN UP LANGGRAPH EXTRACTION NODE")
    
    server_script_path = os.path.abspath(os.path.join("mcp_servers", "flights_server.py"))
    
    if not os.path.exists(server_script_path):
        raise FileNotFoundError(f"❌ Cannot find MCP server at: {server_script_path}")
    
    # 1. Instantiate the MCP Client
    client = MultiServerMCPClient({
        "flights_server": {
            "command": sys.executable,
            "args": [server_script_path],
            "transport": "stdio",
            "env": dict(os.environ)
        }
    })
    
    tools = await client.get_tools()
    search_tool = next((t for t in tools if t.name == "search_flights"), None)
    
    if not search_tool:
        raise ValueError("❌ 'search_flights' tool was not found in the MCP server!")
        
    print(f"✈️ 2. CALLING SERPAPI: {state['origin']} -> {state['destination']} on {state['date']}")
    
    # 2. Invoke the tool with the new stops parameter
    tool_result = await search_tool.ainvoke({
        "departure_id": state["origin"],
        "arrival_id": state["destination"],
        "date": state["date"],
        "stops": state.get("stops_preference", "Any")
    })
    
    print("\n📦 3. RAW PAYLOAD FROM MCP SERVER:")
    print(tool_result)
    print("="*50 + "\n")
    
    # 3. ROBUST DEFENSIVE CHECK: Parse JSON text properly to verify 'flights' list
    raw_text = ""
    if isinstance(tool_result, list) and len(tool_result) > 0:
        first_item = tool_result[0]
        raw_text = first_item.get("text", "") if isinstance(first_item, dict) else getattr(first_item, "text", str(first_item))
    else:
        raw_text = str(tool_result)

    try:
        parsed_data = json.loads(raw_text)
        if "error" in parsed_data:
            raise RuntimeError(f"🚨 SerpApi Error: {parsed_data['error']}")
        
        flights = parsed_data.get("flights", [])
        if not flights:
            raise RuntimeError(f"🚨 SerpApi returned 0 flights for route {state['origin']} -> {state['destination']}.")
            
        print(f"✅ Verified {len(flights)} real flight options in payload!")
    except json.JSONDecodeError:
        if "error" in raw_text.lower():
            raise RuntimeError(f"🚨 FATAL: SerpApi error encountered: {raw_text}")

    # 4. Pass real live JSON payload to structured LLM for accurate parsing
    prompt = (
        f"Analyze these live flight search results from SerpApi for route "
        f"{state['origin']} to {state['destination']} on {state['date']}:\n\n"
        f"{tool_result}\n\n"
        f"Extract the top flights, exact prices in INR, flight numbers, and aircraft types accurately.\n"
        f"Extract the 'price_insights' (level, typical range, and history_list) to determine if this is a good deal.\n"
        f"CRITICAL LINK INSTRUCTION: Extract the 'search_url' at the top of the payload and assign it to 'master_search_url'. Do NOT invent links per flight.\n"
        f"🚨 TIME FILTER RULE: The user explicitly requested this time preference: '{state.get('time_of_day', 'Any')}'. ONLY extract flights departing in this specific time window. If no flights match, return an empty list.\n"
        f"🚨 STOPS RULE: The user prefers '{state.get('stops_preference', 'Any')}' flights. Ensure the extracted options respect this.\n"
        f"🚨 ANTI-HALLUCINATION RULE: ONLY extract flights that actually exist in the JSON payload."
    )
    
    structured_llm = llm.with_structured_output(FlightSummary)
    analysis = await structured_llm.ainvoke(prompt)
    
    return {
        "analysis": analysis, 
        "raw_flights_data": str(tool_result), 
        "status": "flights_extracted"
    }

async def generate_media_node(state: GraphState):
    destination = state['destination'].lower().strip()
    filename = f"{destination.replace(' ', '_')}.jpg"
    filepath = os.path.join("static_images", filename)
    
    # COST OPTIMIZATION: Reuse cached local image if it already exists to eliminate token/API costs
    if os.path.exists(filepath):
        print(f"Cache hit: Reusing existing image for {destination}. Saving API costs.")
    else:
        print(f"Cache miss: Generating new image for {destination} via Gemini.")
        image_bytes = generate_destination_image(state['destination'])
        os.makedirs("static_images", exist_ok=True)
        with open(filepath, "wb") as f:
            f.write(image_bytes)
            
    ngrok_domain = "https://copper-staleness-deniable.ngrok-free.dev" 
    public_url = f"{ngrok_domain}/static/{filename}"
    
    return {"media_url": public_url, "status": "media_generated"}

async def send_notification_node(state: GraphState):
    """Side Effect Node: Sends the Image + Detailed Text first, followed by the PDF summary."""
    analysis = state['analysis']
    origin = state['origin']
    destination = state['destination']
    date_str = state['date']
    
    print("📄 Generating PDF Itinerary...")
    # 1. Generate the PDF
    pdf_filename = generate_itinerary_pdf(
        state_data={"origin": origin, "destination": destination, "date": date_str},
        analysis_data=analysis
    )
    
    # 2. Gather Media URLs
    ngrok_base = os.getenv("NGROK_URL", "").rstrip("/")
    pdf_url = f"{ngrok_base}/static/{pdf_filename}" if ngrok_base else None
    
    # Look for the generated destination image in the state
    img_filename = state.get('destination_image') or state.get('image_file') or f"{destination.lower()}.jpg"
    img_url = f"{ngrok_base}/static/{img_filename}" if ngrok_base else None

    # Determine trend level and emoji
    level = analysis.price_trend.level.title()
    trend_emoji = "🟢" if "low" in level.lower() else "🔴" if "high" in level.lower() else "🟡"
    
    # Today's reference price (using the top flight option)
    today_price = analysis.best_options[0].price_inr if analysis.best_options else 0

    # 3. Build the WhatsApp text exactly matching the requested template
    msg = f"✈️ *Flights: {origin} ➡️ {destination} ({date_str})*\n"
    msg += f"{trend_emoji} *Price Level:* {level} (Typical: {analysis.price_trend.typical_range})\n\n"
    
    # Price History Section
    msg += f"📊 *Price History vs Today (₹{today_price:,}):*\n"
    if analysis.price_trend and analysis.price_trend.history_list:
        for item in analysis.price_trend.history_list:
            if item.price == today_price:
                emoji = "⚪"
                comp_text = "Same as today"
            elif item.price < today_price:
                emoji = "🟢"
                diff = today_price - item.price
                comp_text = f"-₹{diff:,} lower"
            else:
                emoji = "🔴"
                diff = item.price - today_price
                comp_text = f"+₹{diff:,} higher"
                
            msg += f"{emoji} *{item.date}:* ₹{item.price:,} ({comp_text})\n"
    msg += "\n"
    
    # Top Flight Options
    for idx, flight in enumerate(analysis.best_options[:3], 1):
        msg += f"*{idx}. {flight.airline}* (`{flight.flight_number}`)\n"
        msg += f"💰 *₹{flight.price_inr:,}* | 🕒 {flight.departure_time} - {flight.arrival_time}\n"
        msg += f"⏱️ {flight.duration} | 💺 {flight.airplane}\n\n"
        
    # AI Insight / Recommendation
    msg += f"💡 *Insight:* {analysis.overall_recommendation}\n\n"
    
    # Google Flights Link (With robust fallback generator)
    flight_link = state.get('google_flights_url')
    if not flight_link:
        # Fallback: Dynamically generate the exact Google Flights URL if the state is missing it
        flight_link = f"https://www.google.com/travel/flights?q=Flights%20to%20{destination}%20from%20{origin}%20on%20{date_str}"
        
    msg += f"🔗 *View all on Google Flights:*\n{flight_link}\n\n"
        
    msg += "📄 *(A 1-page PDF summary is attached in the next message)*\n\n"
    msg += "Reply *BOOK* to receive direct Indian OTA booking links, or *SNOOZE* to ignore."

    print("📲 Dispatching Image + Data block to WhatsApp...")
    
    # 4. Dispatch 1: Send the Heavy Text Block WITH the Destination Image
    send_whatsapp_message(
        to_phone=state['user_phone'], 
        body_text=msg,
        media_urls=[img_url] if img_url else None
    )
    
    # A safe, non-blocking 2-second pause to guarantee WhatsApp delivers the main message first
    await asyncio.sleep(2)

    print("📲 Dispatching standalone PDF to WhatsApp...")
    
    # 5. Dispatch 2: Send the PDF as a standalone document with minimal text
    if pdf_url:
        send_whatsapp_message(
            to_phone=state['user_phone'], 
            body_text=f"📄 *Attached: 1-Page Trip Summary for {destination}*",
            media_urls=[pdf_url]
        )
    
    return {"status": "notification_sent"}

async def wait_for_user_node(state: GraphState):
    """Interrupt Node: Strictly pauses the graph and waits for the webhook resume command."""
    human_response = interrupt({"question": "Waiting for WhatsApp reply", "phone": state['user_phone']})
    
    # Ensure response is handled cleanly as a string
    response_text = str(human_response).upper()
    
    if "BOOK" in response_text or "TICKET" in response_text:
        return Command(goto="SendOTALinks", update={"status": "approved_for_booking"})
    
    return Command(goto=END, update={"status": "snoozed"})


async def send_ota_links_node(state: GraphState):
    """Generates precise URL parameters for major OTAs and sends them via WhatsApp."""
    import datetime
    
    # Parse standard date (e.g., 2026-09-22) into OTA specific formats
    date_obj = datetime.datetime.strptime(state['date'], "%Y-%m-%d")
    d_slash = date_obj.strftime("%d/%m/%Y") # 22/09/2026
    
    # Skyscanner strictly uses YYMMDD format (e.g., 260922)
    d_skyscanner = date_obj.strftime("%y%m%d") 
    
    origin = state['origin'].upper()
    dest = state['destination'].upper()
    
    # Skyscanner URL paths require lowercase IATA codes
    origin_lower = origin.lower()
    dest_lower = dest.lower()
    
    stops_pref = state.get('stops_preference', 'Any').lower()
    
    # Map generic stops to OTA specific URL parameters
    mmt_filter = "&filterData=STOP_0" if "direct" in stops_pref or "nonstop" in stops_pref else ""
    ct_filter = "&stops=0" if "direct" in stops_pref or "nonstop" in stops_pref else ""
    ss_filter = "&preferdirects=true" if "direct" in stops_pref or "nonstop" in stops_pref else ""
    
    msg = f"✅ *Ready to Book!* Here are your pre-filled search pages for {origin} ➡️ {dest}:\n\n"
    
    # MakeMyTrip
    msg += f"🟡 *MakeMyTrip:*\nhttps://www.makemytrip.com/flight/search?itinerary={origin}-{dest}-{d_slash}&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E{mmt_filter}\n\n"
    
    # ClearTrip
    msg += f"🔴 *ClearTrip:*\nhttps://www.cleartrip.com/flights/results?adults=1&childs=0&infants=0&class=Economy&depart_date={d_slash}&from={origin}&to={dest}{ct_filter}\n\n"
    
    # Goibibo
    msg += f"🔵 *Goibibo:*\nhttps://www.goibibo.com/flight/search?itinerary={origin}-{dest}-{d_slash}&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E&lang=eng\n\n"
    
    # Skyscanner -> Replaces EaseMyTrip and Yatra
    msg += f"☁️ *Skyscanner:*\nhttps://www.skyscanner.co.in/transport/flights/{origin_lower}/{dest_lower}/{d_skyscanner}/?adultsv2=1&cabinclass=economy{ss_filter}\n\n"
    
    msg += "Tap any link above to securely complete your booking on your preferred platform!"
    
    send_whatsapp_message(state['user_phone'], msg, None)
    
    return {"status": "ota_links_sent"}

# --- Graph Builder Updates ---
builder = StateGraph(GraphState)
builder.add_node("ExtractFlights", extract_flights_node)
builder.add_node("GenerateMedia", generate_media_node)
builder.add_node("SendNotification", send_notification_node) # Replaced NotifyAndPause
builder.add_node("WaitForUser", wait_for_user_node)          # New Pause Node
builder.add_node("SendOTALinks", send_ota_links_node)

builder.add_edge(START, "ExtractFlights")
builder.add_edge("ExtractFlights", "GenerateMedia")
builder.add_edge("GenerateMedia", "SendNotification")
builder.add_edge("SendNotification", "WaitForUser")
# WaitForUser dynamically routes to SendOTALinks or END using Command()
builder.add_edge("SendOTALinks", END)