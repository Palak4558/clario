# Sleep Wellness (MCP)

Sleep tracking + AI coaching feature. Nightly sleep data lives in Cloud SQL
(Postgres); an ADK agent talks to that data through a custom **MCP (Model
Context Protocol)** toolset rather than querying the database directly, and
push notifications are sent for sleep interventions/recommendations via FCM.

## Components

```
sleep-wellness-mcp/
├── functions/
│   ├── analyze_sleep/            # HTTP Cloud Function: pulls 7 days of sleep
│   │                              data from Postgres, asks Gemini to summarize
│   │                              patterns and give a recommendation
│   └── send_sleep_notification/  # HTTP Cloud Function: sends an FCM push
│                                  notification for a given intervention and
│                                  logs it to Firestore for in-app display
└── agent/
    ├── agents/sleep-agent-app/main.py   # ADK agent + FastAPI app. Loads the
    │                                     "sleep_wellness_toolset" from an MCP
    │                                     server and exposes a chat endpoint
    │                                     for the Flutter client
    ├── tools/sleep_notification_tool.py # Thin wrapper the agent can use to
    │                                     call send_sleep_notification
    └── Dockerfile                       # Container for the agent app (adk web)
```

> **Note:** the MCP server itself (the thing that exposes
> `sleep_wellness_toolset`, e.g. via `toolbox` config pointed at the
> `sleep_data` Postgres table) isn't included here — only the client side
> (the ADK agent that loads and calls that toolset). If you still have the
> MCP server / toolbox config from the original project, add it under
> `agent/mcp-server/` to make this fully runnable end-to-end.

## Data flow

1. The Flutter app posts a chat message to
   `POST /apps/sleep-agent-app/users/{user_id}/messages` on the agent app.
2. The agent (Gemini 2.5 Flash via ADK) calls the `analyze_sleep_trends` MCP
   tool for that user, which reads from the `sleep_data` Postgres table.
3. Separately, `analyze_sleep` (Cloud Function) can be called directly to
   get a structured 7-day report (`average_duration`, `average_stress`,
   `consistency_score`, `summary`, `recommendation`) without going through
   the agent/MCP path.
4. When an intervention is decided on, `send_sleep_notification` sends an
   FCM push to the user's registered device token and logs the notification
   to `users/{userId}/notifications` in Firestore.

## Environment variables

| Variable | Used by | Notes |
|---|---|---|
| `PROJECT_ID` | `analyze_sleep` | GCP project for Vertex AI |
| `LOCATION` | `analyze_sleep` | Vertex AI region |
| `MODEL` | `analyze_sleep` | Defaults to `gemini-2.5-flash` |
| `PGUSER`, `PGPASSWORD`, `PGHOST`, `PGDATABASE` | `analyze_sleep` | Cloud SQL Postgres credentials — **set via Secret Manager, never commit these** |
| `MCP_SERVER_URL` | agent app | URL of the MCP toolbox server exposing `sleep_wellness_toolset` |
| `SLEEP_USER_ID` | agent app | Default user id if not supplied per-request |
| `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI` | agent app | ADK/Vertex AI config |

A `.env.example` is included in each function folder you deploy from — copy
it to `.env` locally and fill in real values (and keep `.env` out of git;
it's already in the root `.gitignore`).

## Deploying the Cloud Functions

```bash
# analyze_sleep
gcloud functions deploy analyze-sleep-ai \
  --runtime python311 --trigger-http --allow-unauthenticated \
  --entry-point analyze_sleep --region us-central1 \
  --source functions/analyze_sleep \
  --set-env-vars PROJECT_ID=your-project,LOCATION=us-central1 \
  --set-secrets PGUSER=PGUSER:latest,PGPASSWORD=PGPASSWORD:latest,PGHOST=PGHOST:latest

# send_sleep_notification
gcloud functions deploy send-sleep-notification \
  --runtime python311 --trigger-http --allow-unauthenticated \
  --entry-point send_sleep_notification --region us-central1 \
  --source functions/send_sleep_notification
```

## Running the agent app

```bash
cd agent
docker build -t sleep-agent-app .
docker run -p 8000:8000 \
  -e MCP_SERVER_URL=https://your-mcp-server \
  -e GOOGLE_CLOUD_PROJECT=your-project \
  sleep-agent-app
```

The Cloud Run/Functions service accounts here need: `roles/cloudsql.client`
(Postgres), `roles/aiplatform.user` (Vertex AI/Gemini), and
`roles/firebasemessaging.admin` + `roles/datastore.user` for the
notification function.
