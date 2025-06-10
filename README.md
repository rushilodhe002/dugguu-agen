# Service Finder API

A FastAPI-based service that helps users find services near their location using AI-powered search.

## Features

- Location-based service search
- AI-powered query understanding
- Integration with Gemini API
- CORS enabled for cross-origin requests
- Structured JSON responses

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── services/
│       ├── __init__.py
│       ├── gemini_service.py
│       └── location_service.py
├── requirements.txt
└── README.md
```

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python -m app.main
```

The API will be available at `http://localhost:8000`

## API Usage

### Search Endpoint

```
GET /search?query={query}&user_id={user_id}&latitude={latitude}&longitude={longitude}
```

Parameters:
- `query`: The search query (string)
- `user_id`: User identifier (string)
- `latitude`: Location latitude (string)
- `longitude`: Location longitude (string)
- `authorization`: Bearer token (optional, in header)

Example:
```
GET /search?query=find%20doctor%20near%20me&user_id=123&latitude=28.6136&longitude=77.2090
```

Response:
```json
{
  "status": "success",
  "data": {
    "query": "find doctor near me",
    "user_id": "123",
    "location": {
      "latitude": "28.6136",
      "longitude": "77.2090"
    },
    "ai_response": "Based on your location in Delhi..."
  }
}
```

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc` 