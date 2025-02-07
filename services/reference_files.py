import httpx
import asyncio
from urllib.parse import quote
from datetime import datetime
import os
from fastapi import HTTPException
from models.request_models import QueryResponse, ReferenceObject
from config import OUTPUT_DIR,SPRINGER_API_KEY
from pymongo import MongoClient

API_TIMEOUT = 20
MAX_CONCURRENT = 5  # Reduced for rate limiting
SPRINGER_API_URL = "http://api.springernature.com/metadata/json"

mongo_client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
db = mongo_client["Kuizlo"]
essays_collection = db["essays"]
session_questions_collection = db["session_questions"]


async def fetch_with_retry(client, url, headers=None, retries=2):
    """Handle rate limits with exponential backoff"""
    for attempt in range(retries):
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait = 2 ** attempt
                print(f"Rate limited, retrying in {wait} seconds...")
                await asyncio.sleep(wait)
                continue
            raise
    return None

async def fetch_crossref_articles(query: str, limit=15):
    """Fetch English articles from Crossref with language filter"""
    base_url = f"https://api.crossref.org/works?query={quote(query)}&filter=has-abstract:true,language:en&sort=published&order=desc&mailto=retinanisaichandu@email.com"
    results = []
    page = 0
    batch_size = min(limit * 2, 100)  # Get extra to account for filtering
    
    while len(results) < limit * 2 and page < 3:  # Max 3 pages
        url = f"{base_url}&rows={batch_size}&offset={page * batch_size}"
        try:
            async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
                response = await fetch_with_retry(client, url)
                if response:
                    items = response.json().get("message", {}).get("items", [])
                    for item in items:
                        try:
                            authors = "; ".join(
                                f"{a.get('given', '')} {a.get('family', '')}".strip()
                                for a in item.get("author", [])
                            )
                            year = item.get("published", {}).get("date-parts", [[None]])[0][0]
                            entry = {
                                "doi": item.get("DOI"),
                                "Title": item.get("title", [""])[0],
                                "Authors": authors or "N/A",
                                "Year": str(year) if year else "N/A",
                                "Publisher": item.get("publisher", "N/A"),
                                "Abstract": item.get("abstract", "N/A"),
                                "Source": "Crossref",
                                "Language": item.get("language", "en")
                            }
                            if all(entry.values()) and entry["Language"] == "en":
                                results.append(entry)
                        except Exception as e:
                            continue
                    page += 1
        except Exception as e:
            print(f"Crossref error: {str(e)[:200]}")
            break
    
    return sorted(results, key=lambda x: -int(x["Year"]) if x["Year"].isdigit() else 0)[:limit*2]

async def fetch_openalex_articles(query: str, limit=15):
    """Fetch English articles from OpenAlex"""
    url = f"https://api.openalex.org/works?search={quote(query)}&filter=language:eng&per_page={limit * 2}&sort=publication_date:desc"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await fetch_with_retry(client, url, headers={"User-Agent": "ResearchApp/1.0 (mailto:retinanisaichandu@email.com)"})
            if response:
                items = response.json().get("results", [])
                return [process_openalex_item(item) for item in items]
    except Exception as e:
        print(f"OpenAlex error: {str(e)[:200]}")
    return []

def process_openalex_item(item):
    """Process OpenAlex items with validation"""
    try:
        abstract = "N/A"
        if item.get("abstract_inverted_index"):
            word_positions = []
            for word, positions in item["abstract_inverted_index"].items():
                word_positions.extend((pos, word) for pos in positions)
            abstract = ' '.join(word for _, word in sorted(word_positions))
        elif item.get("abstract"):
            abstract = item["abstract"]
        
        return {
            "doi": (item.get("doi") or "").replace("https://doi.org/", ""),
            "Title": item.get("title", "N/A"),
            "Authors": "; ".join(
                a["author"].get("display_name", "Unknown") 
                for a in item.get("authorships", [])
            ),
            "Year": str(item.get("publication_year", "N/A")),
            "Publisher": item.get("host_venue", {}).get("publisher", "N/A"),
            "Abstract": abstract,
            "Source": "OpenAlex",
            "Language": "en"
        }
    except Exception as e:
        print(f"OpenAlex processing error: {e}")
        return None

async def fetch_semanticscholar_articles(query: str, limit=15):
    """Fetch articles from Semantic Scholar with English filter"""
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={quote(query)}&limit={limit * 2}&fields=title,authors,year,venue,abstract,externalIds"
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await fetch_with_retry(client, url)
            if response:
                items = response.json().get("data", [])
                return [process_semanticscholar_item(item) for item in items]
    except Exception as e:
        print(f"Semantic Scholar error: {str(e)[:200]}")
    return []

