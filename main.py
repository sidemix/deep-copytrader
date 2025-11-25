from app.web import app

if __name__ == "__main__":
    # This is for local development
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)