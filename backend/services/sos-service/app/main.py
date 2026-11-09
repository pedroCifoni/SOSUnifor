from fastapi import FastAPI
app = FastAPI(title = "SOS service" , version = "1.0.0")
@app.get("/health")
def heath_check():
    return {
        "service": "sos-service",
        "status" : "healthy"
    }