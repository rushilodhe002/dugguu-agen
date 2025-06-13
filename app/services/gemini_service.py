"""Service for interacting with the Gemini API."""
from typing import Dict, List, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from app.config import GEMINI_API_KEY, GEMINI_API_URL, GEMINI_CONFIG, TOOLS

class GeminiService:
    @staticmethod
    def call_api(prompt: str, tools: Dict = None, conversation_history: List[Dict] = None) -> Optional[Dict]:
        """Make a direct HTTP request to the Gemini API with retry logic."""
        headers = {"Content-Type": "application/json"}
        
        contents = [{"role": "user", "parts": [{"text": prompt}]}]
        if conversation_history:
            contents = conversation_history + contents
        
        payload = {
            "contents": contents,
            "generationConfig": GEMINI_CONFIG
        }
        
        if tools:
            payload["tools"] = tools
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,  # number of retries
            backoff_factor=1,  # wait 1, 2, 4 seconds between retries
            status_forcelist=[500, 502, 503, 504]  # HTTP status codes to retry on
        )
        
        # Create a session with the retry strategy
        session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        try:
            response = session.post(
                GEMINI_API_URL,
                headers=headers,
                params={"key": GEMINI_API_KEY},
                json=payload,
                timeout=10  # Add timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error calling Gemini API: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def process_response(response: Dict) -> str:
        """Process the Gemini API response and extract the text."""
        if not response:
            return "I'm having trouble processing your request right now."

        try:
            candidate = response.get("candidates", [{}])[0]
            content = candidate.get("content", {})
            part = content.get("parts", [{}])[0]
            
            if "text" in part:
                return part["text"]
            elif "functionCall" in part:
                return "Processing your request..."
            else:
                return "I didn't understand that. Could you please rephrase?"
        except (KeyError, IndexError):
            return "I couldn't process the response properly. Please try again." 