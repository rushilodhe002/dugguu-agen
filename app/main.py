"""Main FastAPI application."""
from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, List, Tuple
import json
from datetime import datetime, timedelta
import pytz
import re

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
# Store search results cache
search_cache: Dict[str, Dict] = {}
# Store appointment context for each user
appointment_context: Dict[str, Dict] = {}
# Conversation timeout in hours
CONVERSATION_TIMEOUT = 2
# Search cache timeout in minutes
SEARCH_CACHE_TIMEOUT = 30

# Tag name mapping for normalization
TAG_NAME_MAPPING = {
    # Medical professionals
    'doctor': 'doctor',
    'doctors': 'doctor',
    'physician': 'doctor',
    'physicians': 'doctor',
    'surgeon': 'doctor',
    'surgeons': 'doctor',
    'dentist': 'dentist',
    'dentists': 'dentist',
    'nurse': 'nurse',
    'nurses': 'nurse',
    
    # Government officials
    'mla': 'mla',
    'mlas': 'mla',
    'mp': 'mp',
    'mps': 'mp',
    'minister': 'minister',
    'ministers': 'minister',
    
    # Other service providers
    'lawyer': 'lawyer',
    'lawyers': 'lawyer',
    'advocate': 'lawyer',
    'advocates': 'lawyer',
    'teacher': 'teacher',
    'teachers': 'teacher',
    'professor': 'professor',
    'professors': 'professor'
}

# Marathi keywords for language detection
MARATHI_KEYWORDS = [
    # Pronouns and basic words
    "mi", "tu", "to", "te", "ho", "nahi", "kay", "ka", "kon", "kase", 
    "kuthe", "kevha", "kiti", "ahe", "aahe", "hot", "hoti", "ahet", 
    "mala", "tula", "tyala", "amhala", "tumhala", "tyanna", "pahije",
    "aai", "baba", "mulga", "mulgi", "ghar", "kam", "karnar", "karto",
    "karte", "kartoy", "kartos", "kartat", "kay", "kuth", "kich", "pan",
    "tar", "pudhe", "mule", "ithe", "thodi", "vel", "jau", "yeu", "ja",
    "ye", "gelo", "gela", "geli", "alo", "ali", "yet", "nako", "nka", 
    "mhanun", "ki", "ani",
    
    # Additional common Marathi words
    "tyachya", "tyachi", "tya", "tyala", "tyanna", "tyanche", "tyanchi",
    "maza", "mazi", "majha", "majhi", "majhe", "majhya", "majhi",
    "tumcha", "tumchi", "tumche", "tumchya", "tumchya",
    "amcha", "amchi", "amche", "amchya", "amchya",
    "sobat", "sathi", "karun", "karat", "kela", "keli", "kele",
    "appointment", "meeting", "task", "work", "job", "kam",
    "aaj", "udya", "kal", "parwa", "divas", "ratri", "sakal", "sandhyakal",
    "kiti", "keti", "kuthe", "kuthe", "kase", "kasa", "kashi",
    "mhanje", "mhanun", "mhanon", "mhanat", "mhanala", "mhanali",
    "pahije", "pahijet", "pahijel", "pahijeli", "pahijele",
    "sakta", "saktat", "saktel", "sakteli", "saktele",
    "shakta", "shaktat", "shaktel", "shakteli", "shaktele",
    "sangta", "sangtat", "sangtel", "sangteli", "sangtele",
    "sang", "sanga", "sangna", "sangnar", "sangnar",
    "book", "booking", "schedule", "time", "date", "divas",
    "meet", "meeting", "appointment", "appointments",
    "karnar", "karnar", "karnar", "karnar", "karnar",
    "karto", "karte", "kartoy", "kartos", "kartat",
    "kela", "keli", "kele", "kelo", "keli",
    "hot", "hoti", "hota", "hotat", "hotel",
    "ahe", "aahe", "ahet", "aahet", "ahet",
    "nahi", "naka", "nko", "nka", "nhi"
]

