# ✈️ AI Flight Agent (Autonomous WhatsApp Tracker)

An autonomous AI agent that accepts natural language flight requests, scrapes 15-day historical pricing data, renders a premium interactive dashboard, and dispatches detailed multi-media itinerary summaries directly to WhatsApp.

Features Human-in-the-Loop (HITL) capabilities allowing users to reply **"BOOK"** on WhatsApp to seamlessly resume the paused agent and receive direct OTA ticketing links.

---

## 📸 Interface Preview

![AI Flight Agent Dashboard](assets/ui_screenshot.png)

*(The custom Streamlit UI featuring a deep-navy aviation theme, quick action capabilities, and conversational input).*

---

## ✨ Key Features

* 🧠 **Natural Language Processing:** Built with OpenAI (`gpt-4o`) to intelligently extract IATA codes, dates, time-of-day preferences, and stop preferences from conversational prompts.
* 📊 **Premium Dashboard UI:** A custom-styled Streamlit interface featuring a sleek deep-navy aviation theme, interactive Plotly transparent charts, KPI metrics, and dynamic flight cards.
* 📱 **Rich WhatsApp Integration:** Bypasses standard text limits by sending a visual Destination Image, followed by a dynamically generated 1-page PDF Itinerary summary.
* ⏸️ **Stateful Memory & HITL:** Uses **LangGraph** and an async **PostgreSQL** checkpointer to pause execution. When the user replies "BOOK" via WhatsApp, the FastAPI webhook intercepts the message, wakes up the exact graph thread, and resumes execution.
* 🕰️ **Automated Daily Tracking:** Subscriptions are saved and can be processed via a local Windows Task Scheduler pipeline to deliver daily morning price alerts.

---

## 🏗️ Architecture

1. **Frontend (`streamlit_app.py`):** Captures user input, manages WhatsApp contacts, saves daily subscriptions, and renders the live interactive analysis.
2. **AI Engine (`app/graphs/flight_tracker.py`):** A compiled LangGraph state machine that manages the extraction, scraping, analysis, PDF generation, and notification nodes.
3. **Database (PostgreSQL):** Stores the conversational state and execution checkpoints of the graph.
4. **Webhook (`app/api/routes.py`):** A FastAPI endpoint that listens for Twilio callbacks (user replies).
5. **Worker (`daily_worker.py`):** A scheduled script to iterate through active trackers and dispatch automated alerts.

---

## 🚀 Prerequisites

Before you begin, ensure you have the following accounts and tools configured:

* **Python 3.10+**
* **PostgreSQL:** Running locally or via a cloud provider.
* **OpenAI API Key:** For the GPT-4o LLM.
* **Twilio Account:** An active Sandbox or Production WhatsApp Business API number.
* **Ngrok:** To expose your local FastAPI webhook and serve static media files to Twilio.

---

## 🛠️ Installation & Setup

**1. Clone the repository**

```bash
git clone https://github.com/nikhillpaul9/autonomous-whatsapp-airfare-tracker-agent.git
cd ai-flight-agent

```

**2. Create a virtual environment & install dependencies**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

```

**3. Configure Environment Variables**
Create a `.env` file in the root directory and add the following keys:

```env
# LLM
OPENAI_API_KEY=sk-your-openai-api-key

# Database (For LangGraph Checkpointing)
POSTGRES_URI=postgresql://user:password@localhost:5432/flight_agent

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_NUMBER=+14155238886

# Ngrok Public URL (Required for Webhooks & PDF/Image rendering on WhatsApp)
NGROK_URL=https://your-ngrok-url.ngrok-free.app

```

---

## 💻 Running the Application locally

To run the full suite locally, you will need to open **three separate terminal windows**.

### Terminal 1: Expose Localhost via Ngrok

Twilio needs a public URL to send webhook replies to, and to download the PDF/Images you generate.

```bash
ngrok http 8000

```

*(Copy the generated Forwarding URL and update your `.env` file and Twilio Sandbox settings).*

### Terminal 2: Start the FastAPI Webhook Server

This listens for the "BOOK" replies from WhatsApp to resume the graph.

```bash
uvicorn app.api.routes:app --host 0.0.0.0 --port 8000

```

### Terminal 3: Launch the Streamlit Dashboard

```bash
streamlit run streamlit_app.py

```

---

## 🗂️ Project Structure

```text
ai-flight-agent/
│
├── app/
│   ├── api/
│   │   └── routes.py             # FastAPI webhook for Twilio callbacks
│   ├── graphs/
│   │   └── flight_tracker.py     # LangGraph nodes, edges, and state compilation
│   ├── services/
│   │   ├── pdf_generator.py      # Dynamic PDF itinerary builder
│   │   └── twilio_client.py      # WhatsApp API dispatcher (Media & Text)
│   └── static/                   # Temporarily stores generated PDFs and Images
│
├── assets/
│   └── ui_screenshot.png         # Repository images (e.g., UI Preview)
│
├── streamlit_app.py              # Main UI, Custom CSS, and Agent Invocation
├── daily_worker.py               # Background script for automated daily alerts
├── subscriptions.json            # Local storage for active daily trackers
├── requirements.txt              
├── .env                          
└── README.md                     

```

---

## 💬 Usage Guide

1. **Set your Contact:** Open the Streamlit sidebar and add your WhatsApp number (format: `+1234567890`). Ensure you have joined the Twilio Sandbox from this number.
2. **Search a Flight:** In the chat input, type a natural prompt like: *"Track flights from Kochi to Delhi for the 22nd of September."*
3. **View Dashboard:** The UI will instantly display a 15-day price trend chart, top flight cards, and KPIs.
4. **Check WhatsApp:** You will receive a visually rich message containing the destination image, pricing data, and a standalone 1-page PDF itinerary summary.
5. **Human-in-the-Loop:** Reply **BOOK** on WhatsApp. The FastAPI webhook will wake up the exact LangGraph thread in PostgreSQL and dispatch the direct OTA booking links (e.g., MakeMyTrip/Skyscanner) back to your phone.
6. **Daily Subscriptions:** Include the word *"daily"* or *"track"* in your prompt to save the route. Use Windows Task Scheduler to run `daily_worker.py` every morning for automated alerts.

---

## ⚠️ Important Notes

* **WhatsApp Media Limitations:** The Meta API only allows one media attachment per message block. The system handles this gracefully by dispatching the Image + Text first, waiting `2` seconds, and then dispatching the PDF separately.
* **Ngrok Expiration:** If using a free Ngrok tier, your public URL will change every time you restart Ngrok. Remember to update your `.env` and Twilio Webhook URL accordingly.