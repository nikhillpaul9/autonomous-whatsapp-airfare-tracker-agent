from typing import TypedDict, Annotated, Optional
import operator
from pydantic import BaseModel, Field

class FlightDetail(BaseModel):
    airline: str = Field(description="Name of the airline")
    flight_number: str = Field(description="Flight code/number, e.g., AI 502")
    airplane: str = Field(description="Aircraft model")
    price_inr: int = Field(description="Price of the flight in INR")
    departure_time: str = Field(description="Departure time")
    arrival_time: str = Field(description="Arrival time")
    duration: str = Field(description="Total duration of the flight")
    stops: str = Field(description="Must indicate Direct or Nonstop")

class PriceHistoryPoint(BaseModel):
    date: str = Field(description="Formatted date, e.g., 'Aug 12'")
    price: int = Field(description="Historical price in INR")

class PriceTrend(BaseModel):
    level: str = Field(default="Unknown", description="Extract price_level: 'Low', 'Typical', or 'High'")
    typical_range: str = Field(default="N/A", description="Extract typical_price_range")
    history_list: list[PriceHistoryPoint] = Field(default=[], description="Structured historical price entries")

class FlightSummary(BaseModel):
    master_search_url: str = Field(description="The precise search_url provided at the top of the SerpApi payload") # NEW
    best_options: list[FlightDetail] = Field(description="Top direct flight options")
    price_trend: PriceTrend = Field(description="Price insights and historical trend points")
    overall_recommendation: str = Field(description="Summary recommending the best choice")

class GraphState(TypedDict):
    user_phone: str
    origin: str
    destination: str
    date: str
    time_of_day: str
    stops_preference: str
    raw_flights_data: Optional[str]
    analysis: Optional[FlightSummary]
    media_url: Optional[str]
    status: str
    messages: Annotated[list, operator.add]