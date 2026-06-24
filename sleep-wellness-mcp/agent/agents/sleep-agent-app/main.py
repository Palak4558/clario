from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient
import os
import json
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

# -----------------------------------------------------------------------------
# 1. MCP SERVER CONNECTION
# -----------------------------------------------------------------------------
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:5000")

print("=" * 80)
print(f"Connecting to MCP Server at: {MCP_SERVER_URL}")
print("=" * 80)

try:
    toolbox = ToolboxSyncClient(MCP_SERVER_URL)
    mcp_tools = toolbox.load_toolset("sleep_wellness_toolset")
    print(f"Loaded {len(mcp_tools)} tools from MCP server")
    print("=" * 80)
except Exception as e:
    print(f"ERROR connecting to MCP server: {e}")
    mcp_tools = []

# -----------------------------------------------------------------------------
# 2. USER CONTEXT (dynamic from Flutter client, or default)
# -----------------------------------------------------------------------------
USER_ID = os.getenv("SLEEP_USER_ID", "guest_user")
print(f"Using user_id: {USER_ID}")


# -----------------------------------------------------------------------------
# 3. SAFE RESPONSE PARSER
# -----------------------------------------------------------------------------
def safe_parse_response(resp):
    """Always return a structured dict, even if response is string or list."""
    if isinstance(resp, dict):
        return resp
    if isinstance(resp, list):
        return {"data": resp}
    if isinstance(resp, str):
        try:
            return json.loads(resp)
        except json.JSONDecodeError:
            return {"text_response": resp}
    return {"unknown_response": str(resp)}


# -----------------------------------------------------------------------------
# 4. AGENT CONFIGURATION
# -----------------------------------------------------------------------------
root_agent = Agent(
    name="sleep_wellness_coach",
    model="gemini-2.5-flash",
    description="Sleep wellness AI with PostgreSQL database access via MCP",
    instruction=f"""
You are a Sleep Wellness Coach with DIRECT database access via MCP tools.

When analyzing sleep:
- Always call analyze_sleep_trends(user_id="{USER_ID}")
- Then parse it with safe_parse_response()

Response must follow this clean JSON style:

{{
  "average_sleep_hours": <float>,
  "average_stress": <int>,
  "nightmares": <int>,
  "total_nights": <int>,
  "message": "Based on your database records for {USER_ID}, here is your sleep summary."
}}

If fields are missing, set their values to null.

Always respond with structured JSON (not plain text).
""",
    tools=mcp_tools,
)

print("=" * 80)
print(f"Agent '{root_agent.name}' initialized successfully")
print(f"Loaded {len(mcp_tools)} MCP tools")
print("=" * 80)


# -----------------------------------------------------------------------------
# 5. HTTP API (consumed by the Flutter app)
# -----------------------------------------------------------------------------
@app.post("/apps/sleep-agent-app/users/{user_id}/messages")
async def handle_message(user_id: str, request: Request):
    data = await request.json()
    message = data.get("message", "")
    print(f"Message from client for user {user_id}: {message}")

    try:
        raw_result = root_agent.run(message)
        parsed_result = safe_parse_response(raw_result)
        return parsed_result
    except Exception as e:
        return {"error": str(e)}


@app.get("/")
async def root():
    return {"message": "Sleep Agent API is running"}


if __name__ == "__main__":
    print("Testing analyze_sleep_trends tool call...")
    try:
        raw_result = root_agent.run(f"Analyze sleep trends for {USER_ID}")
        parsed_result = safe_parse_response(raw_result)
        print("Final Parsed Result:")
        print(json.dumps(parsed_result, indent=2))
    except Exception as e:
        print(f"Error during test call: {e}")

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
