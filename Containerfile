# This project was developed with assistance from AI tools.

FROM registry.access.redhat.com/ubi9/python-311:latest

# Set labels for OpenShift and container metadata
LABEL name="mission-planner" \
      version="0.1.0" \
      summary="Cloud mission planning service for Unitree G1 humanoid robot" \
      description="Orchestrates Cosmos-Reason2 scene understanding and Nemotron mission planning for robotic navigation" \
      io.k8s.display-name="Mission Planner" \
      io.openshift.expose-services="8080:http"

# Switch to root to install dependencies, then back to default user
USER 0

COPY pyproject.toml .
COPY app/ app/
RUN pip install --no-cache-dir .

# Switch back to non-root user (UID 1001 is the default in UBI Python images)
USER 1001

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import httpx; httpx.get('http://localhost:8080/v1/health').raise_for_status()"]

ENTRYPOINT ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
