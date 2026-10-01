from fastapi import FastAPI

# 1. Initialize the FastAPI application instance
# This 'app' object represents the core of our backend web server.
app = FastAPI(
    title="VIDYORA AI API",
    description="Backend services for VIDYORA AI - AI-powered adaptive video learning platform",
    version="0.1.0",
)


# 2. Root Endpoint (GET /)
# Handles requests sent to the base URL (e.g. http://127.0.0.1:8000/)
@app.get("/")
def read_root():
    """Welcome endpoint providing basic API metadata."""
    return {
        "message": "Welcome to VIDYORA AI API",
        "status": "online",
        "docs_url": "/docs",
    }


# 3. Health Check Endpoint (GET /health)
# Used by deployment platforms (Render, Docker, Kubernetes) and monitoring tools
# to verify that the server is alive, responsive, and ready to handle traffic.
@app.get("/health")
def health_check():
    """Health check endpoint to verify backend operational status."""
    return {
        "status": "healthy",
        "service": "VIDYORA AI Backend",
        "version": "0.1.0",
    }
