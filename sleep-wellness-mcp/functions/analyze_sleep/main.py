import os
import json
import psycopg2
from psycopg2 import pool
from datetime import datetime, timedelta, timezone
from flask import jsonify
from google import genai

# ---------- CONFIG ----------
PROJECT_ID = os.environ.get("PROJECT_ID", "your-gcp-project-id")
LOCATION = os.environ.get("LOCATION", "us-central1")
MODEL = os.environ.get("MODEL", "gemini-2.5-flash")

# Cloud SQL connection details — set these via env vars / Secret Manager.
# Do NOT hardcode real credentials here.
DB_USER = os.environ.get("PGUSER")
DB_PASS = os.environ.get("PGPASSWORD")
DB_NAME = os.environ.get("PGDATABASE", "postgres")
DB_HOST = os.environ.get("PGHOST")

# ---------- Initialize AI Client ----------
client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

# ---------- Connection Pool ----------
connection_pool = None
try:
    if DB_USER and DB_PASS and DB_HOST:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            1, 10,
            user=DB_USER,
            password=DB_PASS,
            host=DB_HOST,
            database=DB_NAME
        )
        print("✅ PostgreSQL pool created successfully")
    else:
        print("⚠️ PGUSER/PGPASSWORD/PGHOST not set — connection pool not created.")
except Exception as e:
    print("❌ Error creating PostgreSQL pool:", e)
    connection_pool = None


# ---------- FETCH & ANALYZE ----------
def fetch_sleep_data(user_id):
    """Fetch last 7 days of sleep data for the given user."""
    if connection_pool is None:
        raise RuntimeError("Database connection pool is not configured.")

    conn = connection_pool.getconn()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT sleep_date, bedtime, wake_time, sleep_duration_hours, sleep_quality, stress_level, nightmares
            FROM sleep_data
            WHERE user_id = %s AND sleep_date >= %s
            ORDER BY sleep_date DESC
        """, (user_id, (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()))
        rows = cursor.fetchall()
    finally:
        cursor.close()
        connection_pool.putconn(conn)

    data = []
    for r in rows:
        data.append({
            "sleep_date": r[0],
            "bedtime": r[1],
            "wake_time": r[2],
            "sleep_duration": r[3],
            "sleep_quality": r[4],
            "stress_level": r[5],
            "nightmares": r[6],
        })
    return data


def analyze_with_gemini(data):
    """Ask Gemini to summarize the week's sleep data and suggest improvements."""
    prompt = f"""
You are a sleep and wellness AI coach. Here is a user's sleep data for the last 7 days:
{json.dumps(data, indent=2, default=str)}

Analyze this data and return ONLY a JSON with:
{{
  "average_duration": "<hours>",
  "average_stress": "<0-10>",
  "consistency_score": "<0-100>",
  "summary": "<1-2 sentences about pattern>",
  "recommendation": "<specific personalized advice to improve sleep>"
}}
"""
    resp = client.models.generate_content(model=MODEL, contents=prompt)
    try:
        text = resp.candidates[0].content.parts[0].text.strip()
        start = text.index("{")
        end = text.rindex("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {
            "average_duration": "N/A",
            "average_stress": "N/A",
            "consistency_score": 50,
            "summary": "Unable to parse AI output",
            "recommendation": "Try maintaining a fixed sleep schedule and reduce screen time before bed."
        }


# ---------- MAIN CLOUD FUNCTION ----------
def analyze_sleep(request):
    """Entry point for Cloud Function (HTTP-triggered)."""
    try:
        body = request.get_json(force=True)
        user_id = body.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400

        sleep_data = fetch_sleep_data(user_id)
        if not sleep_data:
            return jsonify({"message": "No sleep data found for past 7 days"}), 200

        ai_report = analyze_with_gemini(sleep_data)
        return jsonify({
            "user_id": user_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "report": ai_report
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
