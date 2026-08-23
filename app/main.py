from fastapi import FastAPI

app = FastAPI(
    title="FlyRank Billing Engine",
    description="Usage Metering & Billing Engine Capstone",
    version="1.0.0"
)

@app.get("/health")
def health_check():
    """Health check endpoint to verify the API is running."""
    return {"status": "ok", "message": "Billing engine is running"}