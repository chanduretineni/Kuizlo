from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import httpx
import pandas as pd
from datetime import datetime
import os
import openai
from openai import OpenAI

client = OpenAI(api_key="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")

app = FastAPI()

IEEE_API_KEY = "7uf2eh4qtpdz8nuhsmnajvvc"
IEEE_API_URL = "https://ieeexploreapi.ieee.org/api/v1/search/articles"

SPRINGER_API_KEY = "afb38807408f472ed1e4c9666a9a644a"
SPRINGER_API_URL = "http://api.springernature.com/metadata/json"


class QueryRequest(BaseModel):
    query: str

OUTPUT_DIR = "results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.post("/get-reference-papers/")
async def get_reference_papers(request: QueryRequest):
    """Fetch top 10 reference papers from IEEE Xplore API."""
    try:
        params = {
            "apikey": IEEE_API_KEY,
            "querytext": request.query,
            "max_records": 10,
            "start_record": 1,
            "sort_field": "relevance",
            "sort_order": "desc",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(IEEE_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

        articles = data.get("articles", [])
        if not articles:
            raise HTTPException(status_code=404, detail="No articles found for the given query.")

        records = []
        for article in articles:
            records.append({
                "Title": article.get("title", "N/A"),
                "Authors": "; ".join([author.get("full_name", "N/A") for author in article.get("authors", {}).get("authors", [])]),
                "Publication Year": article.get("publication_year", "N/A"),
                "DOI": article.get("doi", "N/A"),
                "Abstract": article.get("abstract", "N/A"),
                "Link": article.get("pdf_url", "N/A"),
            })

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(OUTPUT_DIR, f"reference_papers_{timestamp}.xlsx")
        df = pd.DataFrame(records)
        df.to_excel(output_file, index=False)

        return {"message": "File created successfully.", "file_path": output_file}

    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data from IEEE API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# Request model
class SpringerQueryRequest(BaseModel):
    query: str

@app.post("/get-springer-papers/")
async def get_springer_papers(request: SpringerQueryRequest):
    """
    Fetch top reference papers from Springer API and save them to an Excel file.
    """
    try:
        params = {
            "q": request.query,
            "api_key": SPRINGER_API_KEY,
            "p": 10  
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(SPRINGER_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

        records = []
        for record in data.get("records", []):
            creators = record.get("creators", [])
            authors = "; ".join(
                [creator.get("creator", "N/A") if isinstance(creator, dict) else str(creator) for creator in creators]
            )

            urls = "; ".join([url.get("value", "N/A") for url in record.get("url", [])])

            records.append({
                "Title": record.get("title", "N/A"),
                "Authors": authors,
                "Publication Name": record.get("publicationName", "N/A"),
                "Publication Date": record.get("publicationDate", "N/A"),
                "DOI": record.get("doi", "N/A"),
                "Abstract": record.get("abstract", "N/A"),
                "Subjects": "; ".join(record.get("subjects", [])),
                "URLs": urls,
                "Open Access": record.get("openaccess", "false"),
                "Volume": record.get("volume", "N/A"),
                "Number": record.get("number", "N/A"),
                "Starting Page": record.get("startingPage", "N/A"),
                "Ending Page": record.get("endingPage", "N/A"),
                "ISSN": record.get("issn", "N/A"),
                "Publisher": record.get("publisher", "N/A"),
                "Content Type": record.get("contentType", "N/A"),
            })

        if not records:
            raise HTTPException(status_code=404, detail="No articles found for the given query.")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(OUTPUT_DIR, f"springer_papers_{timestamp}.xlsx")
        df = pd.DataFrame(records)
        df.to_excel(output_file, index=False)

        return {"message": "File created successfully.", "file_path": output_file}

    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data from Springer API: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")




# use this from env

# class Reference(BaseModel):
#     id: str
#     title: str

# class GenerateEssayRequest(BaseModel):
#     topic: str
#     selected_references: List[Reference]

# class Citation(BaseModel):
#     reference_id: str
#     citation: str

# class GenerateEssayResponse(BaseModel):
#     essay: str

# @app.post("/generate-essay", response_model=GenerateEssayResponse)
# async def generate_essay(request: GenerateEssayRequest):
#     """
#     Generates a 2000-word essay on the given topic using the provided references and saves it to a file.
#     """
#     try:
#         # Prepare references for prompt
#         references_text = "\n".join(
#             [f"{ref.id}: {ref.title}" for ref in request.selected_references]
#         )

#         # Construct the initial ChatGPT prompt
#         base_prompt = f"""
#         Write a detailed 2000-word essay on the topic: "{request.topic}". 
#         Use the following references and provide proper citations in APA format:

#         References:
#         {references_text}

#         Include citations in the text, referencing the titles provided above. 
#         End the essay with a properly formatted references section.
#         """

#         # Initialize variables for multi-part essay generation
#         essay_parts = []
#         max_length = 750  

#         # Generate essay in segments
#         remaining_prompt = base_prompt
#         while len(" ".join(essay_parts)) < 2000 * 5:  # Rough token-to-word ratio
#             response = openai.ChatCompletion.create(
#                 model="gpt-4o-mini",
#                 messages=[
#                     {"role": "system", "content": "You are an expert academic writer."},
#                     {"role": "user", "content": remaining_prompt}
#                 ],
#                 temperature=0.7,
#                 max_tokens=max_length
#             )
#             part = response['choices'][0]['message']['content']
#             essay_parts.append(part)

#             # Update the prompt for continuation
#             remaining_prompt = "Continue writing from where you left off."

#         # Combine essay parts
#         essay_text = "\n\n".join(essay_parts)

#         # Ensure the essay is roughly 2000 words (truncate excess if needed)
#         essay_text = " ".join(essay_text.split()[:2000])

#         # Save the essay to a text file
#         result_folder = "results"
#         os.makedirs(result_folder, exist_ok=True)
#         file_name = os.path.join(result_folder, f"{request.topic.replace(' ', '_')}.txt")
#         with open(file_name, "w", encoding="utf-8") as file:
#             file.write(essay_text)

#         return GenerateEssayResponse(essay=essay_text)

#     except openai.error.OpenAIError as e:
#         raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


# Request and Response Models
class Reference(BaseModel):
    id: str
    title: str
    author: str
    year: int

class GenerateEssayRequest(BaseModel):
    topic: str
    selected_references: List[Reference]

class GenerateEssayResponse(BaseModel):
    essay: str
    file_path: str

@app.post("/generate-essay", response_model=GenerateEssayResponse)
async def generate_essay(request: GenerateEssayRequest):
    """
    Generates a 2000-word essay on the given topic using the provided references and saves it to a file.
    """
    try:
        references_text = "\n".join(
            [f"{ref.id}: {ref.author} ({ref.year}). {ref.title}." for ref in request.selected_references]
        )

        #base promt for gpt ->
        base_prompt = f"""
        Write a detailed 2000-word essay on the topic: "{request.topic}". 
        Use the following references for your citations in APA format:

        References:
        {references_text}

        - Include in-text citations (e.g., Author, Year) that correspond to the provided references.
        - End the essay with a properly formatted References section based on the APA style.
        - Format the essay into clear paragraphs. Each paragraph should be focused on one idea, ensuring that the essay reads smoothly and is easy to follow.
        """

        essay_parts = []
        max_tokens_per_request = 750  
        generated_word_count = 0
        target_word_count = 2000

        # Generate essay iteratively
        while generated_word_count < target_word_count:

            continuation_prompt = base_prompt + "\n\nContinue from the last paragraph:\n" + "\n".join(essay_parts[-1:])

            response = client.chat.completions.create(model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert academic writer."},
                {"role": "user", "content": continuation_prompt}
            ],
            temperature=0.7,
            max_tokens=max_tokens_per_request)
            part = response.choices[0].message.content
            essay_parts.append(part)
            generated_word_count = sum(len(p.split()) for p in essay_parts)
            print(generated_word_count)

        essay_text = " ".join(essay_parts)
        essay_text = " ".join(essay_text.split()[:target_word_count])

        essay_text = "\n\n".join(essay_text.split("\n\n"))

        results_folder = "results"
        os.makedirs(results_folder, exist_ok=True)
        file_name = os.path.join(results_folder, f"{request.topic.replace(' ', '_')}.txt")
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(essay_text)

        return GenerateEssayResponse(essay=essay_text, file_path=file_name)

    except openai.OpenAIError as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")



# Todo:-
# Check the publication date of the reference pages. 
# send documention of springer to rahul 
# create a new endpoint for hix api key 
# write the logic to make the essat generator.