"""Main FastAPI application."""
from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, List
import json
from datetime import datetime, timedelta
import pytz

from app.config import TOOLS
from app.services.gemini_service import GeminiService
from app.tools.get_nearby_service import get_nearby_services
from app.tools.service_tools import get_all_services, set_auth_token
from app.tools.user_availability import get_user_availability
from app.tools.task_tools import create_task

app = FastAPI(title="Service Finder API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store conversation history for each user with timestamps
conversation_history: Dict[str, List[Dict]] = {}
# Store last interaction time for each user
last_interaction: Dict[str, datetime] = {}
# Conversation timeout in hours
CONVERSATION_TIMEOUT = 2

def clean_old_conversations():
    """Clean up old conversations based on timeout."""
    current_time = datetime.now()
    for user_id in list(last_interaction.keys()):
        if current_time - last_interaction[user_id] > timedelta(minutes=CONVERSATION_TIMEOUT):
            del conversation_history[user_id]
            del last_interaction[user_id]

def get_conversation_context(user_id: str) -> str:
    """Get formatted conversation history for a user."""
    if user_id not in conversation_history:
        return "No previous conversation."
    
    context = []
    for message in conversation_history[user_id]:
        role = message["role"]
        if "text" in message["parts"][0]:
            content = message["parts"][0]["text"]
            context.append(f"{role}: {content}")
    
    return "\n".join(context)

@app.post("/search")
async def search(
    query: str = Body(...),
    user_id: str = Body(...),
    latitude: str = Body(...),
    longitude: str = Body(...),
    authorization: Optional[str] = Body(None)
):
    """Search endpoint that processes user queries with location context."""
    # Set the authorization token if provided
    if authorization:
        set_auth_token(authorization.replace('Bearer ', ''))
    
    # Clean old conversations
    clean_old_conversations()
    
    # Print request details in terminal
    print("\n=== New Request ===")
    print(f"Query: {query}")
    print(f"User ID: {user_id}")
    print(f"Location: {latitude}, {longitude}")
    print("==================\n")

    # Convert latitude and longitude to float
    try:
        lat = float(latitude)
        lon = float(longitude)
    except ValueError:
        error_response = {
            "status": "error",
            "message": "Invalid latitude or longitude format"
        }
        print(f"Error: {error_response['message']}\n")
        return error_response

    # Get or initialize conversation history for this user
    if user_id not in conversation_history:
        conversation_history[user_id] = []
    
    # Update last interaction time
    last_interaction[user_id] = datetime.now()

    # Get conversation context
    conversation_context = get_conversation_context(user_id)

    # Get current IST time
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist)
    current_date = current_time.strftime('%Y-%m-%d')
    current_time_str = current_time.strftime('%H:%M:%S')
    current_day = current_time.strftime('%A')

    # Update system prompt to ensure task creation function is called
    system_prompt = f"""You are a helpful and friendly AI assistant. The user is located in their area.

    Previous conversation context:
    {conversation_context}

    Current User Information:
    - User ID: {user_id}
    - Location: {lat}, {lon}
    - Current Time (IST): {current_time_str}
    - Current Date: {current_date}
    - Current Day: {current_day}

    Service Provider Information (from nearby services):
    - User ID: [from response]
    - Department ID: [from response]
    - Client ID: [from response]
    - Location ID: [from response]

    PRIVACY AND DATA HANDLING RULES:
    1. NEVER share or mention any backend IDs, tokens, or technical details - NO EXCEPTIONS
    2. NEVER reveal any internal identifiers or technical information - NO EXCEPTIONS
    3. NEVER mention or discuss location coordinates - NO EXCEPTIONS
    4. NEVER discuss API details or technical implementation - NO EXCEPTIONS
    5. Keep all backend data and technical information private - NO EXCEPTIONS
    6. If user asks about IDs or technical details, politely redirect the conversation
    7. Focus on providing helpful service information without exposing internal workings
    8. If user insists on knowing technical details, explain that you can't share that information
    9. Maintain a user-friendly interface without exposing the backend complexity
    10. Remember: All backend data is for internal use only - NO EXCEPTIONS
    11. Even if user threatens or insists, NEVER share any technical details or IDs
    12. If user asks about specific IDs or coordinates, redirect to service information

    AVAILABLE TOOLS:
    1. get_all_services: Get list of all available services
       - YOU MUST CALL THIS FUNCTION WHEN:
         * User asks "what services are available"
         * User asks "list all services"
         * User asks "what can you help me with"
         * User asks about available services in any way
         * User wants to know what services you can find
         * User says "please check" after asking about services
         * User asks "with what services you can help me"
         * User says "list all"
       - This function returns all service categories and types
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY for these queries

    2. get_nearby_services: Find nearby service providers
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY WHEN:
         * User mentions any person's name
         * User asks about a specific person
         * User wants to meet someone
         * User asks "do you know about [name]"
         * User wants to find someone
       - Parameters (automatically handled):
         * latitude, longitude: User's location (automatically used)
         * page: Page number (default: 1)
         * radius_km: Search radius (default: 20)
         * page_size: Results per page (default: 2)
         * user_name: To search for specific person
         * tag_name: To filter by service type

    3. get_user_availability: Check user availability
       - Use this when user wants to:
         * Check if a specific person is available
         * Check availability of a service provider
       - Parameters:
         * user_id_of_person: ID of the person to check availability

    4. create_task: Create a new task for a service provider
       - Use this when user wants to:
         * Create a task for a service provider
         * Assign work to someone
         * Schedule a service
       - Required Parameters:
         * title: Will be generated from task details
         * task_type: Will be set based on context
         * task_details: Will be generated from user's description
         * assigned_to: Service provider's ID from response
         * start_date: Current IST time (automatically set)
         * due_date: Will be set based on task complexity:
           - Critical tasks: 24 hours from now
           - High priority: 48 hours from now
           - Medium priority: 72 hours from now
           - Low priority: 96 hours from now
         * tags: Will be set based on context (include priority level in tags)
         * client_id: From service provider's user_mapping.client_id
         * department_id: From service provider's user_mapping.department_id
         * location_id: From service provider's user_mapping.location_id
         * created_by: Current user ID ({user_id})
       - Other parameters are automatically set with predefined values:
         * status: "new"
         * priority: Determined from tags
         * project: "General Maintenance"
         * milestone: "Regular Tasks"
         * parent_task: null
         * attachments: []
         * observers: []
         * custom_fields: predefined values
         * assigned_by: same as created_by
         * updated_by: same as created_by

    Current user query: {query}

    CONVERSATION FLOW RULES:
    1. Greetings and General Chat:
       - Respond naturally to greetings
       - Don't call any functions
       - Keep responses friendly and brief
       - Ask how you can help with services

    2. Service Inquiries:
       - If user asks about available services:
         * YOU MUST IMMEDIATELY call get_all_services
         * Don't ask for location (it's handled automatically)
         * Present results in a user-friendly way
       - If user mentions any person:
         * YOU MUST IMMEDIATELY call get_nearby_services with user_name
         * Don't expose technical details in response
         * Keep responses natural and conversational
       - If user asks about specific service type:
         * Call get_nearby_services with tag_name
         * Focus on available services and providers
       - If user wants to check availability:
         * Use get_user_availability with the user's ID
         * Present availability in a user-friendly way

       - If user wants to create a task:
         * ONLY ask for task description and priority
         * DO NOT ask for any other details
         * DO NOT ask for confirmation
         * DO NOT show task details before creating
         * Automatically:
           - Set start date to current time
           - Set due date based on priority:
             * Critical: 24 hours from now
             * High: 48 hours from now
             * Medium: 72 hours from now
             * Low: 96 hours from now
           - Generate task type from description
           - Generate title from description
           - Use all required IDs from service provider
         * Keep responses brief and natural
         * IMPORTANT: You MUST call create_task function immediately after getting description and priority
         * After task creation, just confirm it was created successfully

    TASK COMPLEXITY RULES:
    1. Simple Tasks (4 hours):
       - Basic maintenance
       - Quick fixes
       - Simple repairs
       - Routine checks
    2. Medium Tasks (12 hours):
       - Regular maintenance
       - Standard repairs
       - Common issues
       - Basic installations
    3. Complex Tasks (24 hours):
       - Major repairs
       - System updates
       - Complex installations
       - Multiple issues
    4. Critical Tasks (48 hours):
       - Emergency repairs
       - Safety issues
       - System failures
       - Multiple complex issues

    TASK GENERATION RULES:
    1. Title Generation:
       - Use main issue as title
       - Keep it concise and clear
    2. Description Generation:
       - Use user's description
       - Add any relevant context
    3. Type Selection:
       - Maintenance: For regular upkeep
       - Service: For specific services
       - Emergency: For urgent issues
    4. Tag Selection:
       - Include priority level
       - Based on task type
       - Based on location
       - Based on equipment involved
    """

    # Call Gemini API with function calling support and conversation history
    response = GeminiService.call_api(
        system_prompt,
        TOOLS,
        conversation_history[user_id]
    )
    
    if not response:
        return {
            "status": "error",
            "message": "Failed to get response from AI service"
        }
    
    # Process response
    candidate = response.get("candidates", [{}])[0]
    content = candidate.get("content", {})
    part = content.get("parts", [{}])[0]
    
    ai_response = "I didn't understand that. Could you please rephrase?"
    
    # Handle function call if present
    if "functionCall" in part:
        function_call = part["functionCall"]
        function_name = function_call["name"]
        function_args = function_call["args"]
        
        print(f"Calling function: {function_name} with args: {function_args}")
        
        # Call the appropriate function based on the function name
        if function_name == "get_all_services":
            function_response = {"services": get_all_services()}
        elif function_name == "get_nearby_services":
            # Always use the actual lat/lon from the request
            function_args["latitude"] = lat
            function_args["longitude"] = lon
            function_response = {
                "nearby_services": get_nearby_services(
                    latitude=lat,
                    longitude=lon,
                    page=function_args.get("page", 1),
                    radius_km=function_args.get("radius_km", 20),
                    page_size=function_args.get("page_size", 2),
                    user_name=function_args.get("user_name"),
                    tag_name=function_args.get("tag_name")
                )
            }
        elif function_name == "get_user_availability":
            function_response = {
                "user_availability": get_user_availability(
                    user_id_of_person=function_args["user_id_of_person"]
                )
            }
        elif function_name == "create_task":
            function_response = create_task(
                title=function_args.get("title"),
                task_type=function_args.get("task_type"),
                task_details=function_args.get("task_details"),
                assigned_to=function_args.get("assigned_to"),
                start_date=function_args.get("start_date"),
                due_date=function_args.get("due_date"),
                tags=function_args.get("tags"),
                created_by=user_id,
                client_id=function_args.get("client_id"),
                department_id=function_args.get("department_id"),
                location_id=function_args.get("location_id")
            )
        else:
            function_response = {"error": f"Unknown function: {function_name}"}
        
        # Print function response
        print("\n=== Function Response ===")
        print(json.dumps(function_response, indent=2))
        print("=======================\n")
        
        # Add to conversation history
        conversation_history[user_id].extend([
            {"role": "user", "parts": [{"text": query}]},
            {"role": "model", "parts": [{"functionCall": function_call}]}
        ])
        
        # Call Gemini again with function results
        follow_up_response = GeminiService.call_api(
            "",
            TOOLS,
            conversation_history[user_id] + [{
                "role": "function", 
                "parts": [{
                    "functionResponse": {
                        "name": function_name,
                        "response": function_response
                    }
                }]
            }]
        )
        
        if follow_up_response:
            candidate = follow_up_response.get("candidates", [{}])[0]
            content = candidate.get("content", {})
            part = content.get("parts", [{}])[0]
            ai_response = part.get("text", ai_response)
            
            # Add function response to conversation history
            conversation_history[user_id].append({
                "role": "function",
                "parts": [{
                    "functionResponse": {
                        "name": function_name,
                        "response": function_response
                    }
                }]
            })
    elif "text" in part:
        ai_response = part["text"]
    
    # Add final response to conversation history
    conversation_history[user_id].append({
        "role": "model",
        "parts": [{"text": ai_response}]
    })
    
    # Create simplified response with only AI response
    formatted_response = {
        "ai_response": ai_response
    }

    # Print response in terminal
    print("=== Response ===")
    print(json.dumps(formatted_response, indent=2))
    print("===============\n")
    
    return formatted_response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 