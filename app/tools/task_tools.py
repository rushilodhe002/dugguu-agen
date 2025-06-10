"""Service tools for handling task-related operations."""
import requests
from datetime import datetime
from app.config import BASE_API_URL, CLIENT_ID
from app.tools.service_tools import get_auth_token
from typing import List, Dict, Any

def create_task(
    title: str,
    task_type: str,
    task_details: str,
    assigned_to: str,
    start_date: str,
    due_date: str,
    tags: List[str],
    client_id: str,
    department_id: str,
    location_id: str,
    created_by: str
) -> Dict[str, Any]:
    """
    Create a new task with predefined parameters.
    
    Args:
        title: Title of the task
        task_type: Type of task (Maintenance, Service, Emergency)
        task_details: Detailed description of the task
        assigned_to: ID of the user the task is assigned to
        start_date: Start date in ISO format
        due_date: Due date in ISO format
        tags: List of tags for the task
        client_id: Client ID from service provider
        department_id: Department ID from service provider
        location_id: Location ID from service provider
        created_by: ID of the user creating the task
    
    Returns:
        Dict containing task creation response
    """
    try:
        # Get token from global storage
        token = get_auth_token()
        if not token:
            raise ValueError("No authentication token available")

        # Determine priority based on task details and tags
        priority = "medium"  # default priority
        if any(tag.lower() in ["urgent", "emergency", "critical"] for tag in tags):
            priority = "critical"
        elif any(tag.lower() in ["high", "important"] for tag in tags):
            priority = "high"
        elif any(tag.lower() in ["low", "routine"] for tag in tags):
            priority = "low"

        # Prepare task data with predefined values
        task_data = {
            "title": title,
            "task_type": task_type,
            "task_details": task_details,
            "assigned_by": created_by,  # Use created_by as assigned_by
            "assigned_to": assigned_to,
            "start_date": start_date,
            "due_date": due_date,
            "status": "new",
            "priority": priority,
            "project": "General Maintenance",
            "milestone": "Regular Tasks",
            "parent_task": None,
            "tags": tags,
            "attachments": [],
            "observers": [],
            "custom_fields": {
                "reported_by": "system",
                "estimated_hours": 2,
                "safety_risk": "no"
            },
            "client_id": client_id,
            "department_id": department_id,
            "location_id": location_id,
            "created_by": created_by,
            "updated_by": created_by  # Use created_by as updated_by
        }

        # Make API request
        response = requests.post(
            f"{BASE_API_URL}/task/",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=task_data
        )
        
        # Log response for debugging
        print(f"Task creation response status: {response.status_code}")
        print(f"Task creation response: {response.text}")
        
        response.raise_for_status()
        return response.json()
        
    except Exception as e:
        print(f"Error creating task: {str(e)}")
        raise 