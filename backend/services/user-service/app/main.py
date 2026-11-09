from fastapi import FastAPI

app = FastAPI(
    title = "User service", version = "1.0.0"
)

@app.get("/health")
def health_check():
    return {
        "service": "user-service",
        "status" : "healthy"
    }