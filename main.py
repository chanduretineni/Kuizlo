from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import Optional
from api.reference_files import ieee_article_search
from api.reference_files import springer_article_search
from api.generate_essay_api import generate_essay, humanize_essay, generate_essay_with_instructions
from models.request_models import QueryRequest, GenerateEssayRequest, GenerateEssayResponse, HumanizeEssay, HumanizeEssayResponse, QueryResponse, FineTuneModelResponse, FineTuneModelRequest, SignupRequest,TokenResponse, LoginRequest,QuestionsResponse,AnswersRequest,FinalResponse, InitialRequest
from api.fine_tuned_models_api import fine_tune_request
from api.auth import signup, login
from services.essay_generation_with_instructions import create_essay_outline, generate_final_essay,process_uploaded_file,generate_questions_from_context
import json
router = APIRouter()

# Route for IEEE article search
@router.post("/search/ieee")
async def search_ieee(request: QueryRequest):
    return await ieee_article_search(request)

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