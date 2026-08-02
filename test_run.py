import asyncio
import os
from dotenv import load_dotenv
from langgraph.store.postgres import PostgresStore
from langgraph.checkpoint.memory import MemorySaver

from app.graphs.flight_tracker import builder

load_dotenv()

async def trigger_daily_scan():
    # Initialize the persistence layer
    store = PostgresStore(os.getenv("POSTGRES_URI"))
    checkpointer = MemorySaver()
    
    # Compile the graph
    graph = builder.compile(store=store, checkpointer=checkpointer)
    
    # Simulate a user's subscription memory
    user_phone = "+918130801411" # Replace with your WhatsApp registered number
    thread_config = {"configurable": {"thread_id": f"flight_tracker_{user_phone}"}}
    
    initial_state = {
        "user_phone": user_phone,
        "origin": "DEL",
        "destination": "COK", 
        "date": "2026-09-12",
        "status": "starting",
        "messages": []
    }
    
    print("🚀 Firing off the flight agent...")
    
    # Use graph.astream() with stream_mode="updates"
    async for step in graph.astream(initial_state, config=thread_config, stream_mode="updates"):
        for node, state_update in step.items():
            print(f"✅ Finished node execution: {node}")
            
    # After the loop exits, we check the graph's current state to see if it paused
    state = await graph.aget_state(thread_config)
    
    # If state.next is populated, the graph hit our interrupt() and is waiting for human input
    if state.next:
        print("\n⏸️ Graph paused. Check your WhatsApp for the message!")
        print("Reply to the Twilio message to resume the graph via the webhook.")
    else:
        print("\n🏁 Graph execution finished completely.")

if __name__ == "__main__":
    asyncio.run(trigger_daily_scan())