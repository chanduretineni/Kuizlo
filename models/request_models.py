from pydantic import BaseModel,Field
from typing import List, Optional

class QueryRequest(BaseModel):
    title: str

# Updated Response Model
class ReferenceObject(BaseModel):
    AuthorName: str
    TitleName: str
    Year : str
    Publisher : str
    Abstract : str

class QueryResponse(BaseModel):
    references: List[ReferenceObject]


class Reference(BaseModel):
    id: str
    title: str
    author: str
    year: int

class EssayReferenceObject(BaseModel):
    AuthorName: str
    TitleName: str
    Year : str
    Publisher : str

class GenerateEssayRequest(BaseModel):
    topic: str
    selected_references: List[EssayReferenceObject]
    citationStyle: str
    wordCount: int

class GenerateEssayResponse(BaseModel):
    essay: str

class HumanizeEssay(BaseModel):
    essay_txt : str

class HumanizeEssayResponse(BaseModel):
    humanized_essay : str

class FineTuneModelRequest(BaseModel):
    prompt_text : str

class FineTuneModelResponse(BaseModel):
    model_output : str

class SignupRequest(BaseModel):
    name: str 
    email: str 
    password: str = None  # Optional for Google/Apple signups
    provider: str  # 'email', 'google', or 'apple'

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class LoginRequest(BaseModel):
    email : str
    password : str = None
    provider : str