from pydantic import BaseModel,Field
from typing import List, Optional, Dict,Any
from enum import Enum


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
    topic : str

class FineTuneModelResponse(BaseModel):
    essay_id : str
    model_output: str
    html_content: Optional[str] = None
    file_path : str

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


class FileType(str, Enum):
    PDF = "pdf"
    JPEG = "jpeg"
    PNG = "png"

class InitialRequest(BaseModel):
    instructions: str
    file_type: FileType
    additional_context: Optional[str] = None

class GeneratedQuestion(BaseModel):
    id: str
    question: str
    question_type: str  # "reference", "length", "topic_specific"
    options: Optional[List[str]] = None

class QuestionsResponse(BaseModel):
    questions: List[GeneratedQuestion]
    session_id : str

class Answer(BaseModel):
    question_id: str
    question: str
    question_type: str
    answer: str

class AnswersRequest(BaseModel):
    answers: List[Answer]
    session_id : str


class Subsection(BaseModel):
    title: str
    key_points: List[str]

class OutlineSection(BaseModel):
    title: str
    key_points: List[str]
    subsections: Optional[List[Subsection]] = None
    word_count: int

class EssayOutline(BaseModel):
    title: str
    target_audience: str
    writing_style: str
    reference_style: str
    total_word_count: int
    introduction: OutlineSection
    main_sections: List[OutlineSection]
    conclusion: OutlineSection
    references_section: Optional[OutlineSection] = None

class FinalResponse(BaseModel):
    essay: str
    outline: EssayOutline
    references: Optional[List[str]]

class SaveEssayRequest(BaseModel):
    email: str
    title: str
    word_count: int
    citation_style: str
    generated_essay: str
    entered_essay: Optional[str] = None


# Pydantic models for request/response
class TaskAnalysisResponse(BaseModel):
    task_type: str
    questions: List[Dict[str, str]]
    initial_outline: Optional[Dict[str, Any]]

class TaskCompletionRequest(BaseModel):
    session_id: str
    answers: list[Dict[str, str]]

class TaskCompletionResponse(BaseModel):
    content: str
    format: str


class AnswerResponse(BaseModel):
    answer: str
    pdf_path: str