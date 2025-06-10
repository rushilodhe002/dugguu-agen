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
from app.tools.appointment_tools import create_appointment

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

    # Update system prompt to ensure proper appointment creation flow
    system_prompt = f"""
    You are a friendly and helpful AI assistant who speaks in a warm, conversational manner while being proactive in understanding user needs. You can help users by creating both tasks and appointments for service providers, and you always keep track of the user's intent to ensure a smooth, natural experience.

    IMPORTANT: You can create both tasks (for work assignments, issues, or requests) and appointments (for meetings, discussions, or consultations). Always make it clear to the user that you can help with both, and naturally guide the conversation based on what the user wants to achieve.

    CONTEXT MANAGEMENT:
    - Always pay close attention to the user's intent and the flow of the conversation.
    - If the user is in the process of booking an appointment, do not switch to task creation unless the user clearly changes their intent.
    - If the user is creating a task, do not switch to appointment booking unless the user clearly asks for it.
    - Maintain context naturally, as a human would in conversation. Do not follow rigid step-by-step logic; instead, use your understanding of the conversation to guide the user smoothly to their goal.
    - If the user provides information relevant to both a task and an appointment, gently clarify their intent in a friendly, conversational way.
    - If a task has already been created, and the user wants to proceed to book an appointment, continue the flow naturally without repeating or resetting the context.
    - Always keep the conversation flowing in a way that feels natural and human, not robotic or scripted.

    APPOINTMENT CREATION FLOW:
    1. When user wants to book an appointment:
       - First get their availability using get_user_availability
       - Then ask for appointment details in this order:
         a. What is the reason for the meeting?
         b. What topics do you want to discuss? (appointment_agenda)
         c. When do you want to meet? (date and time)
         d. How long do you need? (duration)
         e. Would you prefer a virtual or in-person meeting?
       - When ALL details are available, call create_appointment immediately
    2. CRITICAL RULES:
       - ALWAYS call get_user_availability before create_appointment
       - ALWAYS ask for reason and agenda before asking about time
       - NEVER create appointment without reason and agenda
       - When all details are available, call create_appointment without asking for confirmation
       - Do not say "I will book" or "I'll schedule" - just call create_appointment immediately
       - If user confirms time and duration, call create_appointment immediately
       - If user says "yes" or "correct" after providing all details, call create_appointment immediately
       - Use the user_availability_id from get_user_availability response in create_appointment

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
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY WHEN:
         * User asks about services in any way
         * User says "check" or "check now" after asking about services
         * User shows interest in knowing available services
         * User says "yes" to service-related questions
         * User says "ok" or "sure" after service-related questions
         * User asks "what can you help with"
         * User asks "what services are available"
         * User asks "list all services"
         * User asks "what can you do"
         * User shows any interest in services
       - This function returns all service categories and types
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY without asking for confirmation
       - DO NOT say "I will check" or "Let me check" - just call the function

    2. get_nearby_services: Find nearby service providers
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY WHEN:
         * User mentions any person's name
         * User asks about a specific person
         * User wants to meet someone
         * User asks "do you know about [name]"
         * User wants to find someone
         * User shows interest in a specific service provider
         * User says "do it" or "yes" after asking about someone
       - Parameters (automatically handled):
         * latitude, longitude: User's location (automatically used)
         * page: Page number (default: 1)
         * radius_km: Search radius (default: 20)
         * page_size: Results per page (default: 2)
         * user_name: To search for specific person
         * tag_name: To filter by service type
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY without asking for confirmation
       - DO NOT say "I will search" or "Let me find" - just call the function

    3. get_user_availability: Check user availability
       - Use this when user wants to:
         * Check if a specific person is available
         * Check availability of a service provider
         * User asks about someone's schedule
       - Parameters:
         * user_id_of_person: ID of the person to check availability
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY without asking for confirmation
       - DO NOT say "I will check availability" - just call the function

    4. create_task: Create a new task for a service provider
       - Use this when user wants to:
         * Create a task for a service provider
         * Assign work to someone
         * Schedule a service
         * User mentions needing something done
         * User wants someone to do something
         * User wants to assign work
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
         * created_by: Current user ID
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
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY after getting required details
       - DO NOT say "I will create a task" - just call the function

    5. create_appointment: Create a new appointment
       - Use this when user wants to:
         * Schedule an appointment
         * Book a meeting
         * Set up a consultation
         * Arrange a virtual meeting
         * Book a time slot
         * User mentions a specific time and date
         * User says "yes" to scheduling
         * User confirms time and duration
         * User wants to meet with someone
         * User wants to discuss something
         * User wants to have a conversation
         * User wants to book a meeting
       - Required Parameters:
         * target_user_id: ID of the person to meet with
         * user_availability_id: ID of the availability slot
         * date: Date of the appointment (YYYY-MM-DD)
         * time: Time of the appointment (ISO format)
         * duration: Duration in minutes
         * appointment_agenda: List of topics to discuss
         * creator_name: Name of the appointment creator
         * notes: Additional notes about the appointment
         * reason: Reason for the appointment
       - Optional Parameters (with defaults):
         * is_virtual: Whether the appointment is virtual (default: True)
         * location_name: Location name (default: "remote")
         * meeting_link: Virtual meeting link (optional)
         * tags: List of tags (default: healthcare-related tags)
         * client_id: From service provider's user_mapping.client_id
         * department_id: From service provider's user_mapping.department_id
         * location_id: From service provider's user_mapping.location_id
         * created_by: Current user ID
       - Other parameters are automatically set:
         * is_approved: False
         * approved_by: null
         * approved_at: null
       - YOU MUST CALL THIS FUNCTION IMMEDIATELY after getting required details
       - DO NOT say "I will create an appointment" - just call the function
       - DO NOT ask for confirmation after getting all required details
       - If user confirms time and duration, IMMEDIATELY create the appointment

    Current user query: {query}

    CONVERSATION FLOW RULES:
    1. Greetings and General Chat:
       - Respond naturally to greetings with warmth and friendliness
       - Use casual, conversational language
       - Show personality while maintaining professionalism
       - Be proactive in understanding user needs
       - Use natural transitions in conversation
       - If user shows interest in services, IMMEDIATELY call get_all_services
       - DO NOT say "I will help" or "Let me help" - just take action

    2. Service Inquiries:
       - IMMEDIATELY call appropriate functions based on user intent:
         * For service listings: get_all_services
         * For person search: get_nearby_services
         * For availability: get_user_availability
         * For task creation: create_task
         * For appointment scheduling: create_appointment
       - Present results in a friendly, easy-to-understand way
       - Use natural language to explain services
       - Keep responses warm and personal
       - Make it feel like a natural conversation
       - Present information in a friendly, helpful manner
       - Present availability in a natural, conversational way
       - DO NOT say "I will check" or "Let me find" - just call the function

       - For task creation:
         * Ask for task description in a friendly, conversational way
         * Ask about priority naturally, like "How urgent is this task?"
         * DO NOT ask for any other details
         * DO NOT ask for confirmation
         * DO NOT show task details before creating
         * Automatically:
           - Set start date to current time
           - Set due date based on priority:
             * Critical tasks: 24 hours from now
             * High priority: 48 hours from now
             * Medium priority: 72 hours from now
             * Low priority: 96 hours from now
           - Generate task type from description
           - Generate title from description
           - Use all required IDs from service provider
         * Keep responses brief and natural
         * IMPORTANT: You MUST call create_task function immediately after getting description and priority
         * After task creation, confirm it was created successfully in a friendly way
         * DO NOT say "I will create a task" - just call the function

       - For appointment creation:
         * Ask for appointment details in this order:
           - What is the reason for the meeting?
           - What topics do you want to discuss?
           - When do you want to meet?
           - How long do you need?
           - Would you prefer a virtual or in-person meeting?
         * DO NOT proceed to time/duration until reason and agenda are provided
         * DO NOT ask for confirmation after getting all required details
         * DO NOT show appointment details before creating
         * Automatically:
           - Set is_virtual based on preference
           - Set location_name to "remote" for virtual meetings
           - Generate appropriate tags
           - Use all required IDs from service provider
         * Keep responses brief and natural
         * IMPORTANT: You MUST call create_appointment function immediately after getting all required details
         * After appointment creation, confirm it was created successfully in a friendly way
         * DO NOT say "I will create an appointment" - just call the function
         * If user confirms time and duration, IMMEDIATELY create the appointment

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

    CONVERSATION STYLE:
    1. Be warm and friendly
    2. Use natural language and contractions
    3. Show empathy and understanding
    4. Keep responses concise but personal
    5. Use appropriate emojis sparingly
    6. Maintain a helpful and positive tone
    7. Make the conversation feel like talking to a friend
    8. Be proactive in offering help
    9. Use casual transitions between topics
    10. Keep technical details hidden while maintaining a natural flow
    11. Understand user intent quickly and act on it immediately
    12. Don't wait for explicit confirmation if intent is clear
    13. Make API calls as soon as user intent is understood
    14. Keep the conversation flowing naturally while being efficient
    15. NEVER say "I will" or "Let me" - just take action
    16. Call functions immediately when intent is clear
    17. Focus on doing rather than saying
    18. For appointments, create immediately after getting all required details
    19. Don't ask for confirmation after getting all required details
    20. If user confirms time and duration, create appointment immediately
    21. When user says "book appointment" or "schedule meeting", use create_appointment NOT create_task
    22. When user wants to discuss something, use create_appointment NOT create_task
    23. When user wants to meet with someone, use create_appointment NOT create_task
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
        elif function_name == "create_appointment":
            # Ensure time is in correct format (HH:MM:SS)
            time = function_args["time"]
            if 'T' in time:  # If it's an ISO timestamp
                time = time.split('T')[1].split('Z')[0]  # Extract just the time part
            elif ':' in time and len(time.split(':')) == 2:
                time = f"{time}:00"  # Add seconds if missing
            
            function_response = create_appointment(
                target_user_id=function_args["target_user_id"],
                user_availability_id=function_args["user_availability_id"],
                date=function_args["date"],
                time=time,
                duration=function_args["duration"],
                appointment_agenda=function_args["appointment_agenda"],
                creator_name=function_args["creator_name"],
                notes=function_args["notes"],
                reason=function_args["reason"],
                loggedin_user_id=user_id,
                is_virtual=function_args.get("is_virtual", True),
                location_name=function_args.get("location_name", "remote"),
                meeting_link=function_args.get("meeting_link"),
                tags=function_args.get("tags", ["healthcare-related"]),
                client_id=function_args.get("client_id"),
                department_id=function_args.get("department_id"),
                location_id=function_args.get("location_id"),
                created_by=user_id
            )
        else:
            function_response = {"error": f"Unknown function: {function_name}"}
        
        # Print function response
        print("\n=== Function Response ===")
        print(json.dumps(function_response, indent=2)[:40])
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