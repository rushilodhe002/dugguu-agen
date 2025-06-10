"""Service tools for handling nearby services."""
import requests
from app.config import BASE_API_URL
from app.tools.service_tools import get_auth_token, set_auth_token

def get_nearby_services(
    latitude: float,
    longitude: float,
    page: int = 1,
    radius_km: int = 20,
    page_size: int = 2,
    user_name: str = None,
    tag_name: str = None
):
    """Get nearby services based on location and filters."""
    try:
        token = get_auth_token()
        if not token:
            print("No auth token available for nearby services")
            return []

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }

        # Build query parameters
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "page": page,
            "radiusKm": radius_km,
            "pageSize": page_size
        }
        
        if user_name:
            params["userName"] = user_name
        if tag_name:
            params["tagName"] = tag_name

        print(f"Making request to nearby services with params: {params}")
        print(f"Using token: {token[:20]}...")
        
        response = requests.get(
            f"{BASE_API_URL}/service-subcategory/service/nearby",
            headers=headers,
            params=params
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        if response.status_code == 200:
            return response.json()
        print(f"Error response from nearby services API: {response.status_code} - {response.text}")
        return []
    except Exception as e:
        print(f"Error fetching nearby services: {e}")
        return [] 