def process_semanticscholar_item(item):
    """Process Semantic Scholar items with validation"""
    try:
        return {
            "doi": item.get("externalIds", {}).get("DOI", "N/A"),
            "Title": item.get("title", "N/A"),
            "Authors": "; ".join(a.get("name", "Unknown") for a in item.get("authors", [])),
            "Year": str(item.get("year", "N/A")),
            "Publisher": item.get("venue", "N/A"),
            "Abstract": item.get("abstract", "N/A"),
            "Source": "Semantic Scholar",
            "Language": "en"  # Semantic Scholar doesn't provide language, assume English
        }
    except Exception as e:
        print(f"Semantic Scholar processing error: {e}")
        return None

async def fetch_springer_via_crossref(query: str, limit=15):
    """Get Springer articles through Crossref with rate limiting"""
    springer_dois = await fetch_springer_dois(query, limit * 2)
    results = []
    
    # Process DOIs with rate limiting
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
    async def process_doi(doi):
        async with semaphore:
            await asyncio.sleep(1)  # Add delay between requests
            return await fetch_crossref_details(doi)
    
    tasks = [process_doi(doi) for doi in springer_dois]
    batch_results = await asyncio.gather(*tasks)
    
    return [r for r in batch_results if r and r["Language"] == "en"]

async def fetch_springer_dois(query: str, limit=15):
    """Fetch Springer DOIs with English filter"""
    params = {
        "q": f"{query}",
        "api_key": SPRINGER_API_KEY,
        "p": limit,
        "s": "1",
        "sort": "relevance"
    }
    try:
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await client.get(SPRINGER_API_URL, params=params)
            response.raise_for_status()
            items = response.json().get("records", [])
            return [item["doi"] for item in items if item.get("doi")]
    except Exception as e:
        print(f"Springer DOI error: {str(e)[:200]}")
        return []

async def fetch_crossref_details(doi: str):
    """Fetch details from Crossref with validation"""
    try:
        url = f"https://api.crossref.org/works/{quote(doi)}?mailto=retinanisaichandu@email.com"
        async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
            response = await fetch_with_retry(client, url)
            if response and response.status_code == 200:
                item = response.json()["message"]
                year = next(iter(
                    item.get("published", {}).get("date-parts", [[None]])[0] or
                    item.get("created", {}).get("date-parts", [[None]])[0] or
                    item.get("issued", {}).get("date-parts", [[None]])[0]
                ), None)
                
                return {
                    "doi": doi,
                    "Title": item.get("title", ["N/A"])[0],
                    "Authors": "; ".join(
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in item.get("author", [])
                    ) or "N/A",
                    "Year": str(year) if year else "N/A",
                    "Publisher": item.get("publisher", "N/A"),
                    "Abstract": item.get("abstract", "N/A"),
                    "Source": "Springer (via Crossref)",
                    "Language": item.get("language", "en")
                }
    except Exception as e:
        print(f"Crossref detail error for {doi}: {str(e)[:200]}")
    return None

def process_results(articles, min_results=10):
    """Process and validate results with fallback"""
    seen = set()
    filtered = []
    
    for article in articles:
        if not article or not all(article.get(f) not in ["N/A", None, ""] for f in ["Title", "Authors", "Year", "Publisher", "Abstract"]):
            continue
        
        if article.get("Language", "en") != "en":
            continue
        
        key = article["doi"] or f"{article['Title']}-{article['Year']}"
        if key not in seen:
            seen.add(key)
            filtered.append(article)
    
    # Sort by year descending, then title
    sorted_results = sorted(
        filtered,
        key=lambda x: (-int(x["Year"]) if x["Year"].isdigit() else 0, x["Title"])
    )
    
    return sorted_results[:15] if len(sorted_results) >= min_results else sorted_results

async def fetch_all_articles(query: str):
    """Main function with robust result gathering"""
    try:
        # Fetch from all sources in parallel
        openalex, semanticscholar = await asyncio.gather(
            #fetch_crossref_articles(query),
            fetch_openalex_articles(query),
            fetch_semanticscholar_articles(query),
            #fetch_springer_via_crossref(query)
        )
        
        # Combine and process results
        all_articles = [a for a in   openalex + semanticscholar if a]
        final_articles = process_results(all_articles)
        
        # Save results
        os.makedirs(os.path.join(OUTPUT_DIR, "results"), exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # pd.DataFrame(final_articles).to_excel(
        #     os.path.join(OUTPUT_DIR, "results", f"articles_{query}_{timestamp}.xlsx"),
        #     index=False
        # )
        
        # Validate and return
        validated = []
        for art in final_articles:
            try:
                validated.append(ReferenceObject(
                    AuthorName=art["Authors"],
                    TitleName=art["Title"],
                    Year=art["Year"],
                    Publisher=art["Publisher"],
                    Abstract=art["Abstract"]
                ))
            except Exception as e:
                print(f"Validation error: {e}")
                continue

        # #Insert the query, title, and references into the essays collection
        # essay_document = {
        #     "title": query,
        #     "references": validated[:15],  
        #     "created_at": datetime.utcnow()
        # }
        # inserted_document = essays_collection.insert_one(essay_document)
        
        return QueryResponse(references=validated[:15])
        
    except Exception as e:
        print(f"Critical error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")