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

def clean_json_response(text: str) -> str:
    """Clean the response text to handle markdown-formatted JSON."""
    # Remove markdown code block if present
    if "```json" in text:
        text = text.split("```json")[1]
    elif "```" in text:
        text = text.split("```")[1]
    
    # Remove any trailing markdown
    if "```" in text:
        text = text.split("```")[0]
    
    # Remove any leading/trailing whitespace and newlines
    text = text.strip()
    
    # Remove any remaining backticks
    text = text.replace("`", "")
    
    # Remove any remaining newlines
    text = text.replace("\n", "")
    
    # Remove any extra spaces
    text = " ".join(text.split())
    
    return text

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
            "response": {
                "message": "Invalid latitude or longitude format",
                "profile": None
            }
        }
        print(f"Error: {error_response['response']['message']}\n")
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

    # First system prompt for analyzing user query and deciding function calls
    analysis_prompt = f"""
    You are a friendly and helpful AI assistant that engages in natural conversation while efficiently handling tasks.
    Your responses should feel like talking to a friend, but you must also be quick to take action when needed.

    CURRENT CONTEXT:
    - Current Date: {current_date}
    - Current Day: {current_day}
    - Current Time: {current_time_str}
    - Logged-in User ID: {user_id}
    - Location: {lat}, {lon}

    CONVERSATION RULES:
    1. You can answer general questions naturally without function calls, such as:
       - Recipes and cooking instructions
       - General knowledge questions
       - Current affairs and news
       - Casual conversation
       - Facts about countries, leaders, etc.
       - Weather information
       - Health and wellness tips
       - Entertainment and movies
       - Sports and games
       - Technology and gadgets
       - Travel and tourism
       - Education and learning
       - Business and finance
       - Science and nature
       - History and culture

    2. For these topics, respond naturally with:
       {{
         "response": {{
           "message": "Your friendly, informative response here",
           "profile": null
         }}
       }}

    AVAILABLE FUNCTIONS:
    1. get_nearby_services(user_name, latitude, longitude)
       - Use when: User asks about a person or mentions someone
       - Example: "do you know anjali" -> IMMEDIATELY call get_nearby_services
       - Always use current location: {lat}, {lon}

    2. get_all_services()
       - Use when: User says "check" or "ok"
       - Example: "check" -> IMMEDIATELY call get_all_services

    3. create_task(title, task_type, task_details, assigned_to, etc.)
       - Use when: User wants to create a task AND has provided:
         * Reason/purpose for the task
         * Task details
         * Duration/priority
       - Example: "create task for her" -> First ask for reason and details
       - Always use logged-in user ID: {user_id}

    4. get_user_availability(user_id_of_person)
       - Use when: User wants to schedule a meeting
       - Example: "i want to meet her" -> IMMEDIATELY call get_user_availability

    5. create_appointment(target_user_id, date, time, duration, etc.)
       - Use when: User confirms appointment details with "yes" or "correct" AND has provided:
         * Reason for the appointment
         * Preferred date and time
         * Duration
         * Agenda points
       - Required parameters:
         * target_user_id (from previous conversation)
         * user_availability_id (from availability check)
         * date (from user's preferred date)
         * time (from user's preferred time)
         * duration (from user's input)
         * reason (from user's input)
         * client_id (from config)
         * department_id (from config)
         * location_id (from config)
         * loggedin_user_id: {user_id}
       - Example: When user confirms -> First verify all details are collected

    FUNCTION CALL RULES:
    1. IMMEDIATELY call functions when triggered
    2. For create_appointment:
       - If user says "yes" or "correct" after details are provided -> CALL IMMEDIATELY
       - If user provides date/time without reason -> Ask for reason first
       - If user provides details -> Ask for confirmation
       - If user denies -> Ask for new details
    3. For create_task:
       - If user wants to create task -> Ask for reason and details first
       - Only create task after getting complete information
    4. NO text response before function call
    5. Use context from previous messages
    6. If function call needed, return ONLY the function call
    7. If NO function call needed, respond with friendly message

    RESPONSE FORMAT:
    For general conversation (no function call needed):
    {{
      "response": {{
        "message": "Your warm, friendly response here",
        "profile": null
      }}
    }}

    For function calls, return ONLY the function call object:
    {{
      "functionCall": {{
        "name": "function_name",
        "args": {{
          "param1": "value1",
          "param2": "value2"
        }}
      }}
    }}

    EXAMPLES:
    1. User: "do you know anjali"
       -> IMMEDIATELY return:
       {{
         "functionCall": {{
           "name": "get_nearby_services",
           "args": {{
             "user_name": "anjali",
             "latitude": {lat},
             "longitude": {lon}
           }}
         }}
       }}

    2. User: "yes" (after appointment details)
       -> IMMEDIATELY return:
       {{
         "functionCall": {{
           "name": "create_appointment",
           "args": {{
             "target_user_id": "previous_user_id",
             "user_availability_id": "availability_id",
             "date": "{current_date}",
             "time": "16:00:00",
             "duration": 30,
             "reason": "incomplete work of school",
             "client_id": "3dbb0be6-5d65-49b1-b2ed-034f1806582b",
             "department_id": "department_id",
             "location_id": "location_id",
             "loggedin_user_id": "{user_id}"
           }}
         }}
       }}

    3. User: "hi"
       -> Return friendly message:
       {{
         "response": {{
           "message": "Hey there! How can I help you today? 😊",
           "profile": null
         }}
       }}

    Current user query: {query}
    Current context:
    - User ID: {user_id}
    - Location: {lat}, {lon}
    - Date: {current_date}
    - Time: {current_time_str}
    - Day: {current_day}
    """

    # Call Gemini API with function calling support and conversation history
    response = GeminiService.call_api(
        analysis_prompt,
        TOOLS,
        conversation_history[user_id]
    )
    
    if not response:
        return {
            "response": {
                "message": "Failed to get response from AI service",
                "profile": None
            }
        }
    
    # Process response
    candidate = response.get("candidates", [{}])[0]
    content = candidate.get("content", {})
    part = content.get("parts", [{}])[0]
    
    default_response = {
        "response": {
            "message": "I didn't understand that. Could you please rephrase?",
            "profile": None
        }
    }
    
    # Handle function call if present
    if "text" in part:
        raw_text = part.get("text", "{}")
        cleaned_text = clean_json_response(raw_text)
        try:
            parsed_response = json.loads(cleaned_text)
            if "functionCall" in parsed_response:
                function_call = parsed_response["functionCall"]
                function_name = function_call["name"]
                function_args = function_call["args"]
                
                print(f"\n=== Function Call ===")
                print(f"Function: {function_name}")
                print(f"Args: {json.dumps(function_args, indent=2)}")
                print("===================\n")
                
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
                    
                    # Get required parameters from conversation history or function args
                    target_user_id = function_args["target_user_id"]
                    user_availability_id = function_args["user_availability_id"]
                    date = function_args["date"]
                    duration = function_args["duration"]
                    reason = function_args["reason"]
                    
                    # Create appointment with required parameters
                    function_response = create_appointment(
                        target_user_id=target_user_id,
                        user_availability_id=user_availability_id,
                        date=date,
                        time=time,
                        duration=duration,
                        appointment_agenda=[reason],  # Use reason as agenda
                        creator_name=function_args.get("creator_name", "User"),
                        notes=function_args.get("notes", ""),
                        reason=reason,
                        loggedin_user_id=user_id,
                        client_id=function_args.get("client_id"),
                        department_id=function_args.get("department_id"),
                        location_id=function_args.get("location_id"),
                        created_by=user_id
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
                
                # Let Gemini format the response
                format_prompt = f"""
                Based on the function response, create a natural, conversational message. Follow these rules:
                1. Be friendly and helpful
                2. Include relevant details from the response
                3. Format the response as JSON with this EXACT structure:
                {{
                    "response": {{
                        "message": "your natural response here",
                        "profile": [
                            {{
                                "name": "full name",
                                "email": "email address",
                                "phone_number": "phone number",
                                "designation": "role name"
                            }}
                        ]
                    }}
                }}

                For get_nearby_services:
                - If user found: Format profile EXACTLY as shown above
                - Combine first_name and last_name for the name field
                - Use phone for phone_number
                - Use role from official_information[0].role for designation
                - If no user found: Set profile to null
                - Add a friendly message about the person and their role
                - Ask if they want to schedule an appointment or create a task
                - NEVER show any IDs in the response
                Example response:
                {{
                  "response": {{
                    "message": "I found [name]! They are a [role] and can help you with [services]. Would you like to schedule an appointment with them or create a task?",
                    "profile": [
                      {{
                        "name": "full name",
                        "email": "email address",
                        "phone_number": "phone number",
                        "designation": "role name"
                      }}
                    ]
                  }}
                }}

                For get_user_availability:
                - Format response to focus on current week's availability
                - If available all week, say "Available all week from [start time] to [end time]"
                - If specific days available, list only those days
                - Keep response concise and clear
                - Ask if they want to schedule
                - If they say yes, ask for:
                  * Reason for the appointment
                  * Preferred date and time
                  * Duration (in minutes)
                  * Agenda points
                - Set profile to null
                - NEVER show any IDs in the response

                For create_appointment:
                - If user confirms appointment details:
                  * Call create_appointment with:
                    - target_user_id (from previous conversation)
                    - user_availability_id (from availability check)
                    - date (from user's preferred date)
                    - time (from user's preferred time)
                    - duration (from user's input)
                    - reason (from user's input)
                    - client_id (from config)
                    - department_id (from config)
                    - location_id (from config)
                - If appointment created successfully:
                  * Confirm the appointment details
                  * Provide next steps
                - If error:
                  * Explain the issue
                  * Suggest alternatives
                - Set profile to null
                - NEVER show any IDs in the response

                For create_task:
                - If task created successfully:
                  * Confirm the task details
                  * Provide next steps
                - If error:
                  * Explain the issue
                  * Suggest alternatives
                - Set profile to null
                - NEVER show any IDs in the response

                Current function: {function_name}
                Function response: {json.dumps(function_response, indent=2)}
                """
                
                response = GeminiService.call_api(
                    format_prompt,
                    TOOLS,
                    conversation_history[user_id]
                )
                
                if response and "candidates" in response:
                    candidate = response["candidates"][0]
                    content = candidate.get("content", {})
                    part = content.get("parts", [{}])[0]
                    
                    if "text" in part:
                        try:
                            ai_response = json.loads(clean_json_response(part["text"]))
                        except json.JSONDecodeError:
                            ai_response = {
                                "response": {
                                    "message": "I couldn't process that response properly. Could you please try again?",
                                    "profile": None
                                }
                            }
                    else:
                        ai_response = {
                            "response": {
                                "message": "I couldn't process that response properly. Could you please try again?",
                                "profile": None
                            }
                        }
                else:
                    ai_response = {
                        "response": {
                            "message": "I couldn't process that response properly. Could you please try again?",
                            "profile": None
                        }
                    }
            elif "response" in parsed_response:
                ai_response = parsed_response
            else:
                ai_response = default_response
        except json.JSONDecodeError as e:
            print(f"\n=== JSON Parse Error ===")
            print(f"Error: {str(e)}")
            print("=====================\n")
            ai_response = default_response
    elif "text" in part:
        print("\n=== Raw Gemini Response ===")
        print(json.dumps(part, indent=2))
        print("=========================\n")
        
        try:
            # Try to parse the response as JSON
            raw_text = part.get("text", "{}")
            print("\n=== Raw Text Response ===")
            print(raw_text)
            print("=======================\n")
            
            # Clean the response text
            cleaned_text = clean_json_response(raw_text)
            print("\n=== Cleaned Text Response ===")
            print(cleaned_text)
            print("=========================\n")
            
            ai_response = json.loads(cleaned_text)
            if not isinstance(ai_response, dict) or "response" not in ai_response:
                print("\n=== Invalid Response Format ===")
                print("Response missing 'response' key or not a dict")
                print("=============================\n")
                ai_response = default_response
        except json.JSONDecodeError as e:
            print(f"\n=== JSON Parse Error ===")
            print(f"Error: {str(e)}")
            print("=====================\n")
            ai_response = default_response
    
    # Add final response to conversation history
    conversation_history[user_id].append({
        "role": "model",
        "parts": [{"text": json.dumps(ai_response)}]
    })
    
    # Print final response
    print("\n=== Final Response ===")
    print(json.dumps(ai_response, indent=2))
    print("=====================\n")
    
    return ai_response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 