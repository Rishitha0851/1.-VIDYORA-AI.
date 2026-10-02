from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 1. Initialize the FastAPI application instance
app = FastAPI(
    title="VIDYORA AI API",
    description="Backend services for VIDYORA AI - AI-powered adaptive video learning platform",
    version="0.1.0",
)

# 2. Configure CORS (Cross-Origin Resource Sharing)
# The React development server runs at http://localhost:5173.
# By default, web browsers block web pages from making HTTP requests
# to a different origin (domain/port) for security.
# Here we explicitly whitelist our local frontend origin.
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # Only allow requests from our frontend
    allow_credentials=True,      # Allow cookies / authentication headers if needed later
    allow_methods=["*"],         # Allow all standard HTTP methods (GET, POST, etc.)
    allow_headers=["*"],         # Allow all standard request headers (Content-Type, etc.)
)


# 3. Root Endpoint (GET /)
@app.get("/")
def read_root():
    """Welcome endpoint providing basic API metadata."""
    return {
        "message": "Welcome to VIDYORA AI API",
        "status": "online",
        "docs_url": "/docs",
    }


# 4. Health Check Endpoint (GET /health)
@app.get("/health")
def health_check():
    """Health check endpoint to verify backend operational status."""
    return {
        "status": "healthy",
        "service": "VIDYORA AI Backend",
        "version": "0.1.0",
    }
