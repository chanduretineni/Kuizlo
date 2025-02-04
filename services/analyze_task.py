
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
    question : str
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

async def identify_content_tasks(content: str, client: OpenAI) -> List[dict]:
    """Identify tasks from content dynamically using detailed and structured prompts"""
    task_prompt = f"""
    You are an expert task analyzer and strategist. Analyze the provided content in detail and identify all possible tasks. Be flexible and dynamic enough to handle diverse data structures or contexts.

    **Context to consider:**
    1. The file may contain structured data (tables, forms) or unstructured text (paragraphs, images, or lists).
    2. Explicit and implicit tasks should be included, covering questions, calculations, summaries, or suggested next steps.
    3. Original data formats may require specific outputs or transformations (e.g., HTML, JSON, Excel reports).

    **Output JSON Schema:**
    {{
        "tasks": [
            {{
                "task_id": "t1",
                "description": "Clear task description summarizing purpose and action",
                "type": "question|calculation|summary|transformation|etc",
                "priority": "high|medium|low",
                "dependencies": ["list other tasks it depends on, if any"]
            }}
        ]
    }}

    **Guidelines for Task Generation:**
    1. If the content has questions or requests, create tasks to answer them.
    2. For structured data, infer any logical groupings, patterns, or summaries required.
    3. Recognize themes and terms suggesting implicit tasks or areas requiring analysis.
    4. Each task should align with generating meaningful output for end users.
    5. If multiple outputs (e.g., charts, dashboards) are possible, include suggestions.

    Analyze the content here:
    {content[:3000]}

    Return the JSON output strictly matching the schema.
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a highly skilled AI designed to extract meaningful tasks from diverse data sources. Your role is to ensure flexibility and precision in identifying tasks for effective outputs."},
            {"role": "user", "content": task_prompt}
        ],
        temperature=0.4,
        response_format={"type": "json_object"}
    )

    try:
        tasks = json.loads(response.choices[0].message.content)["tasks"]
        return tasks
    except (KeyError, json.JSONDecodeError) as e:
        logger.error(f"Error parsing tasks from response: {str(e)}")
        raise HTTPException(status_code=500, detail="Error identifying tasks from content")


async def generate_initial_output(content: str, client: OpenAI) -> tuple:
    """Generate accurate HTML output with task-focused answers"""
    # Stage 1: Identify tasks
    tasks = await identify_content_tasks(content, client)
    
    # Stage 2: Generate HTML
    prompt = f"""
    You are an expert content analyzer and HTML generator. Your goal is to create structured and accurate HTML output based on identified tasks. 

    **Context:**
    1. Tasks are extracted from the provided content. Use the extracted tasks and the content itself to generate answers.
    2. If the task involves a question explicitly stated in the content, provide a direct answer using the context.
    3. For tasks that require logical interpretation, generate answers intelligently based on content themes.
    4. Ensure all information in the HTML is factually accurate and corresponds to the original context.

    **HTML Requirements:**
    1. Create a separate section for each task inside a `<div>` with a `class='task'` and a `data-task-id` attribute matching the task ID.
    2. Preserve the numbering and order of tasks as provided in the task list.
    3. For each task:
        - Include the task description as a heading.
        - Provide an answer or output for the task.
        - Clearly indicate if the answer is derived from the context or generated by AI.
    4. Format the HTML to be simple and readable. Use semantic tags where appropriate.

    **Example HTML for a task:**
    ```
    <div class='task' data-task-id='t1'>
        <h2>Task 1: Analyze the content for key themes</h2>
        <p><strong>Answer:</strong> The content mentions key themes like...</p>
    </div>
    ```

    **Tasks to Generate HTML For:**
    {json.dumps(tasks, indent=2)}
    
    **Original Content:**
    {content[:3000]}

    Return ONLY the HTML body content (without `<html>` tags or `<body>` tags).
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system", 
                "content": (
                    "You are a highly skilled AI for creating structured HTML outputs. "
                    "Your purpose is to generate clear, accurate, and readable HTML sections for tasks, "
                    "leveraging both content-derived answers and AI-generated solutions where needed."
                )
            },
            {"role": "user", "content": prompt}
        ],
        temperature=0.5
    )
    
    html_content = response.choices[0].message.content.strip()
    
    # Save the generated HTML to a file
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    filename = f"initial_{uuid.uuid4().hex[:8]}.html"
    filepath = output_dir / filename
    
    with open(filepath, "w") as f:
        f.write(f"<!DOCTYPE html>\n<html>\n<body>\n{html_content}\n</body>\n</html>")
    
    return html_content, str(filepath), tasks


