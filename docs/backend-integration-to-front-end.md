# Backend Integration with the Front End Plan
**Audience:** Beginner to intermediate developers integrating a frontend with a FastAPI backend  

## Overview Plan:
### Phase 1: Minimal Fast API Echo Server
Create a basic /chat endpoint that just echoes messages back
- Test: curl or Postman
- Goal: Verify FastAPI works and CORS is configured

### Phase 2: Connect Existing Streaming Logic
- Use Server-Sent Events (SSE) for streaming
- Test: Single conversation works via HTTP

### Phase 3: Add Session Management
Handle multiple users with thread/session IDs
- Store sessions per user
- Test: Two concurrent conversations work independently

### Phase 4: Connect to Frontend
Point to Chatkit widget to your backend
- Test: Full conversation flow from browser
- Verify streaming works in real-time

### Phase 5: Polish
Add error handling, logging, database verification







## Execute plan:
## Phase 1: Minimal Fast API Echo Server
- Create `api.py` - A FastAPI server with:
- `/` - Root endpoint (returns server info)
- `/health` - Health check
- `/chat` - Streaming chat endpoint that echoes your message word-by-word using Server Sent Events (SSE)
- `CORS` enabled for frontend at localhost: 3000

### Steps to test
#### Step 1: Start the server
```
 uv run uvicorn api:app --reload --port 8000 
```
- What it does: Starts the FastAPI server on port 8000 with auto-reload (restarts when you change code)
- Expected output: Should say "Uvicorn running on http://127.0.0.1:8000"
- FastAPI is your app’s code. Uvicorn is the program that actually starts it and listens for requests.
- Browsers, curl, and Postman can’t talk directly to Python files
- Uvicorn:
    - Starts a local web server
    - Receives HTTP requests (like /chat)
    - Sends them to your FastAPI app
    - Returns responses back to the client

#### Step 2: Test Root Endpoint (in a new terminal!!!) 
```
curl http://localhost:8000/
```
- What it does: Checks if the server is responding                     
- Expected output: JSON with {"status": "ok", "service": "Digital Town Hall API", ...}
- `curl` lets you talk to your server from the terminal, the same way a browser or an app would.

### Step 3: Test Health Endpoint
```
curl http://localhost:8000/health
```
- What it does: Checks if server is responding
- Expected output: JSON with {"status": "healthy"}

### Step 4: Test Streaming Chat Endpoint (In Terminal or Postman)
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello from the backend", "session_id": "test123"}'
```

#### What it does

* Sends a chat message to the backend to the `/chat` endpont
    ```-H "Content-Type: application/json" \```
    - This tells the server: "I am sending JSON data"
    ```-d '{"message": "Hello from the backend", "session_id": "test123"}'```
    - This is the request body.
    - `message` is the message you want to send
    - You can add more fields here if your API expects them (e.g. user info, metadata, options)
* Receives a **streaming response** via Server-Sent Events (SSE)




#### Expected Output

You should see each word streamed one at a time:

```
data: Hello

data: from

data: the

data: backend

data: [DONE]
```

---
### Additional Notes:
* What is `CORS?` - browser security rule that controls which websites are allowed to talk to your backend API.

#### Success Criteria for Phase 1

* Server starts without errors
* Root endpoint returns JSON
* Chat endpoint streams words back
* CORS headers are present (check with browser DevTools later)


