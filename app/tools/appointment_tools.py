"""Appointment tools for handling appointment-related operations."""
import requests
from datetime import datetime, timedelta
from app.config import BASE_API_URL
from app.tools.service_tools import get_auth_token
from typing import List, Dict, Any, Optional

def create_appointment(
    target_user_id: str,
    user_availability_id: str,
    date: str,
    time: str,
    duration: int,
    appointment_agenda: List[str],
    creator_name: str,
    notes: str,
    reason: str,
    loggedin_user_id: str,
    is_virtual: bool = True,
    location_name: str = "remote",
    meeting_link: Optional[str] = None,
    tags: List[str] = ["healthcare-related"],
    client_id: Optional[str] = None,
    department_id: Optional[str] = None,
    location_id: Optional[str] = None,
    created_by: Optional[str] = None
) -> Dict:
    """Create a new appointment."""
    try:
        # Convert time to correct format (HH:MM:SS)
        if 'T' in time:  # If it's an ISO timestamp
            time = time.split('T')[1].split('Z')[0]  # Extract just the time part
        elif ':' in time and len(time.split(':')) == 2:
            time = f"{time}:00"  # Add seconds if missing
        
        # Prepare the request payload
        payload = {
            "target_user_id": target_user_id,
            "user_availability_id": user_availability_id,
            "date": date,
            "time": time,
            "duration": duration,
            "appointment_agenda": appointment_agenda,
            "creator_name": creator_name,
            "notes": notes,
            "reason": reason,
            "loggedin_user_id": loggedin_user_id,
            "is_virtual": is_virtual,
            "location_name": location_name,
            "meeting_link": meeting_link,
            "tags": tags,
            "client_id": client_id,
            "department_id": department_id,
            "location_id": location_id,
            "created_by": created_by
        }

        # Remove None values from payload
        payload = {k: v for k, v in payload.items() if v is not None}

        # Get auth token
        token = get_auth_token()
        if not token:
            raise ValueError("No authentication token available")

        # Make the API request with proper headers
        response = requests.post(
            f"{BASE_API_URL}/appointment/",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
        )

        # Log the response for debugging
        print(f"Appointment creation response status: {response.status_code}")
        print(f"Appointment creation response: {response.text}")

        # Check if the request was successful
        response.raise_for_status()
        
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error creating appointment: {e}")
        raise 