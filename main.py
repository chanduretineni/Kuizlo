from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import Optional, Any
from api.reference_files import springer_article_search
from api.generate_essay_api import generate_essay, humanize_essay, generate_essay_with_instructions
from models.request_models import QueryRequest, GenerateEssayRequest, GenerateEssayResponse, HumanizeEssay, HumanizeEssayResponse, QueryResponse, FineTuneModelResponse, FineTuneModelRequest, SignupRequest,TokenResponse, LoginRequest,QuestionsResponse,AnswersRequest,FinalResponse
from api.fine_tuned_models_api import fine_tune_request
from api.auth import signup, login
from services.essay_generation_with_instructions import create_essay_outline, generate_final_essay,process_uploaded_file,generate_questions_from_context
import json
import uuid
from pymongo import MongoClient
from models.request_models import SaveEssayRequest
from services.essay_storage_service import essay_storage_service
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import Optional, List, Dict
from pydantic import BaseModel
from openai import OpenAI
from bson import json_util
from datetime import datetime
import logging
from services.analyze_task import generate_final_content,generate_task_outline,generate_clarifying_questions,extract_text_from_file,generate_initial_output

# MongoDB Connection
mongo_client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
db = mongo_client["Kuizlo"]
essays_collection = db["essays"]
session_questions_collection = db["session_questions"] 
router = APIRouter()
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
sessions = {}

class QuestionAnswer(BaseModel):
    question_id: str
    answer: str

class ProcessFileResponse(BaseModel):
    session_id: str
    questions: List[Dict[str, Any]]
    initial_html: str
    output_path: str

class CreateOutlineRequest(BaseModel):
    session_id: str
    answers: List[QuestionAnswer]

class CreateOutlineResponse(BaseModel):
    outline: Dict[str, Any]

class CompleteTaskRequest(BaseModel):
    session_id: str
    modified_outline: Dict[str, Any]

class CompleteTaskResponse(BaseModel):
    content: str
    format: str



# Route for Springer article search
@router.post("/search/springer",response_model=QueryResponse)
async def search_springer(request: QueryRequest):
    return await springer_article_search(request)

# Route for Essay Generation
@router.post("/generate-essay", response_model=GenerateEssayResponse)
async def generate_essay_api(request: GenerateEssayRequest):
    return await generate_essay(request)

# Route for Essay Generation
@router.post("/humanize-essay", response_model=HumanizeEssayResponse)
def humanize_essay_api(request: HumanizeEssay):
    return humanize_essay(request)

# Route for Fine Tuned Models
@router.post("/fine-tuned-model", response_model=FineTuneModelResponse)
async def generate_fine_tune_model(request: FineTuneModelRequest):
    return await fine_tune_request(request)

# Route for Essay Generation
@router.post("/generate-essay-with-instructions", response_model=GenerateEssayResponse)
async def generate_essay_with_instructions_api(request: GenerateEssayRequest):
    return await generate_essay_with_instructions(request)

#Route for Signup
@router.post("/auth/signup")
async def signup_api(signup_request: SignupRequest):
    return await signup(signup_request)

#Route for Login
@router.post("/auth/login", response_model=TokenResponse)
async def login_api(form_data: LoginRequest):
        return await login(form_data)

@router.post("/submit-answers", response_model=FinalResponse)
async def submit_answers(answers_request: AnswersRequest):
    # Retrieve original context using session_id

    # Create outline
    outline = await create_essay_outline(
        answers_request
    )
    
    # Generate final essay
    essay = await generate_final_essay(
        outline, 
        answers_request.answers
    )
    
    return FinalResponse(
        essay=essay,
        outline=outline,
        references=["Reference 1", "Reference 2"]
    )

@router.post("/generate-questions", response_model=QuestionsResponse)
async def generate_questions(
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    try:
        # Validate input: at least one of `file` or `content` must be provided
        if not file and not content:
            raise ValueError("At least one of `file` or `content` must be provided.")
        
        # Process the file  
        file_content = ""
        if file:
            file_content = await process_uploaded_file(file)
        
        # Generate questions
        questions = await generate_questions_from_context(
            content,
            file_content
        )
        
        return questions
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in request_data")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.post("/save-essay")
async def save_essay(request: SaveEssayRequest):
    return await essay_storage_service.save_essay(request)

@router.get("/retrieve-essay")
async def retrieve_essay(email: str):
    return await essay_storage_service.get_essay(email)

# main.py updates (partial)
class ProcessFileResponse(BaseModel):
    session_id: str
    questions: List[Dict[str, Any]]
    initial_html: str
    output_path: str

@router.post("/process-file", response_model=ProcessFileResponse)
async def process_file(
    content: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    try:
        client = OpenAI()
        combined_content = ""
        
        if file:
            file_content = await extract_text_from_file(file)
            combined_content += file_content + "\n"
        if content:
            combined_content += content
        
        if not combined_content.strip():
            raise HTTPException(status_code=400, detail="No valid content provided")
        
        session_id = get_session_id()
        
        # Generate initial output and questions in parallel
        initial_html, output_path,tasks = await generate_initial_output(combined_content, client)
        questions = await generate_clarifying_questions(combined_content,tasks, client)
        
        # Save to MongoDB
        session_data = {
            "session_id": session_id,
            "tasks":tasks,
            "content": combined_content,
            "questions": questions,
            "initial_output": output_path,
            "created_at": datetime.utcnow()
        }
        session_questions_collection.insert_one(session_data)
        
        return ProcessFileResponse(
            session_id=session_id,
            questions=questions,
            initial_html=initial_html,
            output_path=output_path
        )
        
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        

@router.post("/create-outline", response_model=CreateOutlineResponse)
async def create_outline(request: CreateOutlineRequest):
    """Endpoint 2: Create outline from user answers"""
    try:
        client = OpenAI()
        # Retrieve session data
        session_data = session_questions_collection.find_one(
            {"session_id": request.session_id}
        )
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Generate outline
        outline = await generate_task_outline(
            content=session_data["content"],
            tasks=session_data["tasks"],
            answers=request.answers,
            client=client
        )
        
        # Update session data
        session_questions_collection.update_one(
            {"session_id": request.session_id},
            {"$set": {
                "answers": json.loads(json_util.dumps(request.answers)),
                "outline": outline
            }}
        )
        
        return CreateOutlineResponse(outline=outline)
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Outline error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/complete-task", response_model=CompleteTaskResponse)
async def complete_task(request: CompleteTaskRequest):
    """Endpoint 3: Generate final content from outline"""
    try:
        client = OpenAI()
        # Retrieve session data
        session_data = session_questions_collection.find_one(
            {"session_id": request.session_id}
        )
        if not session_data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Generate final content
        content = await generate_final_content(
            content=session_data["content"],
            tasks=session_data["tasks"],
            outline=request.modified_outline,
            client=client
        )
        
        # Save final result
        essays_collection.insert_one({
            "session_id": request.session_id,
            "content": content[6:],
            "generated_at": datetime.utcnow()
        })
        
        return CompleteTaskResponse(
            content=content,
            format="html"
        )
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Completion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
def get_session_id():
    """Generate unique session ID with collision check"""
    while True:
        session_id = str(uuid.uuid4())
        if not session_questions_collection.find_one({"session_id": session_id}):
            return session_id