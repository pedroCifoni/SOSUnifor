from fastapi import FastAPI


app = FastAPI(
    title="Notification Service",
    version="1.0.0"
)


@app.get("/health")
def health_check():
    return {
        "service": "notification-service",
        "status": "healthy"
    }