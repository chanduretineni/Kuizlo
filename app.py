import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles  
from main import router

app = FastAPI()

# Adding CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace "*" with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# # Mount the static files directory
# app.mount(
#     "/static",  # URL path prefix
#     StaticFiles(directory="/Users/retinenisaichandu/Documents/untitled folder/Kuizlo/results"),  # Directory path
#     name="static",
# )
# Including the router for APIs
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)
