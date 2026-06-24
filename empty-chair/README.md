# Empty Chair

An AI-facilitated take on the Gestalt "Empty Chair" technique: a structured
dialogue where the user voices their thoughts to an imagined person or
feeling sitting across from them ("RED Chair"), then switches seats and
responds from that perspective ("BLUE Chair" being the user's own seat). A
Gemini-powered facilitator guides the session with short, open-ended prompts
rather than advice or analysis — its job is to keep the dialogue moving, not
to interpret it for the user.

## Session flow

1. **`startSession`** — creates a new session in Firestore (`sessionPhase: initial_analysis`)
   and returns an opening AI message asking the user to describe what's
   coming up for them.
2. **`analyzeInitialProblem`** — the pre-analysis loop. The facilitator asks
   brief clarifying questions until the user explicitly asks for an analysis
   (keywords like "analyze", "what's really going on", etc.) or the
   conversation hits a length threshold. At that point it produces a short
   **Analysis Statement / Root Emotion / Cause of Emotion**, saves it to the
   session, and flips `sessionPhase` to `empty_chair_ready`.
3. **`startEmptyChairSession`** *(optional)* — a lightweight endpoint a
   client can call to explicitly mark a session ready, if it wants to skip
   the analysis step.
4. **`processMessage`** — handles each turn of the actual Empty Chair
   dialogue once `sessionPhase == empty_chair_ready`. It:
   - Embeds the user's message (`text-embedding-004`) and runs a semantic
     search (cosine similarity) over past sessions with the *same*
     `personInChair`, pulling in the 2 most relevant past summaries as
     long-term memory context for Gemini.
   - Tracks how many consecutive turns have been in one chair and nudges
     the user to switch perspectives if they've stayed in one seat for 3+
     turns.
   - Generates the next facilitator prompt (always a question/prompt, never
     advice or a direct answer) and saves both messages to Firestore.
   - Is self-initializing: if no `sessionId` is supplied or the one given
     doesn't exist, it transparently creates a new session straight into
     `empty_chair_ready`, so a client can call this endpoint directly
     without orchestrating the earlier steps.
5. **`generateSessionSummaries`** — run once a session ends. Summarizes the
   Blue Chair statements, the Red Chair statements, and an overall
   facilitator reflection, embeds each, and stores them on the session
   document — this is what `processMessage` searches over for long-term
   memory in future sessions about the same person/issue.

## Firestore data model

```
users/{userId}/sessions/{sessionId}
  personInChair, userGoal, startTime, endTime, sessionPhase
  preAnalysisRootEmotion, preAnalysisCauseOfEmotion, preAnalysisStatement
  blueSummary, blueSummaryEmbedding
  redSummary, redSummaryEmbedding
  overallSessionReflection, reflectionEmbedding

users/{userId}/sessions/{sessionId}/messages/{messageId}
  text, role (user|ai), perspective (blue|red|facilitator)
  phase (initial_analysis|empty_chair_ready), timestamp
```

## Environment variables

| Variable | Default | Notes |
|---|---|---|
| `PROJECT_ID` | `your-gcp-project-id` | GCP project running Firestore + Vertex AI |
| `LOCATION` | `us-central1` | Vertex AI region |
| `GEMINI_MODEL_NAME` | `gemini-2.5-flash` | |
| `EMBEDDING_MODEL_NAME` | `text-embedding-004` | |

Set real values via `gcloud functions deploy --set-env-vars` or Secret
Manager — don't hardcode them.

## Deploying

Each function in `main.py` is deployed as its own Cloud Function (2nd gen),
all pointing at the same source:

```bash
gcloud functions deploy startSession \
  --runtime python311 --trigger-http --allow-unauthenticated \
  --entry-point startSession --region us-central1 \
  --set-env-vars PROJECT_ID=your-project,LOCATION=us-central1

# repeat for: analyzeInitialProblem, startEmptyChairSession,
# processMessage, generateSessionSummaries
```

The Cloud Functions service account needs `roles/datastore.user` (Firestore)
and `roles/aiplatform.user` (Vertex AI) at minimum.
