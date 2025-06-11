"""Configuration settings for the application."""

# API Keys and Endpoints
GEMINI_API_KEY = "your apu"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# Base URL for the API
BASE_API_URL = "https://m8p03gbszk.execute-api.ap-south-1.amazonaws.com/auth/api"

# Client ID for user availability
CLIENT_ID = "3dbb0be6-5d65-49b1-b2ed-034f1806582b"

# Gemini API Configuration
GEMINI_CONFIG = {
    "temperature": 0.9,
    "topP": 1,
    "maxOutputTokens": 2048
}

# Available Tools Configuration
TOOLS = {
    "function_declarations": [
        {
            "name": "get_all_services",
            "description": "Get the list of all available service categories and subcategories",
            "parameters": {
                "type": "object",
                "properties": {},
            }
        },
        {
            "name": "get_nearby_services",
            "description": "Find nearby service providers based on location and optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "description": "Latitude coordinate"},
                    "longitude": {"type": "number", "description": "Longitude coordinate"},
                    "page": {"type": "integer", "description": "Page number for pagination", "default": 1},
                    "radius_km": {"type": "number", "description": "Search radius in kilometers", "default": 20},
                    "page_size": {"type": "integer", "description": "Number of items per page", "default": 4},
                    "user_name": {"type": "string", "description": "Optional username to filter services"},
                    "tag_name": {"type": "string", "description": "Optional service tag to filter results"}
                },
                "required": ["latitude", "longitude"]
            }
        },
        {
            "name": "get_user_availability",
            "description": "Check the availability of a specific user/service provider.",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_id_of_person": {
                        "type": "string",
                        "description": "The ID of the person whose availability you want to check"
                    }
                },
                "required": ["user_id_of_person"]
            }
        },
        {
            "name": "create_task",
            "description": "Create a new task for a service provider.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Title of the task"
                    },
                    "task_type": {
                        "type": "string",
                        "description": "Type of task (e.g., Maintenance, Service)"
                    },
                    "task_details": {
                        "type": "string",
                        "description": "Detailed description of the task"
                    },
                    "assigned_to": {
                        "type": "string",
                        "description": "ID of the person to whom the task is assigned"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date and time of the task (ISO format)"
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date and time of the task (ISO format)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tags related to the task (include priority level in tags)"
                    },
                    "client_id": {
                        "type": "string",
                        "description": "Client ID from service provider"
                    },
                    "department_id": {
                        "type": "string",
                        "description": "Department ID from service provider"
                    },
                    "location_id": {
                        "type": "string",
                        "description": "Location ID from service provider"
                    },
                    "created_by": {
                        "type": "string",
                        "description": "ID of the user creating the task"
                    }
                },
                "required": ["title", "task_type", "task_details", "assigned_to", "start_date", "due_date", "tags", "client_id", "department_id", "location_id", "created_by"]
            }
        },
        {
            "name": "create_appointment",
            "description": "Create a new appointment with a service provider.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_user_id": {
                        "type": "string",
                        "description": "ID of the person to meet with"
                    },
                    "user_availability_id": {
                        "type": "string",
                        "description": "ID of the availability slot"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date of the appointment (YYYY-MM-DD)"
                    },
                    "time": {
                        "type": "string",
                        "description": "Time of the appointment (ISO format)"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Duration in minutes"
                    },
                    "appointment_agenda": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of topics to discuss"
                    },
                    "creator_name": {
                        "type": "string",
                        "description": "Name of the appointment creator"
                    },
                    "notes": {
                        "type": "string",
                        "description": "Additional notes about the appointment"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the appointment"
                    },
                    "loggedin_user_id": {
                        "type": "string",
                        "description": "ID of the logged-in user"
                    },
                    "is_virtual": {
                        "type": "boolean",
                        "description": "Whether the appointment is virtual",
                        "default": True
                    },
                    "location_name": {
                        "type": "string",
                        "description": "Location name",
                        "default": "remote"
                    },
                    "meeting_link": {
                        "type": "string",
                        "description": "Virtual meeting link (optional)"
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tags",
                        "default": ["healthcare-related"]
                    },
                    "client_id": {
                        "type": "string",
                        "description": "Client ID from service provider"
                    },
                    "department_id": {
                        "type": "string",
                        "description": "Department ID from service provider"
                    },
                    "location_id": {
                        "type": "string",
                        "description": "Location ID from service provider"
                    },
                    "created_by": {
                        "type": "string",
                        "description": "ID of the user creating the appointment"
                    }
                },
                "required": ["target_user_id", "user_availability_id", "date", "time", "duration", "appointment_agenda", "creator_name", "notes", "reason"]
            }
        }
    ]
} 
