from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from typing import Optional, List, Dict,Any
from pydantic import BaseModel
from openai import OpenAI
import PyPDF2
import docx
import pytesseract
from PIL import Image
import io
import json
import logging
import uuid
from datetime import datetime
from pymongo import MongoClient
from bson import json_util
from config import OUTPUT_DIR
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()


mongo_client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
db = mongo_client["Kuizlo"]
essays_collection = db["essays"]
session_questions_collection = db["session_questions"]

def get_session_id():
    """Generate unique session ID with collision check"""
    while True:
        session_id = str(uuid.uuid4())
        if not session_questions_collection.find_one({"session_id": session_id}):
            return session_id

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


async def extract_text_from_file(file: UploadFile) -> str:
    """Extract text from various file formats"""
    try:
        content = await file.read()
        file_extension = file.filename.split('.')[-1].lower()
        
        if file_extension == 'pdf':
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            return " ".join(page.extract_text() for page in pdf_reader.pages)
            
        elif file_extension == 'docx':
            doc = docx.Document(io.BytesIO(content))
            return " ".join(paragraph.text for paragraph in doc.paragraphs)
            
        elif file_extension in ['jpg', 'jpeg', 'png']:
            image = Image.open(io.BytesIO(content))
            return pytesseract.image_to_string(image)
            
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
            
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing file")



async def generate_clarifying_questions(content: str, client: OpenAI) -> List[Dict[str, any]]:
    """Generate content-specific questions through multi-stage analysis"""
    # Stage 1: Content Analysis
    analysis_prompt = f"""
    Analyze the following document content and ask few inteligent question you need to finish the identified task in the given content:
    
    {content[:3000]}
    
    Identify:
    1.Identify task and ask if you need any more information about task to complete it.
    2. Core themes/main topics
    3. Potential ambiguities needing clarification
    4. Technical/specialized terminology
    5. Implicit requirements
    6. Formatting patterns
    7. Audience indicators
    
    Return JSON format:
    {{
        "analysis": {{
            "core_themes": [string],
            "ambiguities": [string],
            "special_terms": [string],
            "implicit_requirements": [string],
            "formatting_patterns": [string],
            "audience_cues": [string]
        }}
    }}
    """
    
    # Stage 2: Question Generation
    generation_prompt = """
    Generate essential clarification questions based on this analysis:
    {analysis}
    
    Requirements:
    - Create 5-8 questions minimum
    - Prioritize content-specific questions
    - Include multiple-choice options where appropriate
    - Cover both factual and interpretive aspects
    - Address potential ambiguities
    
    Response JSON Format:
    {{
        "questions": [
            {{
                "question_id": "q1",
                "question_text": "What type of references are preferred?",
                "question_type": "formatting",
                "options": ["Academic", "Industry", "Mixed"],
                "context_source": "Document contains technical terminology"
            }}
        ]
    }}
    """
    
    try:
        # Content analysis phase
        analysis_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Expert content analyst"},
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.3,
            response_format={"type": "json_object"}
        )
        analysis = json.loads(analysis_response.choices[0].message.content)["analysis"]
        
        # Question generation phase
        gen_response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Question generation specialist"},
                {"role": "user", "content": generation_prompt.format(analysis=json.dumps(analysis))}
            ],
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        
        return json.loads(gen_response.choices[0].message.content)["questions"]
    
    except Exception as e:
        logger.error(f"Question generation error: {str(e)}")
        return [{
            "question_id": "fallback",
            "question_text": "Please specify any special requirements:",
            "question_type": "general",
            "options": []
        }]

async def generate_task_outline(content: str, answers: List[Dict], client: OpenAI) -> Dict:
    """Generate intelligent outline based on task type"""
    answer_context = "\n".join([f"{a.question_id}: {a.answer}" for a in answers])
    #task_prompts = get_task_specific_prompts(task_type)
    
    prompt = f"""
    Create detailed outline based on:
    - Content: {content[:3000]}
    - Requirements: {answer_context}

    
    Include 3-5 main sections with sub-sections.
    Mark critical points with [IMPORTANT].
    
    Return JSON format with:
    {{
        "title": "Document Title",
        "sections": [
            {{
                "name": "Section Name",
                "key_points": ["list", "of points"],
                "subsections": ["optional", "subsections"]
            }}
        ],
        "formatting": ["list of formatting requirements"]
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Professional document architect"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        response_format={"type": "json_object"}
    )
    
    return json.loads(response.choices[0].message.content)


async def generate_final_content(content: str, outline: Dict, client: OpenAI) -> str:
    """Generate HTML content from outline and save to file"""
    outline_str = json.dumps(outline, indent=2)
    
    prompt = f"""
    Create professional HTML content following this outline:
    {outline_str}
    
    Source Content: {content[:3000]}
    
    Requirements:
    1. Use clean, semantic HTML5
    2. Include appropriate headings (h1-h3)
    3. Format lists as <ul> or <ol> with <li> items
    4. Use <strong> and <em> for emphasis
    5. Add section dividers with <hr>
    6. Maintain proper hierarchy and structure
    
    Return ONLY the HTML body content without <html> or <body> tags.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Expert HTML content generator"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6
    )
    
    html_content = response.choices[0].message.content.strip()
    
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    filename = f"result_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
    filepath = output_dir / filename

    with open(filepath, "w") as f:
        f.write(f"<!DOCTYPE html>\n<html>\n<body>\n{html_content}\n</body>\n</html>")
    
    return html_content, str(filepath)

async def generate_initial_output(content: str, client: OpenAI) -> tuple:
    """Generate immediate HTML analysis from content"""
    prompt = f"""
    Analyze this content and create structured HTML output:
    {content[:3000]}
    
    Guidelines:
    1. If content contains questions, answer them in <ol> lists
    2. For case studies, create sectioned <div> elements
    3. Use <h2> for main headings
    4. Format definitions as <dl> lists
    5. Preserve original structure where possible
    6. Add class attributes for styling (e.g., class="question-block")
    
    Return ONLY the HTML body content without <html> or <body> tags.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Expert content analyzer and HTML formatter"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    
    html_content = response.choices[0].message.content.strip()
    
    # Save to file
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    filename = f"initial_{uuid.uuid4().hex[:8]}.html"
    filepath = output_dir / filename
    
    with open(filepath, "w") as f:
        f.write(f"<!DOCTYPE html>\n<html>\n<body>\n{html_content}\n</body>\n</html>")
    
    return html_content, str(filepath)

