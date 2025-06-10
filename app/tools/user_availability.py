"""Service tools for handling user availability."""
import requests
import logging
from app.config import BASE_API_URL
from app.tools.service_tools import get_auth_token

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_user_availability(user_id_of_person: str) -> dict:
    """
    Get availability information for a specific user.
    
    Args:
        user_id_of_person: ID of the user to check availability for
    
    Returns:
        Dict containing availability information
    """
    try:
        # Get token from global storage
        token = get_auth_token()
        if not token:
            logger.error("No auth token available for user availability check")
            return {}

        # Use the correct client ID from the cURL command
        client_id = "3dbb0be6-5d65-49b1-b2ed-034f1806582b"
        
        # Make API request
        response = requests.get(
            f"{BASE_API_URL}/user-availability/client/{client_id}/user/{user_id_of_person}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "accept": "*/*"
            }
        )
        
        # Log response for debugging
        logger.info(f"User availability response status: {response.status_code}")
        logger.info(f"User availability response: {response.text[:40]}")
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        logger.error(f"Error getting user availability: {str(e)}")
        raise 