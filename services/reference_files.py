import httpx
import json
from config import IEEE_API_URL, IEEE_API_KEY
from config import SPRINGER_API_URL, SPRINGER_API_KEY, OUTPUT_DIR
from fastapi import HTTPException
import pandas as pd
from datetime import datetime
import os
from models.request_models import ReferenceObject,QueryResponse
async def fetch_ieee_articles(query: str):
    params = {
        "apikey": IEEE_API_KEY,
        "querytext": query
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(IEEE_API_URL, params=params)
        return response.json()



# async def fetch_springer_articles(query: str):
#     params = {
#         "api_key": SPRINGER_API_KEY,
#         "q": query
#     }

#     async with httpx.AsyncClient() as client:
#         response = await client.get(SPRINGER_API_URL, params=params)
#         response.raise_for_status()
#         data = response.json()

#     records = []
#     for record in data.get("records", []):
#         creators = record.get("creators", [])
#         authors = "; ".join(
#             [creator.get("creator", "N/A") if isinstance(creator, dict) else str(creator) for creator in creators]
#         )

#         urls = "; ".join([url.get("value", "N/A") for url in record.get("url", [])])
#         if record.get("doi"):
#             crossref_data = await get_crossref_data(record.get("doi"))
#         records.append({
#             "Title": record.get("title", "N/A"),
#             "Authors": authors,
#             "Publication Name": record.get("publicationName", "N/A"),
#             "Publication Date": record.get("publicationDate", "N/A"),
#             "DOI": record.get("doi", "N/A"),
#             "Abstract": record.get("abstract", "N/A"),
#             "Subjects": "; ".join(record.get("subjects", [])),
#             "URLs": urls,
#             "Open Access": record.get("openaccess", "false"),
#             "Volume": record.get("volume", "N/A"),
#             "Number": record.get("number", "N/A"),
#             "Starting Page": record.get("startingPage", "N/A"),
#             "Ending Page": record.get("endingPage", "N/A"),
#             "ISSN": record.get("issn", "N/A"),
#             "Publisher": record.get("publisher", "N/A"),
#             "Content Type": record.get("contentType", "N/A"),
#         })

#     if not records:
#         raise HTTPException(status_code=404, detail="No articles found for the given query.")

#     timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
#     output_file = os.path.join(OUTPUT_DIR, f"springer_papers_{timestamp}.xlsx")
#     df = pd.DataFrame(records)
#     df.to_excel(output_file, index=False)

#     return {"message": "File created successfully.", "file_path": output_file}


async def get_crossref_data(doi: str):
    """Retrieves data from the Crossref API using a DOI."""
    url = f"https://api.crossref.org/works/{doi}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {})
    except httpx.HTTPError as e:
        print(f"Crossref API error for DOI {doi}: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from Crossref API for DOI {doi}: {e}")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred while fetching data from Crossref API: {e}")
        return {}

async def fetch_springer_articles(query: str):
    """Fetches articles from the Springer API and enriches them with Crossref data."""
    params = {
        "api_key": SPRINGER_API_KEY,
        "q": query
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(SPRINGER_API_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=response.status_code, detail=f"Springer API request failed: {e}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"Invalid JSON received from Springer API: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while fetching data from Springer API: {e}")

    records = []
    for record in data.get("records", []):
        creators = record.get("creators", [])
        springer_authors = "; ".join(
            [creator.get("creator", "N/A") if isinstance(creator, dict) else str(creator) for creator in creators]
        )
        springer_abstract = record.get("abstract", "N/A")
        springer_publication_name = record.get("publicationName", "N/A")
        springer_publication_date = record.get("publicationDate", "N/A")
        springer_urls = "; ".join([url.get("value", "N/A") for url in record.get("url", [])])
        springer_title = record.get("title","N/A")

        doi = record.get("doi", None)
        crossref_data = {}
        if doi:
            crossref_data = await get_crossref_data(doi)

        title = crossref_data.get("title", [springer_title])[0]
        authors = "; ".join([
            f"{author.get('given', '')} {author.get('family', '')}"
            for author in crossref_data.get("author", [])
        ]) if crossref_data.get("author") else springer_authors
        publication_date_parts = crossref_data.get("published-online", {}) or crossref_data.get("published-print",{}) or crossref_data.get("created",{})
        publication_date = "-".join(map(str, publication_date_parts.get("date-parts", [["N/A"]])[0])) if publication_date_parts.get("date-parts") else springer_publication_date
        publisher = crossref_data.get("publisher", "N/A")
        abstract = crossref_data.get("abstract", springer_abstract)
        url = crossref_data.get("URL", springer_urls)
        container_title = crossref_data.get("container-title", [springer_publication_name])[0]

        records.append({
            "Title": title,
            "Authors": authors,
            "Publication Name": container_title,
            "Publication Date": publication_date,
            "DOI": doi,
            "Abstract": abstract,
            "Publisher": publisher,
            "URL": url,
        })

    if not records:
        raise HTTPException(status_code=404, detail="No articles found for the given query.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = os.path.join(OUTPUT_DIR,"results")
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
    output_file = os.path.join(OUTPUT_DIR, f"springer_papers_{query}_{timestamp}.xlsx") # Added query to filename
    df = pd.DataFrame(records)
    df.to_excel(output_file, index=False)

    # Convert the records into the response model
    references = [ReferenceObject(AuthorName=rec["Authors"], TitleName=rec["Title"], Year=rec["Publication Date"].split("-")[0], Publisher=rec["Publisher"]) for rec in records]

    return QueryResponse(references=references)