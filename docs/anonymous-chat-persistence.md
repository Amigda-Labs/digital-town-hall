# Guidelines for Persisting data for anonymous users

## Networking Introduction

Before diving into implementation, we have to consider how to manage our **threads** in order for things not to overlap. If multiple devices are pointing to the same **thread pool**, different users' conversation histories might bleed into one another.

At the networking level, the server already knows where to send responses back to — using the requester's **IP + Port** as a return address:

```
User A: 192.168.1.1:51234 → request → server responds to 192.168.1.1:51234
User B: 192.168.1.1:57823 → request → server responds to 192.168.1.1:57823
```

Like a mailing address on an envelope — the post office doesn't need to know your name, just where to send the reply. So responding to the right person is never the problem.

However, that port is **ephemeral**. The OS assigns it from a pool when the request starts, and releases it back to the pool once the request is done. The next click gets a completely different port — the server has no way to link the two:

```
Click 1: 192.168.1.1:51234 → request → response → port released
Click 2: 192.168.1.1:58901 → request → response → port released
                      ↑ different port, looks brand new to the server
```

It's like calling a taxi company, getting a ride, hanging up — then calling again. They have no idea it's the same person unless you give your name.

This is the problem **`device_id`** solves. A persistent identifier stored on the client that survives across requests, so the server can recognize the same device and filter the right threads for them.

- **Source IP + Port** → tells the server these are two separate connections (networking layer)
- **asyncio** → the engine that juggles multiple connections concurrently (concurrency layer)
- **Uvicorn** → translates incoming network connections into something asyncio/FastAPI can work with (the middleman/bridge)
- **FastAPI** → your business logic, routing, what actually happens per request (application layer)


### Summary

Use a **device-based identifier** to scope chat threads per browser/device. The frontend generates a persistent `device_id` stored in `localStorage` and sends it in the `X-Device-ID` header on every request. The backend stores and filters threads using this ID so each device only sees its own conversation history.

## Guidelines for backend

### Goal
- Use the `X-Device-ID` header sent by the frontend to scope chat threads to a specific device, so each device only sees its own conversation history.

### Step 1: Read the device ID from the request header
- In your ChatKit endpoint, extract `X-Device-ID` from the incoming request headers.
- Pass it into `chatkit_server.process()` via the `context` dict under the key `"device_id"`.
- If the header is absent or empty, pass `None` — treat it as an anonymous/unscoped request.

```python
device_id = request.headers.get("X-Device-ID")
result = await chatkit_server.process(await request.body(), context={"device_id": device_id})
```

### Step 2: Add a `device_id` column to the threads table
- Add an optional, indexed `device_id` column (`VARCHAR(255)`, nullable) to `ChatKitThreadModel`.
- Index the column so filtering threads by device is efficient.

```python
device_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
```

### Step 3: Migrate existing databases
- After `Base.metadata.create_all`, run a migration to add the column to databases that predate this change.
- For **PostgreSQL**, use `ADD COLUMN IF NOT EXISTS` (idempotent).
- For **SQLite**, check `PRAGMA table_info` first and only run `ALTER TABLE` if the column is missing (SQLite does not support `IF NOT EXISTS`).

### Step 4: Store the device ID when saving a thread
- When persisting a new `ChatKitThreadModel` row, read `device_id` from the context and store it on the model.
- Existing threads without a device ID retain `NULL`.

```python
device_id=context.get("device_id")
```

### Step 5: Filter threads by device ID when listing
- In the `list_threads` / `get_threads` query, read `device_id` from the context.
- If a non-empty `device_id` is present, add a `WHERE device_id = :device_id` clause so the response only includes threads belonging to that device.
- If `device_id` is `None` or empty, return all threads (or apply whatever default scoping policy you need).

```python
device_id = context.get("device_id")
if device_id:
    stmt = stmt.where(ChatKitThreadModel.device_id == device_id)
```

### Important considerations
- `device_id` is an untrusted, client-supplied value — it provides isolation, not authentication. Never use it to gate access to sensitive operations.
- Threads created before this feature was introduced will have `device_id = NULL`. Decide explicitly how to handle them (e.g., exclude from all device-scoped queries, or expose only to authenticated admin views).
- If you later add user authentication, you can join `device_id` with a user account to migrate anonymous threads to a real user.



## Guidelines for frontend

### Guidelines: Attaching a Device ID to Support Multiple Devices in Your Frontend

### Goal
- Assign each browser/device a unique, persistent identifier so the backend can distinguish between devices making requests to the ChatKit API.

### Step 1: Create a device ID generator
- Define a helper function that checks `localStorage` for an existing device ID under the key `chatkit:device-id`.
- If no ID exists, generate one using `crypto.randomUUID()` (available in secure/HTTPS contexts).
- Include a fallback generator (e.g., `Math.random().toString(36) + Date.now().toString(36)`) for environments where `crypto.randomUUID` is not available.
- Store the newly generated ID in `localStorage` so it persists across sessions and page reloads.

### Step 2: Initialize the device ID on component mount
- Use a `useRef` to hold the device ID value without triggering re-renders.
- Use a `useEffect` (runs once on mount) to call the generator and assign the result to the ref.
- This ensures `localStorage` is only accessed on the client side, avoiding SSR errors.

### Step 3: Attach the device ID to every ChatKit API request
- ChatKit's `CustomApiConfig` does not support a `headers` property directly.
- Use the `fetch` override property on the API config instead.
- Wrap the native `fetch`, spreading the existing `init` options and merging your custom header into `init.headers`.
- The header name to use is `X-Device-ID` with the value from the ref.

### Important considerations
- `X-Device-ID` identifies a device/browser, not an authenticated user. One user on two browsers produces two different IDs. Two users on the same browser share one ID.
- If the user clears browser storage, a new device ID will be generated on the next visit.
- On the very first render, there is a brief window before `useEffect` runs where the ref value is an empty string. The backend should treat an empty or missing `X-Device-ID` header as an anonymous request.
- Always check for `crypto.randomUUID` availability before calling it. Not all environments support it (e.g., HTTP without TLS, older browsers, some webviews).

## Why is there no secret key?
A secret key was considered, but it would need to be stored either in memory or local storage. Memory storage would lose the key on page refresh, while local storage offers no added security since it’s the same place the device ID is stored.

Since the threads only contain non-sensitive town questions, exposing a device ID does not risk sensitive data.