async def generate_clarifying_questions(content: str, tasks: List[dict], client: OpenAI) -> List[Dict[str, any]]:
    """Generate task-focused essential questions for clarification"""
    prompt = f"""
    You are an expert in identifying missing details and generating clarifying questions to complete tasks effectively. 

    **Objective:**
    - Review the generated tasks and content context to identify any gaps or ambiguities.
    - Focus on asking only essential and actionable questions to complete the tasks.
    - Avoid asking questions that are already explicitly stated as tasks or questions in the context.
    - Provide questions in a clear and concise manner, ensuring they are relevant to the tasks and context.
    - As the last question, ask if the user wants to add any additional tasks or inputs.

    **Requirements for Questions:**
    1. Only ask for information that is missing or unclear, based on the tasks and context.
    2. Do not repeat or reframe questions explicitly present in the tasks.
    3. Where applicable, provide multiple-choice options to make responses easier.
    4. Ensure each question is tied to a specific task and is actionable.
    5. End the list with: "Do you want to add any additional tasks or details?"

    **Tasks to Clarify:**
    {json.dumps(tasks, indent=2)}
    
    **Content Context:**
    {content[:3000]}

    **Response Format in JSON:**
    {{
        "questions": [
            {{
                "task_id": "t1",
                "question_id": "q1",
                "question_text": "Specific question text",
                "options": ["Option 1", "Option 2"],
                "critical": boolean
            }}
        ]
    }}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a highly skilled AI specializing in generating clarifying questions "
                        "to address task gaps. Your purpose is to analyze tasks and context thoroughly, "
                        "identify missing information, and generate actionable and relevant questions to "
                        "ensure task completion. Avoid redundancy and focus on what is necessary."
                    )
                },
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
            "question_text": "Please specify any critical requirements or additional tasks:",
            "options": []
        }]

async def generate_task_outline(content: str, tasks: List[dict], answers: List[dict], client: OpenAI) -> Dict:
    """Create a dynamic, high-level task-oriented outline based on tasks, answers, and context."""
    answer_map = {a.question: a.answer for a in answers}

    prompt = f"""
    You are a highly skilled AI specialized in organizing tasks and responses into clear, actionable outlines. 

    **Objective:**
    - Create a high-level outline summarizing identified tasks and user-provided answers.
    - Help the user visualize the final structure of the output with concise and well-organized content.

    **Requirements:**
    1. Retain the original order of tasks for consistency.
    2. Provide a summary of user answers directly associated with each task.
    3. For complex tasks, break them into logical subtasks for clarity.
    4. Highlight tasks or subtasks that require high priority or immediate attention.
    5. Ensure the outline is structured, easy to read, and intuitive for users to follow.

    **Input Data:**
    - **Identified Tasks:** {json.dumps(tasks, indent=2)}
    - **User Answers:** {json.dumps(answer_map, indent=2)}
    - **Content Context:** {content[:3000]}

    **Output JSON Format:**
    {{
        "title": "Task Completion Outline",
        "tasks": [
            {{
                "task_id": "t1",
                "description": "Detailed task description",
                "answer_summary": "Summary of user answer or key input",
                "subtasks": [
                    "Step 1",
                    "Step 2",
                    "Step 3"
                ],
                "priority": "High/Medium/Low"
            }}
        ]
    }}
    """
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert in task management and organization. Your role is to analyze provided "
                        "tasks, answers, and content to generate a comprehensive, high-level outline. Focus on "
                        "clarity, relevance, and actionable details while ensuring the final structure is easy "
                        "for users to interpret and follow."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Task outline generation error: {str(e)}")
        return {
            "title": "Task Completion Outline",
            "tasks": [
                {
                    "task_id": "fallback",
                    "description": "Unable to generate a detailed outline due to an error.",
                    "answer_summary": "N/A",
                    "subtasks": ["Please review the input and try again."],
                    "priority": "High"
                }
            ]
        }

async def generate_final_content(content: str, tasks: List[dict], outline: Dict, answers: List[dict], client: OpenAI) -> str:
    """Generate a comprehensive final output as a detailed HTML document."""
    answer_map = {a[1][1]: a[2][1] for a in answers}

    # Construct the prompt for a professional, detailed HTML output
    prompt = f"""
    You are a highly advanced AI specialized in generating comprehensive and detailed outputs.
    Your goal is to create a professional final document answering the tasks using the outline format and original content as context for answering the task:
    - **Original Content Context:** {content[:3000]}
    - **Identified Tasks:** {json.dumps(tasks, indent=2)}
    - **Completion Outline:** {json.dumps(outline, indent=2)}
    - **User Answers:** {json.dumps(answer_map, indent=2)}

    **Output Requirements:**
    1. Answer all the tasks in detailed way which you can solve using your ai and taking the context from the original content given.. 
    1. Address all tasks with precision and in the order they appear in the outline.
    2. Integrate user-provided answers naturally and seamlessly.
    3. Provide clear and detailed explanations for each task.
    4. Use professional and clean formatting (headers, lists, sections).
    5. Add references or supporting data where necessary (e.g., web lookups, mathematical calculations).
    6. Avoid redundant information and ensure each section has unique value.

    **HTML Output Specifications:**
    - Use basic HTML structure (headers: <h1>, <h2>, etc.; lists: <ul>, <ol>; paragraphs: <p>).
    - Ensure a clean and professional appearance.
    - Use section numbers (e.g., 1, 1.1, 2, etc.) for clarity.
    - Add summary and conclusion sections if applicable.

    Return only the body of the HTML document, without the `<html>` or `<body>` tags.
    """

    try:
        # Send the prompt to the OpenAI API for generating the final content
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert document generator. Use the provided content, tasks, outline, and answers "
                        "to create a cohesive and professional HTML document. Your output must be precise, "
                        "contextually accurate, and formatted for ease of reading."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        
        # Extract the HTML content from the response
        html_content = response.choices[0].message.content.strip()
        
        # Save the final HTML document to a file
        output_dir = Path("results")
        output_dir.mkdir(exist_ok=True)
        filename = f"final_{datetime.now().strftime('%Y%m%d%H%M%S')}.html"
        filepath = output_dir / filename
        
        with open(filepath, "w") as f:
            f.write(f"<!DOCTYPE html>\n<html>\n<body>\n{html_content}\n</body>\n</html>")
        
        return html_content  # Return the HTML body content
    except Exception as e:
        logger.error(f"Final content generation error: {str(e)}")
        return """
        <h1>Final Document</h1>
        <p>An error occurred while generating the final document. Please review the input data and try again.</p>
        """
