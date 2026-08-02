import os
import json
from fastapi import APIRouter, Request, Response
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore
from langgraph.types import Command

from app.graphs.flight_tracker import builder

# Create local directory for static assets
os.makedirs("static_images", exist_ok=True)

# Centralized Database URI (reads from environment variable with fallback)
DB_URI = os.getenv("POSTGRES_URI", "postgresql://user:password@localhost:5432/flight_agent")
SUBSCRIPTION_FILE = "subscriptions.json"

router = APIRouter()


def remove_user_subscription(phone: str) -> bool:
    """Helper function to remove a phone number from subscriptions.json."""
    if not os.path.exists(SUBSCRIPTION_FILE):
        return False

    try:
        with open(SUBSCRIPTION_FILE, "r") as f:
            subs = json.load(f)

        clean_target = phone.replace("+", "").strip()
        updated_subs = [
            sub for sub in subs
            if sub.get("phone", "").replace("+", "").strip() != clean_target
        ]

        if len(subs) != len(updated_subs):
            with open(SUBSCRIPTION_FILE, "w") as f:
                json.dump(updated_subs, f, indent=4)
            return True
    except Exception as e:
        print(f"⚠️ Error updating subscriptions.json: {e}")

    return False


@router.post("/whatsapp")
async def twilio_webhook(request: Request):
    form_data = await request.form()

    from_number = form_data.get("From", "")
    body = form_data.get("Body", "").strip()

    # Strip whatsapp: prefix to use clean phone identifier
    phone_id = from_number.replace("whatsapp:", "").strip()
    thread_id = f"flight_tracker_{phone_id}"

    print(f"\n📩 Webhook Received from {phone_id}: '{body}'")

    # 1. Global Opt-Out / Unsubscribe Interceptor
    if body.upper() in ["STOP", "UNSUBSCRIBE", "CANCEL"]:
        was_removed = remove_user_subscription(phone_id)
        msg_text = (
            "✅ You have been successfully unsubscribed from all daily flight alerts."
            if was_removed
            else "ℹ️ No active daily flight alerts were found for your number."
        )
        twiml_response = f'<?xml version="1.0" encoding="UTF-8"?><Response><Message>{msg_text}</Message></Response>'
        return Response(content=twiml_response, media_type="application/xml")

    # 2. Resuming LangGraph Thread via Async Postgres Checkpointer & Store
    try:
        async with AsyncConnectionPool(DB_URI, max_size=20, kwargs={"autocommit": True}) as pool:
            # 1. Extract a physical connection from the pool
            async with pool.connection() as conn:
                
                # 2. Pass the physical connection to the Saver and the async Store
                checkpointer = AsyncPostgresSaver(conn)
                store = AsyncPostgresStore(conn)
                
                await checkpointer.setup()
                await store.setup()
                
                graph = builder.compile(checkpointer=checkpointer, store=store)
                config = {"configurable": {"thread_id": thread_id}}

                print(f"🚀 Resuming graph execution for thread {thread_id} via Postgres...")

                # Resume the paused thread with the user's WhatsApp message
                async for event in graph.astream(Command(resume=body), config=config, stream_mode="updates"):
                    pass

    except Exception as e:
        print(f"❌ Resumption Error: {e}")

    # Return empty TwiML so Twilio acknowledges receipt
    return Response(content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>', media_type="application/xml")