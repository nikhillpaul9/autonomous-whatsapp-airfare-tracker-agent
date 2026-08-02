import os
from fpdf import FPDF
from datetime import datetime

def generate_itinerary_pdf(state_data, analysis_data) -> str:
    """Generates a PDF itinerary and returns the local filename."""
    os.makedirs("static_images", exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"itinerary_{state_data['origin']}_{state_data['destination']}_{timestamp}.pdf"
    filepath = os.path.join("static_images", filename)
    
    pdf = FPDF()
    pdf.add_page()
    
    # Header
    pdf.set_font("helvetica", "B", 18)
    pdf.set_text_color(31, 119, 180) # Plotly Blue
    pdf.cell(0, 10, f"Flight Itinerary & Summary", ln=True, align="C")
    pdf.ln(5)
    
    # Route Details
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, f"Route: {state_data['origin']} to {state_data['destination']}", ln=True)
    
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 8, f"Date: {state_data['date']}", ln=True)
    pdf.cell(0, 8, f"Price Trend: {analysis_data.price_trend.level.title()} (Typical: {analysis_data.price_trend.typical_range})", ln=True)
    pdf.ln(5)
    
    # Flights Options
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(31, 119, 180)
    pdf.cell(0, 10, "Top Recommended Flights", ln=True)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_font("helvetica", "", 11)
    for idx, flight in enumerate(analysis_data.best_options[:3], 1):
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 8, f"{idx}. {flight.airline} (Flight {flight.flight_number}) - INR {flight.price_inr:,}", ln=True)
        pdf.set_font("helvetica", "", 11)
        pdf.cell(0, 6, f"    Departs: {flight.departure_time} | Arrives: {flight.arrival_time}", ln=True)
        pdf.cell(0, 6, f"    Duration: {flight.duration} | Aircraft: {flight.airplane}", ln=True)
        pdf.ln(3)
        
    # Recommendation
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 8, "Agent Recommendation:", ln=True)
    pdf.set_font("helvetica", "I", 11)
    pdf.multi_cell(0, 6, analysis_data.overall_recommendation)
    
    pdf.output(filepath)
    return filename