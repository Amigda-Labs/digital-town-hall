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
#### Additional Notes:
* What is `CORS?` - browser security rule that controls which websites are allowed to talk to your backend API.

#### Success Criteria for Phase 1

* Server starts without errors
* Root endpoint returns JSON
* Chat endpoint streams words back
* CORS headers are present (check with browser DevTools later)



## Phase 2

After applying the code changes:

### Step 1: Start the server
```
uv run uvicorn api:app --reload --port 8000
```
### Step 2: Test with a chat message
Open a new terminal and try this:
(Note: Enter them line by line "\" means that this command continue to the next line, enter the message for every "\")
```curl
curl -X POST http://localhost:8000/chat \                                                                                                                   
    -H "Content-Type: application/json" \                                                                                                                     
    -d '{"message": "Hello, I want to report a pothole on Main Street"}' \                                                                                    
    -N
```

### Step 3: Test session persistence
Send a follow-up message with the same session_id:

#### First message - creates session
```            
  curl -X POST http://localhost:8000/chat \
    -H "Content-Type: application/json" \
    -d '{"message": "Hi there", "session_id": "test-user-123"}' \  
    -N
```

#### Second message - reuses session (should remember context)
```                                                                                               
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What did I just say?", "session_id": "test-user-123"}' \
  -N
```

#### Third message - reuses session (should remember context and should trigger the function tools, also look at the openai traces)
```
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "hi there i would like to give some feedback, I would like to suggest we should have lockers in ginza station becaause people shop there more, it’s hard to bring your shopping bags everywhere. My name is jao garcia. I have nothing else to say?", "session_id": "test-user-123"}' \
  -N
```

### Step 4: Check active sessions
```
curl http://localhost:8000/sessions
```
Should show all active session IDs.
### Step 5: Verify Database
Your incidents/feedback should be saved to the database. In the example from the third message, a feedback should be stored. You can check this in your database (Supabase)

| Phase 1         | Phase 2                    |
|-----------------|----------------------------|
| Echo server     | Real agents                |
| Fake streaming  | Actual LLM streaming       |
| No memory       | Session persistence        |
| No database     | Saves to Supabase / SQLite |

### Trouble Shoot: 
- if there are missing modules not found in openai agents, just remove the package you have and install then install them again.
```
uv remove openai-agents
uv add "openai-agents[sqlalchemy]"
```

#### Additional Notes:
- If server restarts, the session list will be empty
- Cannot pull conversations since there is no conversations database. 
- You can track conversations in OpenAI's platform
- You can add trace metadata in order to track sessions
- It is better to only use the group_id for identifying users, and session_id as metadata for every conversation.
- If server restarts, context will be empty. Additional testing for context overlapping is also needed. 



# Phase 3 Features Added:
### 1. Session Management Endpoints

- **POST** `/sessions/create` — Create a new session
- **GET** `/sessions/{session_id}` — Get session details
- **DELETE** `/sessions/{session_id}` — Delete a session
- **GET** `/sessions?user_id=xxx` — List all sessions (optionally filtered by user)

### 2. Anonymous User Support

- If `user_id` is not provided, generate `anonymous-{uuid}`
- Frontend stores this ID in `localStorage`
- All sessions from the same browser share the same `user_id`

### 3. Tracing with Metadata

- Each trace includes:
  - `session_id`
  - `user_id`
  - `group_id`
  - `message_count`
- `group_id` groups all sessions belonging to the same user
- View traces at: https://platform.openai.com/traces


## Testing of Phase 3 – Session & Conversation Validation

This document outlines the test cases for validating session creation, anonymous user handling, concurrent conversations, and session listing behavior in the backend.

---

### Test 1: Create Anonymous User Session

Create a session without providing a `user_id`.

#### Request

```bash
curl -X POST http://localhost:8000/sessions/create \
  -H "Content-Type: application/json" \
  -d '{}'
```

#### Expected Result

* The response includes a generated `user_id`
* Format: `anonymous-<uuid>`
* This `user_id` represents an anonymous user and can be reused by the frontend (e.g., stored in `localStorage`)

---

### Test 2: Create Logged-In User Session

Create a session for a known, logged-in user.

#### Request

```bash
curl -X POST http://localhost:8000/sessions/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "john-doe-123"}'
```

#### Expected Result

* The session is created and associated with `user_id = john-doe-123`
* The returned `session_id` is linked to this user
* Multiple sessions can exist for the same user

---

### Test 3: Two Concurrent Conversations

Validate that two users can have independent, simultaneous conversations.

---

#### Terminal 1: User Alice

##### Create Session

```bash
SESSION_1=$(curl -s -X POST http://localhost:8000/sessions/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice"}' | jq -r '.session_id')
```

##### Send Chat Message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hi I'm Alice\", \"session_id\": \"$SESSION_1\"}" \
  -N
```

```bash
SESSION_2=$(curl -s -X POST http://localhost:8000/sessions/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "alice"}' | jq -r '.session_id')
```

##### Send Chat Message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hi I'm still Alice\", \"session_id\": \"$SESSION_2\"}" \
  -N
```
---

#### Terminal 2: User Bob

##### Create Session

```bash
SESSION_2=$(curl -s -X POST http://localhost:8000/sessions/create \
  -H "Content-Type: application/json" \
  -d '{"user_id": "bob"}' | jq -r '.session_id')
```

#### Send Chat Message

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"Hi I'm Bob\", \"session_id\": \"$SESSION_2\"}" \
  -N
```

#### Expected Result

* Alice and Bob receive independent responses
* No message leakage between sessions
* Streaming responses (`-N`) work concurrently

---

### Test 4: View All Sessions for a User

Retrieve all sessions associated with a specific user.

#### Request

```bash
curl "http://localhost:8000/sessions?user_id=alice"
```

#### Expected Result

* Returns a list of all sessions associated with `user_id = alice`
* Sessions are grouped under the same user
* Confirms correct session-to-user mapping

---

## Summary

This test phase verifies:

* Anonymous and authenticated session creation
* Stable `user_id` → `session_id` relationships
* Safe concurrent conversations
* Accurate session listing per user

All tests passing indicates Phase 3 session management is functioning as expected.

