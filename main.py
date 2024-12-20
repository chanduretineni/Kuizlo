from fastapi import APIRouter
from api.reference_files import ieee_article_search
from api.reference_files import springer_article_search
from api.generate_essay_api import generate_essay, humanize_essay
from models.request_models import QueryRequest, GenerateEssayRequest, GenerateEssayResponse, HumanizeEssay, HumanizeEssayResponse

router = APIRouter()

# Route for IEEE article search
@router.post("/search/ieee")
async def search_ieee(request: QueryRequest):
    return await ieee_article_search(request)

# Route for Springer article search
@router.post("/search/springer")
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
