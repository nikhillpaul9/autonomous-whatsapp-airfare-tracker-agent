import sys
import asyncio

# Fix for Psycopg async on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
import json
import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

# Import your existing compiled graph builder
from app.graphs.flight_tracker import builder

# Centralized Database URI (Must match routes.py)
DB_URI = os.getenv("POSTGRES_URI", "postgresql://user:password@localhost:5432/flight_agent")

# Dynamically calculate the current year
today = datetime.date.today()
current_year = today.year

st.set_page_config(page_title="Flight Tracker AI", page_icon="✈️", layout="centered")

def apply_custom_ui():
    st.markdown("""
    <style>
    /* 1. Global Backgrounds */
    .stApp {
        background-color: #0B1120 !important;
    }
    
    /* 2. Fix the White Bottom Bars */
    [data-testid="stBottom"] {
        background-color: #0B1120 !important; 
    }
    [data-testid="stBottom"] > div {
        background-color: #0B1120 !important;
    }

    /* 3. FIX: Target the inner div of the chat input to remove the white background */
    [data-testid="stChatInput"] > div, 
    [data-testid="stChatInput"] > div > div {
        background-color: #1E293B !important;
        border-color: #3B82F6 !important;
    }
    
    /* Force typed text to be visible */
    [data-testid="stChatInput"] textarea {
        color: #FFFFFF !important; 
        -webkit-text-fill-color: #FFFFFF !important;
        background-color: transparent !important;
        font-size: 1rem !important;
    }
    [data-testid="stChatInput"] textarea::placeholder {
        color: #94A3B8 !important;
        -webkit-text-fill-color: #94A3B8 !important;
    }

    /* 4. Sidebar - Background Image & Readable Text */
    [data-testid="stSidebar"] {
        background: linear-gradient(rgba(11, 17, 32, 0.85), rgba(11, 17, 32, 0.95)), 
                    url('https://images.unsplash.com/photo-1542296332-2e4473faf563?q=80&w=800&auto=format&fit=crop') center/cover no-repeat !important;
        border-right: 1px solid #1E293B !important;
    }
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: #F8FAFC !important; 
    }
    
    /* 5. Chat Bubbles Fix (Clean & Symmetrical) */
    [data-testid="stChatMessage"] {
        background-color: transparent !important;
        border: none !important;
    }
    [data-testid="stChatAvatar"] {
        display: none !important; /* Hides default avatars */
    }
    /* User Message (Right, Blue) */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        flex-direction: row-reverse;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] {
        background: #2563EB !important;
        color: #FFFFFF !important;
        border-radius: 20px 20px 4px 20px !important;
        padding: 12px 18px !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stMarkdownContainer"] p {
        color: #FFFFFF !important;
    }
    /* Assistant Message (Left, Dark Slate) */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        flex-direction: row;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"] {
        background: #1E293B !important;
        color: #E2E8F0 !important;
        border: 1px solid #334155 !important;
        border-radius: 20px 20px 20px 4px !important;
        padding: 14px 20px !important;
    }
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"] p,
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"] li {
        color: #E2E8F0 !important;
    }

    /* 6. Premium App Header */
    .premium-header {
        background: linear-gradient(rgba(11, 17, 32, 0.6), rgba(11, 17, 32, 1)), 
                    url('https://images.unsplash.com/photo-1436491865332-7a61a109cc05?q=80&w=2074&auto=format&fit=crop') no-repeat center 30%;
        background-size: cover;
        padding: 40px 20px 30px 20px;
        border-radius: 0 0 24px 24px;
        margin: -3rem -4rem 1rem -4rem;
        border-bottom: 1px solid #3B82F6;
        text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
    }
    .premium-header h1 { margin: 0; font-size: 2.2rem; font-weight: 700; color: #F8FAFC; }
    .premium-header h1 span { color: #3B82F6; }
    .premium-header p { margin: 8px 0 0 0; font-size: 1rem; color: #94A3B8; }
    
    /* 7. Added UI Functionality: Quick Action Badges */
    .quick-actions {
        display: flex;
        justify-content: center;
        gap: 12px;
        margin-bottom: 30px;
        flex-wrap: wrap;
    }
    .action-badge {
        background: #1E293B;
        border: 1px solid #334155;
        padding: 8px 16px;
        border-radius: 20px;
        font-size: 0.85rem;
        color: #94A3B8;
        display: flex;
        align-items: center;
        gap: 6px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.2);
    }
    .action-badge span {
        color: #3B82F6; /* Blue icon color */
    }
    /* 8. FIX: Force all Assistant chat text, KPIs, and Headers to be bright white */
    
    /* Targets any text inside the assistant bubble, even if it lacks a <p> tag */
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"],
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) [data-testid="stMarkdownContainer"] * {
        color: #E2E8F0 !important;
    }

    /* Targets the Dashboard Headers (e.g., Market Analysis & Trends) */
    div[data-testid="stMarkdownContainer"] h3 {
        color: #F8FAFC !important;
    }

    /* Targets the KPI Metric Values (e.g., ₹10,209) */
    [data-testid="stMetricValue"] {
        color: #F8FAFC !important;
    }
    [data-testid="stMetricValue"] div {
        color: #F8FAFC !important;
    }

    /* Targets the KPI Metric Labels (e.g., Best Price Today) */
    [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
    }
    [data-testid="stMetricLabel"] div {
        color: #94A3B8 !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 1. NLP Extraction Schema ---
class FlightQueryExtraction(BaseModel):
    origin: str = Field(description="3-letter IATA code for the departure city (e.g., COK for Kochi, DEL for Delhi)")
    destination: str = Field(description="3-letter IATA code for the arrival city (e.g., COK for Kochi, DEL for Delhi)")
    date: str = Field(
        description=f"Flight date in YYYY-MM-DD format. "
                    f"CRITICAL: Today's date is {today.strftime('%Y-%m-%d')}. "
                    f"If the user specifies a date like '22nd of September' without a year, "
                    f"use the year {current_year} (or the next upcoming occurrence)."
    )
    time_of_day: str = Field(default="Any", description="Time of day requested, e.g., 'Morning', 'Afternoon', 'Evening', 'Night', or 'Any'")
    stops_preference: str = Field(default="Any", description="Preference for flight stops: 'Direct' (or nonstop), '1 Stop', '2 Stops', or 'Any'.")

# --- 2. Chart Rendering Helper ---
def render_dashboard(analysis):
    """Renders KPIs, an interactive 15-day price chart, and top flight cards."""
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### 📊 Market Analysis & Trends")
    
    # 1. KPIs
    best_price = analysis.best_options[0].price_inr if analysis.best_options else 0
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="🏆 Best Price Today", value=f"₹{best_price:,}")
    with col2:
        st.metric(label="📈 Price Level", value=analysis.price_trend.level.title())
    with col3:
        st.metric(label="⚖️ Typical Range", value=analysis.price_trend.typical_range)

    st.markdown("<br>", unsafe_allow_html=True)

    # 2. Fix the Chart: Dark Mode & Transparent Background
    if analysis.price_trend and analysis.price_trend.history_list:
        df = pd.DataFrame([{"Date": item.date, "Price": item.price} for item in analysis.price_trend.history_list])
        
        fig = px.line(df, x="Date", y="Price", markers=True)
        
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94A3B8"),
            margin=dict(l=0, r=0, t=30, b=0),
            xaxis=dict(showgrid=False, zeroline=False, color="#94A3B8", title=""),
            yaxis=dict(showgrid=True, gridcolor="#334155", zeroline=False, color="#94A3B8", title="Price (INR)")
        )
        
        fig.update_traces(
            line_color="#3B82F6", 
            line_width=3,
            marker=dict(size=10, color="#3B82F6", line=dict(width=2, color="#0B1120"))
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ✈️ Top Recommended Flights")
    
    # 3. Custom Visual Cards
    for flight in analysis.best_options[:3]:
        st.markdown(f"""
        <div style="background-color: #1E293B; border: 1px solid #334155; border-radius: 16px; padding: 18px; margin-bottom: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.2);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <h4 style="color: #F8FAFC; margin: 0; font-size: 1.1rem;">
                    {flight.airline} <span style="color: #3B82F6; font-size: 0.9em; font-weight: normal;">({flight.flight_number})</span>
                </h4>
                <div style="font-size: 1.3rem; font-weight: 700; color: #10B981;">₹{flight.price_inr:,}</div>
            </div>
            <div style="display: flex; justify-content: space-between; color: #94A3B8; font-size: 0.95rem;">
                <div>🕒 <b>{flight.departure_time}</b> ➔ <b>{flight.arrival_time}</b></div>
                <div>⏱️ {flight.duration} &nbsp;|&nbsp; 💺 {flight.airplane}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# --- Sidebar: Tracker Management ---
if "contacts" not in st.session_state:
    st.session_state.contacts = {"Nikhil": "+918130801411"}

with st.sidebar:
    tabs = st.tabs(["⚙️ Settings", "📡 Active Trackers"])

    with tabs[0]:
        st.header("⚙️ User Configuration")
        
        # Dropdown for existing contacts
        contact_names = list(st.session_state.contacts.keys())
        selected_contact = st.selectbox("Select WhatsApp Contact", options=contact_names)
        user_phone = st.session_state.contacts[selected_contact]
        
        st.caption(f"Active Number: {user_phone}")
        
        # Form to add new contacts
        with st.expander("➕ Add New Contact"):
            new_name = st.text_input("Name")
            new_phone = st.text_input("Phone Number (with + code)")
            if st.button("Add Contact"):
                if new_name and new_phone:
                    st.session_state.contacts[new_name] = new_phone
                    st.success(f"Added {new_name}!")
                    st.rerun()
                    
        st.divider()
        st.write("This agent extracts flight preferences, filters by time-of-day, retrieves 15-day historical pricing trends, and requests WhatsApp approval.")

    with tabs[1]:
        st.header("Manage Subscriptions")
        try:
            with open("subscriptions.json", "r") as f:
                subs = json.load(f)

            if not subs:
                st.write("No active trackers.")
            else:
                for idx, sub in enumerate(subs):
                    with st.expander(f"{sub['origin']} ➡️ {sub['destination']} ({sub['date']})"):
                        st.caption(f"Subscriber: {sub['phone']}")
                        if st.button("🗑️ Delete", key=f"del_{idx}"):
                            subs.pop(idx)
                            with open("subscriptions.json", "w") as f:
                                json.dump(subs, f, indent=4)
                            st.rerun()
        except (FileNotFoundError, json.JSONDecodeError):
            st.write("No active trackers.")

# 1. Call the completely bulletproof UI Enhancer
apply_custom_ui()

# 2. Render the premium header AND the new interactive functionalities bar
st.markdown("""
<div class="premium-header">
    <h1>✈️ AI <span>Flight</span> Agent</h1>
    <p>Intelligent price tracking • Instant WhatsApp alerts</p>
</div>

<!-- Added Functionality: Capabilities Bar -->
<div class="quick-actions">
    <div class="action-badge"><span>🎯</span> Daily Tracking</div>
    <div class="action-badge"><span>📄</span> PDF Itineraries</div>
    <div class="action-badge"><span>💰</span> Lowest Price Analysis</div>
    <div class="action-badge"><span>📱</span> WhatsApp Direct Booking</div>
</div>
""", unsafe_allow_html=True)

# --- 3. Chat State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Where would you like to fly, and when?"}
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# --- 4. Core Chatbot Logic ---
if prompt := st.chat_input("E.g., Give me details on flights from Kochi to Delhi on 22nd of September..."):
    
    if not user_phone:
        st.warning("⚠️ Please enter your WhatsApp number in the sidebar first.")
        st.stop()

    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing request and translating to IATA codes..."):
            try:
                llm = ChatOpenAI(model="gpt-4o", temperature=0)
                extractor = llm.with_structured_output(FlightQueryExtraction)
                extracted_params = extractor.invoke(prompt)
                
                st.info(f"📍 **Route:** {extracted_params.origin} ➡️ {extracted_params.destination} | **Date:** {extracted_params.date} | **Time:** {extracted_params.time_of_day} | **Stops:** {extracted_params.stops_preference}")
                
            except Exception as e:
                st.error("Could not parse the flight details from your message. Please try again.")
                st.stop()

        with st.spinner("Booting MCP server and querying live Google Flights data..."):
            try:
                if "daily" in prompt.lower():
                    sub_file = "subscriptions.json"
                    subs = []
                    if os.path.exists(sub_file):
                        with open(sub_file, "r") as f:
                            subs = json.load(f)
                    
                    subs.append({
                        "origin": extracted_params.origin,
                        "destination": extracted_params.destination,
                        "date": extracted_params.date,
                        "phone": user_phone
                    })
                    
                    with open(sub_file, "w") as f:
                        json.dump(subs, f, indent=4)
                        
                    response_msg = f"✅ Daily tracker set! You will receive WhatsApp price trend updates every morning for {extracted_params.origin} ➡️ {extracted_params.destination}."
                    st.success(response_msg)
                    st.session_state.messages.append({"role": "assistant", "content": response_msg})
                
                else:
                    # Run immediately for one-off requests
                    async def run_agent():
                        # 1. Connect using Async context manager for Postgres
                        async with AsyncConnectionPool(DB_URI, max_size=20, kwargs={"autocommit": True}) as pool:
                            # 1. Extract a physical connection from the pool
                            async with pool.connection() as conn:
                                
                                # 2. Pass the physical connection to the Saver and the async Store
                                checkpointer = AsyncPostgresSaver(conn)
                                store = AsyncPostgresStore(conn)
                                
                                await checkpointer.setup()
                                await store.setup()
                                
                                graph = builder.compile(checkpointer=checkpointer, store=store)
                            
                            # 2. Use deterministic thread ID matched exactly to routes.py
                            clean_phone = user_phone.replace("whatsapp:", "").strip()
                            thread_id = f"flight_tracker_{clean_phone}" 
                            config = {"configurable": {"thread_id": thread_id}}
                            
                            initial_state = {
                                "origin": extracted_params.origin,
                                "destination": extracted_params.destination,
                                "date": extracted_params.date,
                                "time_of_day": extracted_params.time_of_day,
                                "stops_preference": extracted_params.stops_preference,
                                "user_phone": clean_phone
                            }
                            
                            # 3. Stream the graph asynchronously
                            async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
                                pass 
                                
                            # 4. Fetch the final state to extract the analysis for the UI chart
                            state = await graph.aget_state(config)
                            return state.values.get("analysis")
                    
                    # Execute the async function and retrieve the final LLM analysis
                    final_analysis = asyncio.run(run_agent())
                    
                    response_msg = f"✅ Flight data successfully processed! I have sent the top options to your WhatsApp. Reply **BOOK** to proceed."
                    st.success(response_msg)
                    st.session_state.messages.append({"role": "assistant", "content": response_msg})
                    
                    # 5. Render the interactive dashboard in Streamlit
                    if final_analysis:
                        render_dashboard(final_analysis)
                
            except Exception as e:
                st.error(f"Graph Execution Error: {str(e)}")