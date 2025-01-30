
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

async def identify_content_tasks(content: str, client: OpenAI) -> List[str]:
    """Identify tasks from content using prompt chaining"""
    task_prompt = f"""
    Analyze this content and list specific tasks to complete:
    {content[:3000]}
    
    Identify all the (5-7) main tasks considering:
    1. Explicit questions/instructions in content
    2. Implicit requirements based on structure
    3. Required output formats
    4. Key themes and terminology
    
    Return JSON format:
    {{
        "tasks": [
            {{
                "task_id": "t1",
                "description": "Clear task description",
                "type": "question|analysis|summary|etc"
            }}
        ]
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Expert task identification specialist"},
            {"role": "user", "content": task_prompt}
        ],
        temperature=0.4,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)["tasks"]

async def generate_initial_output(content: str, client: OpenAI) -> tuple:
    """Generate immediate HTML output with task-focused prompt chaining"""
    # Stage 1: Identify tasks
    tasks = await identify_content_tasks(content, client)
    
    # Stage 2: Generate HTML
    prompt = f"""
    Create structured HTML output for these tasks:
    {json.dumps(tasks, indent=2)}
    
    Original Content:
    {content[:3000]}
    
    Requirements:
    1. Create separate section for each task
    2. Answer questions directly if present
    3. Use <div class='task'> containers
    4. Preserve original numbering
    5. Add data-task-id attributes for tracking
    
    Return ONLY HTML body content without <html> tags.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Expert HTML task formatter"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    
    html_content = response.choices[0].message.content.strip()
    
    # Save file
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    filename = f"initial_{uuid.uuid4().hex[:8]}.html"
    filepath = output_dir / filename
    
    with open(filepath, "w") as f:
        f.write(f"<!DOCTYPE html>\n<html>\n<body>\n{html_content}\n</body>\n</html>")
    
    return html_content, str(filepath), tasks

async def generate_clarifying_questions(content: str, tasks: List[dict], client: OpenAI) -> List[Dict[str, any]]:
    """Generate task-focused essential questions"""
    prompt = f"""
    Generate crucial questions to better complete these tasks:
    {json.dumps(tasks, indent=2)}
    
    Content Context:
    {content[:3000]}
    
    Requirements:
    - Focus on missing information needs
    - Include multiple-choice options where applicable
    - Avoid obvious or redundant questions
    - Ask last question something like if you want to add any new task ? 
    
    Response Format in JSON:
    {{
        "questions": [
            {{
                "task_id": "t1",
                "question_id": "q1",
                "question_text": "Specific question text",
                "options": ["Relevant", "Choices"],
                "critical": boolean
            }}
        ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "Expert task-focused question generator"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)["questions"]
    
    except Exception as e:
        logger.error(f"Question generation error: {str(e)}")
        return [{
            "question_id": "fallback",
            "question_text": "Please specify any critical requirements:",
            "options": []
        }]

async def generate_task_outline(content: str, tasks: List[dict], answers: List[dict], client: OpenAI) -> Dict:
    """Create dynamic task-oriented outline"""
    answer_map = {a['question_id']: a['answer'] for a in answers}
    
    prompt = f"""
    Create outline based on:
    - Identified Tasks: {json.dumps(tasks, indent=2)}
    - User Answers: {json.dumps(answer_map, indent=2)}
    - Content Context: {content[:3000]}
    
    Requirements:
    1. Maintain original task order
    2. Include answer summaries
    3. Add subtasks for complex items
    4. Mark completion priorities
    
    Return JSON format:
    {{
        "title": "Task Completion Outline",
        "tasks": [
            {{
                "task_id": "t1",
                "description": "Task description",
                "answer_summary": "Extracted answer",
                "subtasks": ["list", "of steps"]
            }}
        ]
    }}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Expert task organizer"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.4,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

async def generate_final_content(content: str, tasks: List[dict], outline: Dict, answers: List[dict], client: OpenAI) -> str:
    """Generate comprehensive final output"""
    prompt = f"""
    Create final document combining:
    - Original Content: {content[:3000]}
    - Identified Tasks: {json.dumps(tasks, indent=2)}
    - Completion Outline: {json.dumps(outline, indent=2)}
    - User Answers: {json.dumps(answers, indent=2)}
    
    Requirements:
    1. Address all tasks systematically
    2. Integrate answers naturally
    3. Use professional academic formatting
    4. Include section numbers/headers
    5. Add references if needed
    
    Return rich HTML format without <html> tags.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "Expert document integrator"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6
    )
    
    html_content = response.choices[0].message.content.strip()
    
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    filename = f"final_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
    filepath = output_dir / filename
    
    with open(filepath, "w") as f:
        f.write(f"<!DOCTYPE html>\n<html>\n<body>\n{html_content}\n</body>\n</html>")
    
    return html_content, str(filepath)