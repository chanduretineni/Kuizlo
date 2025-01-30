
from models.request_models import QueryRequest
from services.reference_files import fetch_all_articles
from models.request_models import QueryRequest


async def springer_article_search(request: QueryRequest):
    query = request.title
    response = await fetch_all_articles(query)
    return response
