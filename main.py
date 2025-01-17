from fastapi import APIRouter, Depends
from api.reference_files import ieee_article_search
from api.reference_files import springer_article_search
from api.generate_essay_api import generate_essay, humanize_essay, generate_essay_with_instructions
from models.request_models import QueryRequest, GenerateEssayRequest, GenerateEssayResponse, HumanizeEssay, HumanizeEssayResponse, QueryResponse, FineTuneModelResponse, FineTuneModelRequest, SignupRequest,TokenResponse
from api.fine_tuned_models_api import fine_tune_request
from api.auth import signup, login
from fastapi.security import OAuth2PasswordRequestForm

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
async def login_api(form_data: OAuth2PasswordRequestForm = Depends()):
        return await login(form_data)