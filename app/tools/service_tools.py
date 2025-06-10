"""Service tools for handling service-related operations."""
import requests
from app.config import BASE_API_URL

# Global token storage
_auth_token = None

def set_auth_token(token: str):
    """Set the authentication token."""
    global _auth_token
    _auth_token = token
    print(f"Token set in service tools: {_auth_token[:20]}...")  # Print first 20 chars for debugging

def get_auth_token():
    """Get the current authentication token."""
    return _auth_token

def get_all_services():
    """Get all available services."""
    try:
        token = get_auth_token()
        if not token:
            print("No auth token available")
            return []
            
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accept": "application/json"
        }
            
        response = requests.get(f"{BASE_API_URL}/service-subcategory/subcategories-list", headers=headers)
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {response.headers}")
        
        if response.status_code == 200:
            return response.json()
        print(f"Error response from services API: {response.status_code} - {response.text}")
        return []
    except Exception as e:
        print(f"Error getting services: {e}")
        return [] 