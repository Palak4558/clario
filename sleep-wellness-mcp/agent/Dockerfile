FROM python:3.11-slim
WORKDIR /app

# Create a non-root user
RUN adduser --disabled-password --gecos "" myuser
USER myuser

ENV PATH="/home/myuser/.local/bin:$PATH"
ENV GOOGLE_GENAI_USE_VERTEXAI=1
ENV GOOGLE_CLOUD_PROJECT=your-gcp-project-id
ENV GOOGLE_CLOUD_LOCATION=us-central1

# Install ADK
RUN pip install google-adk==1.17.0

# Copy agent
COPY --chown=myuser:myuser "agents/sleep-agent-app/" "/app/agents/sleep-agent-app/"

# Install agent dependencies
RUN pip install -r "/app/agents/sleep-agent-app/requirements.txt"

EXPOSE 8000

CMD adk web --port=8000 --host=0.0.0.0 "/app/agents"
