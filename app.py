import uvicorn
from fastapi import FastAPI
from main import router  # Importing the router from main.py

app = FastAPI()

# Including the router for APIs
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
