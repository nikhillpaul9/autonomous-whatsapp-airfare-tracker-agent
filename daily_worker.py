import sys
import asyncio

# Fix for Psycopg async on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import json
import os
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from app.graphs.flight_tracker import builder

# Centralized Database URI (Must match routes.py and streamlit_app.py)
DB_URI = os.getenv("POSTGRES_URI", "postgresql://user:password@localhost:5432/flight_agent")
SUBSCRIPTION_FILE = "subscriptions.json"


def clean_expired_subscriptions():
    """Removes tracked flights whose dates have passed from the JSON store."""
    if not os.path.exists(SUBSCRIPTION_FILE):
        return []
        
    try:
        with open(SUBSCRIPTION_FILE, "r") as f:
            subs = json.load(f)

        valid_subs = []
        today = datetime.date.today()

        for sub in subs:
            # Convert the flight date string to a Date object
            flight_date = datetime.datetime.strptime(sub['date'], "%Y-%m-%d").date()

            # Only keep flights occurring in the future
            if flight_date >= today:
                valid_subs.append(sub)
            else:
                print(f"🗑️ Auto-expired old flight: {sub['origin']} -> {sub['destination']}")

        with open(SUBSCRIPTION_FILE, "w") as f:
            json.dump(valid_subs, f, indent=4)

        return valid_subs
    except Exception as e:
        print(f"⚠️ Error cleaning subscriptions: {e}")
        return []


async def run_daily_scans():
    """Executes the daily flight search for all active subscriptions using LangGraph."""
    # 1. Clean expired flights before running
    subs = clean_expired_subscriptions()
    
    if not subs:
        print("ℹ️ No active flight subscriptions found.")
        return
        
    print(f"🚀 Executing daily scan for {len(subs)} tracked routes...")
    
    # 2. Connect to the shared Postgres architecture
    async with AsyncConnectionPool(DB_URI, max_size=20, kwargs={"autocommit": True}) as pool:
            # 1. Extract a physical connection from the pool
        async with pool.connection() as conn:
            
            # 2. Pass the physical connection to the Saver and the async Store
            checkpointer = AsyncPostgresSaver(conn)
            store = AsyncPostgresStore(conn)
            
            await checkpointer.setup()
            await store.setup()
            
            graph = builder.compile(checkpointer=checkpointer, store=store)
        
        for sub in subs:
            # 3. Use deterministic thread ID to allow Webhook resumption via WhatsApp replies
            clean_phone = sub["phone"].replace("whatsapp:", "").strip()
            thread_id = f"flight_tracker_{clean_phone}"
            
            config = {"configurable": {"thread_id": thread_id}}
            
            initial_state = {
                "origin": sub["origin"],
                "destination": sub["destination"],
                "date": sub["date"],
                # Keep stops and time generic for daily sweeps unless specifically requested
                "time_of_day": "Any",
                "stops_preference": "Any",
                "user_phone": clean_phone
            }
            
            try:
                # 4. Stream the graph to fetch SerpApi data and push to WhatsApp
                async for event in graph.astream(initial_state, config=config, stream_mode="updates"):
                    pass
                print(f"✅ Notification dispatched to {clean_phone} for {sub['origin']} ➡️ {sub['destination']}")
            except Exception as e:
                print(f"❌ Error processing route for {clean_phone}: {e}")


if __name__ == "__main__":
    scheduler = AsyncIOScheduler()
    
    # Schedules the job to run every day at 11:00 AM
    scheduler.add_job(run_daily_scans, 'cron', hour=21, minute=0)
    scheduler.start()
    
    print("🕰️ Autonomous Flight Worker Started. Waiting for scheduled triggers...")
    
    try:
        # Keep the event loop alive to listen for scheduled cron jobs
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Shutting down Autonomous Flight Worker.")