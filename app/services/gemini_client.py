from google import genai
from app.core.config import settings

def generate_destination_image(destination: str) -> bytes:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    
    # We append the aspect ratio directly to the prompt for the Gemini 3.1 Flash Image model
    prompt = f"A beautiful, cinematic, wide-angle postcard-style photograph of {destination}, highlighting its iconic landscape or culture. 16:9 aspect ratio."
    
    # The Nano Banana 2 model uses the standard generate_content endpoint
    response = client.models.generate_content(
        model="gemini-3.1-flash-image", 
        contents=[prompt]
    )
    
    # Extract the image bytes from the response parts
    for part in response.parts:
        if part.inline_data is not None:
            return part.inline_data.data
            
    raise ValueError("No image data returned from Gemini API")