def detect_language(text: str) -> str:
    """Detect if text is Marathi or English."""
    if not text:
        return 'en'
    
    # Convert to lowercase and split into words
    words = re.findall(r'\w+', text.lower())
    
    # Count Marathi words
    marathi_word_count = sum(1 for word in words if word in MARATHI_KEYWORDS)
    
    # If more than 30% of words are Marathi, consider it Marathi
    if marathi_word_count / len(words) > 0.3:
        return 'mr'
    
    return 'en'

def get_default_response(lang: str) -> dict:
    """Get default response based on language."""
    if lang == 'mr':
        return {
            "response": {
                "message": "मला समजत नाही आलं. पुन्हा सांगू शकता का?",
                "profile": None
            }
        }
    return {
        "response": {
            "message": "I didn't understand that. Could you please rephrase?",
            "profile": None
        }
    }

def get_location_error(lang: str) -> dict:
    """Get location error response based on language."""
    if lang == 'mr':
        return {
            "response": {
                "message": "अक्षांश किंवा रेखांश फॉरमॅट चुकीचा आहे",
                "profile": None
            }
        }
    return {
        "response": {
            "message": "Invalid latitude or longitude format",
            "profile": None
        }
    }

def get_person_not_found_error(lang: str) -> dict:
    """Get person not found error based on language."""
    if lang == 'mr':
        return {
            "response": {
                "message": "मला तुम्हाला टास्क देण्यासाठी कोणताही व्यक्ती सापडला नाही. कृपया त्याचं नाव सांगा.",
                "profile": None
            }
        }
    return {
        "response": {
            "message": "I couldn't find the person you want to create a task for. Could you please mention their name first?",
            "profile": None
        }
    }

def normalize_tag_name(tag: str) -> str:
    """
    Normalize tag name to its standard form.
    Handles plural forms and common variations.
    """
    tag = tag.lower().strip()
    return TAG_NAME_MAPPING.get(tag, tag)

def parse_date_time(input_str: str) -> Tuple[str, str, int]:
    """
    Parse date and time from user input.
    Handles formats like:
    - "13/6/2025 2pm to 3pm"
    - "13/6/2025 2:00 PM to 3:00 PM"
    - "13-6-2025 14:00 to 15:00"
    Returns (date, time, duration_in_minutes)
    """
    # Extract date
    date_pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})'
    date_match = re.search(date_pattern, input_str)
    if not date_match:
        return None, None, None
    
    day, month, year = map(int, date_match.groups())
    date = f"{year}-{month:02d}-{day:02d}"
    
    # Extract time range
    time_pattern = r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*to\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'
    time_match = re.search(time_pattern, input_str.lower())
    if not time_match:
        return date, None, None
    
    # Parse start time
    start_hour, start_min, start_ampm = time_match.groups()[:3]
    start_hour = int(start_hour)
    start_min = int(start_min) if start_min else 0
    if start_ampm == 'pm' and start_hour < 12:
        start_hour += 12
    elif start_ampm == 'am' and start_hour == 12:
        start_hour = 0
    
    # Parse end time
    end_hour, end_min, end_ampm = time_match.groups()[3:]
    end_hour = int(end_hour)
    end_min = int(end_min) if end_min else 0
    if end_ampm == 'pm' and end_hour < 12:
        end_hour += 12
    elif end_ampm == 'am' and end_hour == 12:
        end_hour = 0
    
    # Calculate duration in minutes
    start_time = start_hour * 60 + start_min
    end_time = end_hour * 60 + end_min
    if end_time < start_time:
        end_time += 24 * 60  # Add 24 hours if end time is next day
    duration = end_time - start_time
    
    # Format time string
    time = f"{start_hour:02d}:{start_min:02d}:00"
    
    return date, time, duration

