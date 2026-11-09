from fastapi import FastAPI


app = FastAPI(
    title="Location Service",
    version="1.0.0"
)


@app.get("/health")
def health_check():
    return {
        "service": "location-service",
        "status": "healthy"
    }