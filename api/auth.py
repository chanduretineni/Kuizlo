from fastapi import HTTPException, Depends
from models.request_models import SignupRequest,LoginRequest
from services.authentication import signup_process,login_process

async def signup(signup_request: SignupRequest):
    try:
        return await signup_process(signup_request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def login(form_data : LoginRequest):
    try:
        return await login_process(form_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
