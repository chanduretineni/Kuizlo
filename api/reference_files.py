from services.reference_files import fetch_ieee_articles
from models.request_models import QueryRequest
from services.reference_files import fetch_springer_articles
from models.request_models import QueryRequest

async def ieee_article_search(request: QueryRequest):
    query = request.title
    response = await fetch_ieee_articles(query)
    return {"source": "IEEE", "data": response}


async def springer_article_search(request: QueryRequest):
    query = request.title
    response = await fetch_springer_articles(query)
    return response