def clean_old_conversations():
    """Clean up old conversations and search cache based on timeout."""
    current_time = datetime.now()
    for user_id in list(last_interaction.keys()):
        if current_time - last_interaction[user_id] > timedelta(minutes=CONVERSATION_TIMEOUT):
            del conversation_history[user_id]
            del last_interaction[user_id]
            if user_id in search_cache:
                del search_cache[user_id]
            if user_id in appointment_context:
                del appointment_context[user_id]

def get_cached_search(user_id: str, search_key: str) -> Optional[Dict]:
    """Get cached search result if available and not expired."""
    if user_id not in search_cache:
        return None
    
    cache_entry = search_cache[user_id].get(search_key)
    if not cache_entry:
        return None
    
    cache_time = cache_entry.get("timestamp")
    if not cache_time or datetime.now() - cache_time > timedelta(minutes=SEARCH_CACHE_TIMEOUT):
        del search_cache[user_id][search_key]
        return None
    
    return cache_entry.get("result")

def cache_search_result(user_id: str, search_key: str, result: Dict):
    """Cache search result with timestamp."""
    if user_id not in search_cache:
        search_cache[user_id] = {}
    
    search_cache[user_id][search_key] = {
        "result": result,
        "timestamp": datetime.now()
    }

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
    
    # Clean old conversations and cache
    clean_old_conversations()
    
    # Print request details in terminal
    print("\n=== New Request ===")
    print(f"Query: {query}")
    print(f"User ID: {user_id}")
    print(f"Location: {latitude}, {longitude}")
    print("==================\n")

    # Detect user language
    current_lang = detect_language(query)
    print(f"Detected language: {'Marathi' if current_lang == 'mr' else 'English'}")

    # Convert latitude and longitude to float
    try:
        lat = float(latitude)
        lon = float(longitude)
    except ValueError:
        error_response = get_location_error(current_lang)
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

    # Check if this is an appointment-related query
    if any(word in query.lower() for word in ['appointment', 'schedule', 'book', 'meet', 'meeting']):
        # Try to parse date and time from the query
        date, time, duration = parse_date_time(query)
        if date and time and duration:
            # Store in appointment context
            if user_id not in appointment_context:
                appointment_context[user_id] = {}
            appointment_context[user_id].update({
                'date': date,
                'time': time,
                'duration': duration
            })

    # First system prompt for analyzing user query and deciding function calls
    analysis_prompt = f"""
    You are a friendly and helpful AI assistant that engages in natural conversation while efficiently handling tasks.
    Your responses should feel like talking to a friend, but you must also be quick to take action when needed.

    LANGUAGE REQUIREMENT:
    - User's language: {'Marathi' if current_lang == 'mr' else 'English'}
    - You MUST respond in the same language as the user's query
    - For Marathi: Use proper Devanagari script (यासारखे) for Marathi responses
    - For English: Respond in English

    CURRENT CONTEXT:
    - Current Date: {current_date}
    - Current Day: {current_day}
    - Current Time: {current_time_str}
    - Logged-in User ID: {user_id} 
    - Location: {lat}, {lon}
    - Appointment Context: {appointment_context.get(user_id, {})}

    CONVERSATION MANAGEMENT:
    1. Always maintain context from previous messages
    2. Track important information like:
       - Last mentioned person (name, ID, role, availability)
       - Current task/appointment details
       - User preferences
       - Previous decisions
       - Already collected information
    3. Use conversation history to understand context:
       {conversation_context}
    4. NEVER ask for information already provided
    5. NEVER search for a person again if already found
    6. Use stored information from previous searches
    7. Maintain timestamps for all interactions
    8. NEVER say "I didn't understand" unless absolutely necessary
    9. ALWAYS try to understand user intent from context
    10. Handle variations in date/time formats (e.g., "14june", "14 june", "june 14")
    11. Handle variations in duration formats (e.g., "1hr", "1 hour", "60 min")
    12. If user provides date/time/duration -> Use it immediately
    13. If user provides reason -> Use it immediately
    14. If any information is missing -> Ask only for missing information

    SPELLING AND UNDERSTANDING:
    - Handle spelling mistakes intelligently (e.g., "docor" -> "doctor", "mla" -> "MLA")
    - Understand common typos and variations
    - Use context to determine correct meaning
    - Don't ask for spelling corrections
    - Proceed with the most likely intended meaning
    - Handle multiple variations of the same word
    - Handle variations in date/time formats
    - Handle variations in duration formats
    - Handle variations in appointment scheduling phrases (e.g., "book", "schedule", "make appointment")

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
           "message": "Your warm, friendly response here",
           "profile": null
         }}
       }}

    3. For person-related queries:
       - If user asks about a specific person by name -> Use get_nearby_services with user_name
       - If user asks about a role/type (e.g., "doctor", "mla") -> Use get_nearby_services with tagName
       - If user uses pronouns (he/she/they) or "her/him/them" -> Check conversation history for last mentioned person
       - If user says "tell me about her/him" -> Use last mentioned person's details from conversation history
       - NEVER pass both user_name and tagName at the same time
       - If user_name is available, use that; if tagName is available, use that
       - Handle spelling variations in names and roles
       - NEVER search for a person again if already found in conversation history

    AVAILABLE FUNCTIONS:
    1. get_nearby_services(user_name, latitude, longitude)
       - Use when: User asks about a person or mentions someone
       - Example: "do you know anjali" or "i want to meet ramesh" -> IMMEDIATELY call get_nearby_services
       - Always use current location: {lat}, {lon}
       - MUST be called first before any other function when user mentions a person
       - If user_name is available, use that; if tagName is available, use that
       - NEVER pass both user_name and tagName at the same time
       - Handle spelling variations in names and roles
       - NEVER call if person already found in conversation history

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
       - Use conversation history to gather task details
       - Automatically determine priority from context
       - Use last mentioned person's details for IDs
       - Handle spelling variations in task details
       - NEVER ask for information already provided

    4. get_user_availability(user_id_of_person)
       - Use when: User wants to schedule a meeting AND we have found the person using get_nearby_services
       - Example: "i want to meet her" -> First call get_nearby_services, then get_user_availability
       - NEVER call this function before finding the person with get_nearby_services
       - Use last mentioned person's ID from conversation history
       - After getting availability, immediately ask: "Would you like to book an appointment at [time]?"

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
       - Use conversation history to gather appointment details
       - Handle spelling variations in appointment details
       - NEVER ask for information already provided
       - Handle variations in date/time formats
       - Handle variations in duration formats
       - If user provides date/time/duration -> Use it immediately
       - If user provides reason -> Use it immediately
       - If any information is missing -> Ask only for missing information

    FUNCTION CALL RULES:
    1. IMMEDIATELY call functions when triggered
    2. For user-related functions:
       - ALWAYS call get_nearby_services first when user mentions a person
       - Only call get_user_availability after finding the person
       - Only call create_appointment after checking availability
       - For pronouns or "tell me about her/him", use last mentioned person from conversation history
       - Handle spelling variations in names and roles
       - NEVER search for a person again if already found
    3. For create_appointment:
       - If user says "yes" or "correct" after details are provided -> CALL IMMEDIATELY
       - If user provides date/time without reason -> Ask for reason first
       - If user provides details -> Ask for confirmation
       - If user denies -> Ask for new details
       - Handle spelling variations in appointment details
       - NEVER ask for information already provided
       - Handle variations in date/time formats
       - Handle variations in duration formats
       - If user provides date/time/duration -> Use it immediately
       - If user provides reason -> Use it immediately
       - If any information is missing -> Ask only for missing information
    4. For create_task:
       - If user wants to create task -> Ask for reason and details first
       - Only create task after getting complete information
       - Use conversation history to gather task details
       - Automatically determine priority from context
       - Handle spelling variations in task details
       - NEVER ask for information already provided
    5. NO text response before function call
    6. Use context from previous messages
    7. If function call needed, return ONLY the function call
    8. If NO function call needed, respond with friendly message
    9. NEVER ask redundant questions
    10. Use stored information from conversation history
    11. NEVER say "I didn't understand" unless absolutely necessary
    12. ALWAYS try to understand user intent from context

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

    2. User: "find doctor near me"
       -> IMMEDIATELY return:
       {{
         "functionCall": {{
           "name": "get_nearby_services",
           "args": {{
             "tagName": "doctor",
             "latitude": {lat},
             "longitude": {lon}
           }}
         }}
       }}

    3. User: "tell me about her" (after finding Meghna)
       -> Use last mentioned person (Meghna) from conversation history
       -> Return friendly message with Meghna's details

    4. User: "yes" (after appointment details)
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

    5. User: "hi"
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
    - Conversation History: {conversation_context}
    """

    # Call Gemini API with function calling support and conversation history
    response = GeminiService.call_api(
        analysis_prompt,
        TOOLS,
        conversation_history[user_id]
    )
    
    if not response:
        return get_default_response(current_lang)
    
    # Process response
    candidate = response.get("candidates", [{}])[0]
    content = candidate.get("content", {})
    part = content.get("parts", [{}])[0]
    
    default_response = get_default_response(current_lang)
    
    # Initialize ai_response with default value
    ai_response = default_response
    
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
                    # Check cache first
                    search_key = f"{function_args.get('user_name', '')}_{function_args.get('tagName', '')}_{lat}_{lon}"
                    cached_result = get_cached_search(user_id, search_key)
                    
                    if cached_result:
                        print("\n=== Using Cached Search Result ===")
                        function_response = {"nearby_services": cached_result}
                    else:
                        function_args["latitude"] = lat
                        function_args["longitude"] = lon
                        
                        # Normalize tag name if present
                        if "tagName" in function_args:
                            function_args["tagName"] = normalize_tag_name(function_args["tagName"])
                        
                        search_result = get_nearby_services(
                            latitude=lat,
                            longitude=lon,
                            page=function_args.get("page", 1),
                            radius_km=function_args.get("radius_km", 20),
                            page_size=function_args.get("page_size", 2),
                            user_name=function_args.get("user_name"),
                            tag_name=function_args.get("tagName")
                        )
                        function_response = {"nearby_services": search_result}
                        # Cache the result
                        cache_search_result(user_id, search_key, search_result)
                elif function_name == "get_user_availability":
                    function_response = {
                        "user_availability": get_user_availability(
                            user_id_of_person=function_args["user_id_of_person"]
                        )
                    }
                elif function_name == "create_task":
                    # Get the last mentioned person's details from conversation history
                    last_person_details = None
                    for message in reversed(conversation_history[user_id]):
                        if message["role"] == "function" and "functionResponse" in message["parts"][0]:
                            response = message["parts"][0]["functionResponse"]["response"]
                            if "nearby_services" in response and response["nearby_services"]["success"]:
                                users = response["nearby_services"]["data"]["users"]
                                if users:
                                    last_person_details = users[0]
                                    break
                    
                    if not last_person_details:
                        ai_response = get_person_not_found_error(current_lang)
                    else:
                        # Extract required IDs from the last person's details
                        user_mapping = last_person_details.get("user_mapping", {})
                        department_id = user_mapping.get("department_id")
                        client_id = user_mapping.get("client_id")
                        location_id = user_mapping.get("location_id")
                        
                        # Get current date for start_date if not provided
                        current_date = datetime.now().strftime("%Y-%m-%d")
                        
                        # Set default due date to 7 days from now if not provided
                        due_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
                        
                        # Get task details from conversation history
                        task_details = []
                        for message in reversed(conversation_history[user_id]):
                            if message["role"] == "user":
                                text = message["parts"][0].get("text", "").lower()
                                if "road" in text or "bad" in text or "maintenance" in text:
                                    task_details.append(text)
                                if len(task_details) >= 3:  # Limit to last 3 relevant messages
                                    break
                        
                        # Combine task details
                        combined_details = " ".join(reversed(task_details)) if task_details else "Road maintenance work in the area"
                        
                        # Determine priority from conversation
                        priority = "medium"
                        for message in reversed(conversation_history[user_id]):
                            if message["role"] == "user":
                                text = message["parts"][0].get("text", "").lower()
                                if "high" in text or "urgent" in text or "very bad" in text:
                                    priority = "high"
                                    break
                                elif "low" in text:
                                    priority = "low"
                                    break
                        
                        # Create task with available information
                        function_response = create_task(
                            title=function_args.get("title", "Road Maintenance Task"),
                            task_type=function_args.get("task_type", "maintenance"),
                            task_details=combined_details,
                            assigned_to=last_person_details.get("user_id"),
                            start_date=current_date,
                            due_date=due_date,
                            tags=["maintenance", "roads", priority],
                            created_by=user_id,
                            client_id=client_id,
                            department_id=department_id,
                            location_id=location_id
                        )
                        
                        if function_response.get("success"):
                            if current_lang == 'mr':
                                ai_response = {
                                    "response": {
                                        "message": f"मी {last_person_details.get('first_name', '')} {last_person_details.get('last_name', '')} यांचा रोड मेंटेनन्स बाबत {priority} प्राधान्याचा टास्क बनवला आहे. टास्क आज सुरू होईल आणि ७ दिवसात संपेल.",
                                        "profile": None
                                    }
                                }
                            else:
                                ai_response = {
                                    "response": {
                                        "message": f"I've created a {priority} priority task for {last_person_details.get('first_name', '')} {last_person_details.get('last_name', '')} regarding road maintenance. The task will start today and is due in 7 days.",
                                        "profile": None
                                    }
                                }
                        else:
                            if current_lang == 'mr':
                                ai_response = {
                                    "response": {
                                        "message": "मी टास्क बनवला, पण तुम्हाला काही स्पेसिफिक डिटेल्स जोडायचे असल्यास सांगा.",
                                        "profile": None
                                    }
                                }
                            else:
                                ai_response = {
                                    "response": {
                                        "message": "I've created the task, but please let me know if you need to add any specific details or make any changes.",
                                        "profile": None
                                    }
                                }
                elif function_name == "create_appointment":
                    # Get appointment context
                    context = appointment_context.get(user_id, {})
                    
                    # Use context values if available, otherwise use function args
                    time = context.get('time') or function_args.get('time')
                    date = context.get('date') or function_args.get('date')
                    duration = context.get('duration') or function_args.get('duration')
                    
                    if 'T' in time:
                        time = time.split('T')[1].split('Z')[0]
                    elif ':' in time and len(time.split(':')) == 2:
                        time = f"{time}:00"
                    
                    target_user_id = function_args["target_user_id"]
                    user_availability_id = function_args["user_availability_id"]
                    reason = function_args["reason"]
                    
                    function_response = create_appointment(
                        target_user_id=target_user_id,
                        user_availability_id=user_availability_id,
                        date=date,
                        time=time,
                        duration=duration,
                        appointment_agenda=[reason],
                        creator_name=function_args.get("creator_name", "User"),
                        notes=function_args.get("notes", ""),
                        reason=reason,
                        loggedin_user_id=user_id,
                        client_id=function_args.get("client_id"),
                        department_id=function_args.get("department_id"),
                        location_id=function_args.get("location_id"),
                        created_by=user_id
                    )
                    
                    # Clear appointment context after successful creation
                    if function_response.get("success"):
                        appointment_context[user_id] = {}
                else:
                    function_response = {"error": f"Unknown function: {function_name}"}
                
                print("\n=== Function Response ===")
                print(json.dumps(function_response, indent=2))
                print("=======================\n")
                
                conversation_history[user_id].extend([
                    {"role": "user", "parts": [{"text": query}]},
                    {"role": "model", "parts": [{"functionCall": function_call}]}
                ])
                
                conversation_history[user_id].append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": function_name,
                            "response": function_response
                        }
                    }]
                })
                
                format_prompt = f"""
                Based on the function response, create a natural, conversational message. Follow these rules:
                1. NEVER show any IDs in the response
                2. Be friendly and helpful
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

                RESPONSE LANGUAGE:
                - You MUST respond in {'Marathi using Devanagari script' if current_lang == 'mr' else 'English'}
                - For Marathi: Use proper Devanagari script (यासारखे) for Marathi responses

                RESPONSE RULES:
                1. For get_nearby_services:
                   - If user found: {'मी [name] यांना सापडलो/सापडले, जे [designation] आहेत. त्यांचा ईमेल [email] आणि फोन नंबर [phone] आहे. तुम्हाला [name] यांच्याशी अपॉइंटमेंट बुक करायचे आहे का?' if current_lang == 'mr' else 'I found [name], who is [designation]. [Their/His/Her] email is [email] and phone number is [phone]. Would you like to schedule an appointment with [name]?'}
                   - If no user found: {'मला तुमच्या वर्णनाशी जुळणारा कोणी सापडला नाही. तुम्हाला वेगळा शोध करायचा आहे का?' if current_lang == 'mr' else 'I could not find anyone matching that description. Would you like to try a different search?'}
                   - NEVER mention user_id, location_id, or any other IDs
                   - Make the response conversational and friendly
                   - Always ask about scheduling an appointment after finding someone
                   - Use natural language and proper pronouns

                2. For get_user_availability:
                   - If available: {'चांगलं! [Name] [time period] मध्ये उपलब्ध आहेत. तुम्हाला अपॉइंटमेंट बुक करायचे आहे का? तुमची पसंतीची तारीख आणि वेळ सांगा.' if current_lang == 'mr' else 'Great! [Name] is available [time period]. Would you like to schedule an appointment? Just let me know your preferred date and time.'}
                   - If not available: {'माफ करा, [name] त्या वेळी उपलब्ध नाहीत. तुम्हाला वेगळा वेळ पाहायचा आहे का?' if current_lang == 'mr' else 'I am sorry, [name] is not available during that time. Would you like to try a different time?'}
                   - NEVER mention availability_id or any other IDs
                   - Make the response conversational and friendly
                   - Guide the user to provide date and time

                3. For create_appointment:
                   - If successful: {'छान! मी तुमचा [name] यांच्याशी [date] रोजी [time] वाजता [duration] मिनिटांचा अपॉइंटमेंट बुक केला आहे. [reason] बाबत चर्चा करण्यासाठी. तुम्हाला आणखी काही मदत हवी आहे का?' if current_lang == 'mr' else 'Perfect! I have scheduled your appointment with [name] for [date] at [time] for [duration] minutes to discuss [reason]. Is there anything else you need help with?'}
                   - If failed: {'माफ करा, मी अपॉइंटमेंट बुक करू शकलो नाही. तुम्हाला पुन्हा प्रयत्न करायचे आहे का?' if current_lang == 'mr' else 'I am sorry, I could not schedule the appointment. Would you like to try again?'}
                   - NEVER mention appointment_id or any other IDs
                   - Make the response conversational and friendly
                   - Offer additional help after successful booking

                4. For create_task:
                   - If successful: {'मी [name] यांच्यासाठी [task_details] बाबत [priority] प्राधान्याचा टास्क बनवला आहे. तुम्हाला आणखी काही मदत हवी आहे का?' if current_lang == 'mr' else 'I have created a task for [name] regarding [task_details]. The task is set to [priority] priority. Is there anything else you need help with?'}
                   - If failed: {'माफ करा, मी टास्क बनवू शकलो नाही. तुम्हाला पुन्हा प्रयत्न करायचे आहे का?' if current_lang == 'mr' else 'I am sorry, I could not create the task. Would you like to try again?'}
                   - NEVER mention task_id or any other IDs
                   - Make the response conversational and friendly
                   - Offer additional help after successful task creation

                5. For general conversation:
                   - Keep responses friendly and natural
                   - Use proper grammar and punctuation
                   - Include relevant details without technical information
                   - NEVER mention any IDs or technical details
                   - Make the conversation flow naturally
                   - Guide the user to the next step

                Current function response: {json.dumps(function_response, indent=2)}

                IMPORTANT: Your response MUST be a valid JSON string that can be parsed by json.loads(). Do not include any markdown formatting or additional text.
                """
                
                response = GeminiService.call_api(
                    format_prompt,
                    TOOLS,
                    conversation_history[user_id]
                )
                
                print("\n=== Debug: API Response ===")
                print(json.dumps(response, indent=2))
                print("=========================\n")
                
                if not response:
                    print("\n=== Debug: Empty Response ===")
                    ai_response = default_response
                elif "candidates" not in response or not response["candidates"]:
                    print("\n=== Debug: No Candidates ===")
                    ai_response = default_response
                else:
                    candidate = response["candidates"][0]
                    print("\n=== Debug: First Candidate ===")
                    print(json.dumps(candidate, indent=2))
                    print("=========================\n")
                    
                    content = candidate.get("content", {})
                    print("\n=== Debug: Content ===")
                    print(json.dumps(content, indent=2))
                    print("=====================\n")
                    
                    parts = content.get("parts", [])
                    if not parts:
                        print("\n=== Debug: No Parts ===")
                        ai_response = default_response
                    else:
                        part = parts[0]
                        print("\n=== Debug: Part ===")
                        print(json.dumps(part, indent=2))
                        print("==================\n")
                        
                        if "text" not in part:
                            print("\n=== Debug: No Text in Part ===")
                            ai_response = default_response
                        else:
                            try:
                                # Get raw text and ensure it's a string
                                raw_text = str(part.get("text", "{}"))
                                print("\n=== Debug: Raw Text ===")
                                print(f"Type: {type(raw_text)}")
                                print(f"Length: {len(raw_text)}")
                                print(f"Content: {repr(raw_text)}")
                                print("=====================\n")
                                
                                # Clean the text
                                cleaned_text = clean_json_response(raw_text)
                                print("\n=== Debug: Cleaned Text ===")
                                print(f"Type: {type(cleaned_text)}")
                                print(f"Length: {len(cleaned_text)}")
                                print(f"Content: {repr(cleaned_text)}")
                                print("=====================\n")
                                
                                # Ensure we have a valid JSON string
                                if not cleaned_text or cleaned_text.isspace():
                                    print("\n=== Debug: Empty Cleaned Text ===")
                                    ai_response = default_response
                                else:
                                    try:
                                        # Try to parse as JSON
                                        ai_response = json.loads(cleaned_text)
                                        
                                        # Validate response structure
                                        if not isinstance(ai_response, dict):
                                            print("\n=== Debug: Response Not Dict ===")
                                            ai_response = default_response
                                        elif "response" not in ai_response:
                                            print("\n=== Debug: No Response Key ===")
                                            ai_response = default_response
                                        elif not isinstance(ai_response["response"], dict):
                                            print("\n=== Debug: Response Value Not Dict ===")
                                            ai_response = default_response
                                        elif "message" not in ai_response["response"]:
                                            print("\n=== Debug: No Message Key ===")
                                            ai_response = default_response
                                    except json.JSONDecodeError as e:
                                        print(f"\n=== Debug: JSON Parse Error ===")
                                        print(f"Error: {str(e)}")
                                        print(f"Error Type: {type(e)}")
                                        print(f"Error Args: {e.args}")
                                        print("Raw text:", repr(raw_text))
                                        print("Cleaned text:", repr(cleaned_text))
                                        print("=====================\n")
                                        ai_response = default_response
                            except Exception as e:
                                print(f"\n=== Debug: Error Processing Response ===")
                                print(f"Error: {str(e)}")
                                print(f"Error Type: {type(e)}")
                                print(f"Error Args: {e.args}")
                                print("=====================\n")
                                ai_response = default_response
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