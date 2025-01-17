from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from models.request_models import SignupRequest, TokenResponse
import requests
import google.auth.transport.requests
from google.oauth2.id_token import verify_oauth2_token
from db.mongo_db import db
from config import GOOGLE_CLIENT_ID
from fastapi.responses import JSONResponse

# Configuration
SECRET_KEY = "1M16ZIr5lUwiNVdNgJOhJNFws5B1xIXn"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
USER_DATA_COLLECTION = db["user_data"]

# Helper Functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_google_token(token: str):
    try:
        payload = verify_oauth2_token(token, google.auth.transport.requests.Request(), GOOGLE_CLIENT_ID)
        return payload
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid Google token")

def verify_apple_token(token: str):
    response = requests.post("https://appleid.apple.com/auth/token", data={"token": token})
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Invalid Apple token")
    return response.json()

async def signup_process(signup_request: SignupRequest):
    if signup_request.email:
        existing_user = USER_DATA_COLLECTION.find_one({"email": signup_request.email})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")

    if signup_request.provider == "email":
        if not signup_request.password:
            raise HTTPException(status_code=400, detail="Password is required for email signup")
        password_hash = hash_password(signup_request.password)
        user_data = {
            "name": signup_request.name,
            "email": signup_request.email,
            "password_hash": password_hash,
            "auth_provider": "email",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "roles": ["user"]
        }
    elif signup_request.provider == "google":
        payload = verify_google_token(signup_request.token)
        user_data = {
            "name": payload.get("name"),
            "email": payload["email"],
            "auth_provider": "google",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "roles": ["user"]
        }
    elif signup_request.provider == "apple":
        payload = verify_apple_token(signup_request.token)
        user_data = {
            "name": signup_request.name,
            "email": payload["email"],
            "auth_provider": "apple",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "roles": ["user"]
        }
    else:
        raise HTTPException(status_code=400, detail="Invalid provider")

    USER_DATA_COLLECTION.insert_one(user_data)
    # Generate JWT token for email provider
    if signup_request.provider == "email":
        access_token = create_access_token(data={"sub": signup_request.email})
        response = JSONResponse(content={
            "message": "Signup successful",
            "user": {
                "email": user_data["email"],
                "name": user_data["name"],
                "roles": user_data["roles"]
            }
        })
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,  
            secure=False,  
            samesite="Strict"
        )
    return {"message": "User registered successfully"}

async def login_process(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    # Check for Google token in cookies
    google_token = request.cookies.get("google_token") 

    if google_token:
        try:
            payload = verify_google_token(google_token)
            user = USER_DATA_COLLECTION.find_one({"email": payload["email"]})
            if user:
                # If user exists in database, return success
                return {
                    "message": "Google login successful",
                    "user": {
                        "email": user["email"],
                        "name": user["name"],
                        "roles": user["roles"]
                    }
                }
            else:
                # If user doesn't exist, handle accordingly (e.g., redirect to signup)
                raise HTTPException(status_code=404, detail="User not found") 

        except Exception as e:
            # Handle Google token verification errors
            raise HTTPException(status_code=401, detail="Invalid Google token")

    # Check if access_token cookie exists
    access_token = request.cookies.get("access_token")

    if access_token:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            email = payload.get("sub")
            user = USER_DATA_COLLECTION.find_one({"email": email})
            if user:
                return {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": {
                        "email": user["email"],
                        "name": user["name"],
                        "roles": user["roles"]
                    }
                }
            else:
                # Access token is invalid, so remove the cookie
                response = JSONResponse(content={"message": "Invalid access token"})
                response.delete_cookie(key="access_token")
                return response
        except JWTError:
            # Access token is invalid, so remove the cookie
            response = JSONResponse(content={"message": "Invalid access token"})
            response.delete_cookie(key="access_token")
            return response

    # If access_token is not valid, check email and password
    email = form_data.username
    password = form_data.password

    if email and password:
        user = USER_DATA_COLLECTION.find_one({"email": email})
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        if user["auth_provider"] != "email":
            raise HTTPException(status_code=401, detail=f"Use {user['auth_provider']} to sign in")

        if not verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        access_token = create_access_token(data={"sub": email})
        response = JSONResponse({
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "email": user["email"],
                "name": user["name"],
                "roles": user["roles"]
            }
        })
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=False,
            samesite="Strict"
        )
        return response

    # If neither access_token nor email and password is present, raise an error
    raise HTTPException(status_code=400, detail="Missing login credentials")