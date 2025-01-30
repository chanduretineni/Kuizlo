import os
from typing import List, Optional, Dict, Set, Tuple
import openai
import uuid
from fastapi import HTTPException, UploadFile
import PyPDF2
from PIL import Image
from pymongo import MongoClient
import pytesseract
import io
import logging
from datetime import datetime
from models.request_models import GeneratedQuestion,Answer, EssayOutline, AnswersRequest, QuestionsResponse, ReferenceObject, OutlineSection, EssayReferenceObject, QueryRequest
from config import OPENAI_API_KEY
from openai import OpenAI
import json
import math
import re
from bs4 import BeautifulSoup
from services.reference_files import fetch_all_articles
from services.essay_service import generate_references

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# MongoDB Connection
mongo_client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
db = mongo_client["Kuizlo"]
essays_collection = db["essays"]
session_questions_collection = db["session_questions"] 


# In-memory session storage (replace with Redis/DB in production)
sessions = {}

async def process_uploaded_file(file: UploadFile) -> str:
    """
    Process uploaded files and extract text content.
    Supports PDF, JPEG, and PNG files.
    """
    try:
        content = await file.read()
        file_extension = file.filename.split('.')[-1].lower()
        
        if file_extension == 'pdf':
            # Process PDF
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text_content = ""
            for page in pdf_reader.pages:
                text_content += page.extract_text()
            
        elif file_extension in ['jpg', 'jpeg', 'png']:
            # Process Images
            image = Image.open(io.BytesIO(content))
            text_content = pytesseract.image_to_string(image)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        return text_content.strip()
    
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error processing file")
    
# Detect writing type based on instructions and content
def detect_writing_type(instructions: str, content: str) -> str:
    writing_types = {
        'essay': ['analyze', 'discuss', 'compare', 'contrast', 'evaluate', 'argument', 'thesis'],
        'review': ['critique', 'review', 'assessment', 'evaluation', 'feedback'],
        'article': ['inform', 'report', 'describe', 'explain', 'article', 'publication'],
        'research paper': ['research', 'study', 'methodology', 'findings', 'academic'],
        'blog post': ['blog', 'personal', 'narrative', 'opinion', 'informal'],
        'report': ['report', 'business', 'technical', 'summary', 'findings']
    }
    
    # Convert instructions and content to lowercase for case-insensitive matching
    instructions_lower = instructions.lower()
    content_lower = content.lower()
    
    # Check for writing type matches
    for writing_type, keywords in writing_types.items():
        if any(keyword in instructions_lower or keyword in content_lower for keyword in keywords):
            return writing_type
    
    # Default to a generic type if no specific match is found
    return 'academic writing'

def get_session_id():
    while True:
        session_id = str(uuid.uuid4())  # Generate a new session ID
        if not session_questions_collection.find_one({"session_id": session_id}):
            return session_id  # Return the unique ID if it's not in the coll
        
async def generate_questions_from_context(
    instructions: str,
    file_content: str,
) -> List[GeneratedQuestion]:
    """
    Generate relevant questions based on the context using OpenAI API
    """
    try:
        session_id = get_session_id()
        # Detect the writing type
        writing_type = detect_writing_type(instructions, file_content)

        # Construct prompt for OpenAI
        prompt = f"""
        Based on the following instructions and context, generate 10 relevant questions to write a detailed {writing_type}.
        Detected Writing Type: {writing_type}
        For each question, provide the following in JSON format:
        - question_id (q1, q2, etc.)
        - question_text
        - question_type (reference, structure, topic_specific, audience, style)
        - options (array of possible answers, or null if open-ended)
        
        Instructions: {instructions}
        Content: {file_content[:1000]}
        
        Required question types:
        1. Reference requirements (with options)
        2. Word Count (open-ended)
        2. Essay structure preferences (with options)
        3. Specific topic focus areas (with options)
        4. Target audience (open-ended)
        5. Style and tone preferences (open-ended)
        6. If topic is essay or review as referency type (with options like APA,ML8, IEEE, Harvard and chicago)
        
        Format your response as a JSON array of question objects.
        Example format:
        [
            {{
                "question_id": "q1",
                "question_text": "What type of references would you prefer?",
                "question_type": "reference",
                "options": ["Academic journals", "Industry reports", "Both"]
            }}
        ]
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an academic writing assistant. Respond with properly formatted JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        # Get the raw response and parse it as JSON
        questions_raw = response.choices[0].message.content
        
        try:
            # Try to parse the response as JSON
            questions_data = json.loads(questions_raw)
            
            # Convert the parsed JSON into GeneratedQuestion objects
            questions = [
                GeneratedQuestion(
                    id=q["question_id"],
                    question=q["question_text"],
                    question_type=q["question_type"],
                    options=q.get("options")
                )
                for q in questions_data
            ]
            # Save session and questions in MongoDB
            session_questions_collection.insert_one({
                "session_id": session_id,
                "instructions": instructions,
                "file_content": file_content,
                "questions": [q.model_dump() for q in questions],
            })

            
        except json.JSONDecodeError:
            # Fallback if GPT doesn't return proper JSON
            logger.warning("Failed to parse GPT response as JSON. Using fallback questions.")
            
            # Extract questions using regex or string parsing
            # This is a simplified fallback that creates basic questions
            questions = []
            question_types = ["reference", "structure", "topic_specific", "audience", "style"]
            default_options = {
                "reference": ["Academic journals", "Industry reports", "Both"],
                "structure": ["Traditional", "Problem-solution", "Comparative"],
                "topic_specific": ["Recent developments", "Historical context", "Future implications"],
                "audience": None,
                "style": None
            }
            
            for i, q_type in enumerate(question_types):
                question_id = f"q{i+1}"
                questions.append(
                    GeneratedQuestion(
                        id=question_id,
                        question=f"What are your preferences regarding {q_type.replace('_', ' ')}?",
                        question_type=q_type,
                        options=default_options[q_type]
                    )
                )
        
            # Save session and questions in MongoDB
            session_questions_collection.insert_one({
                "session_id": session_id,
                "instructions": instructions,
                "file_content": file_content,
                "questions": [q.dict() for q in questions],
            })

        return QuestionsResponse(session_id=session_id, questions=questions)

    
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating questions")
    
    except Exception as e:
        logger.error(f"Error generating questions: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating questions")

# async def create_essay_outline(request: AnswersRequest) -> EssayOutline:
#     """
#     Create a detailed essay outline based on the answers and context provided
#     """
#     try:

#         # Fetch the session document from MongoDB using session_id
#         session_document = session_questions_collection.find_one({"session_id": request.session_id})

#         if not session_document:
#             raise HTTPException(status_code=404, detail="Session not found")

#         # Extract instructions and file content from the document
#         instructions = session_document.get("instructions", "")
#         file_content = session_document.get("file_content", "")

#         # Organize answers by question type
#         answers_by_type = {}
#         for answer in request.answers:
#             answers_by_type[answer.question_type] = {
#                 'question': answer.question,
#                 'answer': answer.answer
#             }
        
#         # Construct prompt for OpenAI
#         prompt = f"""
#         Create a detailed academic essay outline based on the following information:

#         Essay Instructions: {instructions}
        
#         Context from Questions and Answers:
#         {json.dumps(answers_by_type, indent=2)}
        
#         File Content Summary:
#         {file_content[:500]}

#         Create a comprehensive outline following this exact structure (respond in JSON format):
#         {{
#             "title": "Essay title",
#             "target_audience": "Based on audience answer",
#             "writing_style": "Based on style answer",
#             "reference_style": "Based on reference answer",
#             "total_word_count": 2000,
#             "introduction": {{
#                 "title": "Introduction",
#                 "key_points": ["point1", "point2"],
#                 "word_count": 250
#             }},
#             "main_sections": [
#                 {{
#                     "title": "Section Title",
#                     "key_points": ["point1", "point2"],
#                     "subsections": [
#                         {{
#                             "title": "Subsection Title",
#                             "key_points": ["point1", "point2"]
#                         }}
#                     ],
#                     "word_count": 500
#                 }}
#             ],
#             "conclusion": {{
#                 "title": "Conclusion",
#                 "key_points": ["point1", "point2"],
#                 "word_count": 250
#             }},
#             "references_section": {{
#                 "title": "References",
#                 "key_points": ["point1", "point2"],
#                 "word_count": 0
#             }}
#         }}

#         Ensure:
#         1. The outline is detailed enough to guide the essay writing
#         2. Key points are specific and actionable
#         3. Word counts are distributed appropriately
#         4. Subsections are included where relevant
#         5. The structure reflects the essay type and topic
#         6. All JSON keys match exactly as shown
#         7. Subsections must follow the exact format shown (title and key_points as arrays)
#         8. Word counts should total to the specified total_word_count
#         """
        
#         response = client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are an academic writing assistant. Provide the outline in valid JSON format."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.7
#         )
        
#        # Parse and validate JSON response
#         outline_content = json.loads(response.choices[0].message.content)
        
#         # Convert to EssayOutline model
#         outline = EssayOutline(**outline_content)
#         print(outline)
#         return outline
    
#     except Exception as e:
#         logger.error(f"Error creating outline: {str(e)}")
#         raise HTTPException(status_code=500, detail="Error creating outline")

# class CitationTracker:
#     def __init__(self):
#         self.citations: Set[str] = set()

#     def extract_citations(self, content: str, reference_style: str) -> None:
#         """Extract citations based on reference style"""
#         try:
#             if reference_style.lower() == 'apa':
#                 # Match patterns like (Author, Year) or (Author et al., Year)
#                 citations = re.findall(r'\(([^)]+?,\s*\d{4}[^)]*)\)', content)
#             elif reference_style.lower() == 'mla':
#                 # Match patterns like (Author Page) or (Author)
#                 citations = re.findall(r'\(([^)]+?\s*\d*)\)', content)
#             elif reference_style.lower() == 'chicago':
#                 # Match patterns like (Author Year) or (Author Year, Page)
#                 citations = re.findall(r'\(([^)]+?\s*\d{4}[^)]*)\)', content)
#             else:
#                 # Generic citation pattern
#                 citations = re.findall(r'\(([^)]+)\)', content)
            
#             for citation in citations:
#                 self.citations.add(citation.strip())
                
#         except Exception as e:
#             logger.error(f"Error extracting citations: {str(e)}")
#             # Continue without failing if citation extraction fails
#             pass

    # def get_all_citations(self) -> List[str]:
    #     return list(self.citations)

class HTMLFormatter:
    def __init__(self, outline: EssayOutline):
        self.outline = outline
        
    def format_section(self, content: str, section_title: str, level: int = 2) -> str:
        """Format a section with appropriate HTML tags"""
        # Clean the content if it contains HTML tags
        soup = BeautifulSoup(content, 'html.parser')
        cleaned_content = soup.get_text()
        
        formatted_content = f"""
        <section class="essay-section">
            <h{level} class="section-title">{section_title}</h{level}>
            <div class="section-content">
                {self._format_paragraphs(cleaned_content)}
            </div>
        </section>
        """
        return formatted_content
    
    def _format_paragraphs(self, content: str) -> str:
        """Format text into HTML paragraphs"""
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        return '\n'.join([f"<p>{p}</p>" for p in paragraphs])
    
    def format_essay(self, introduction: str, main_content: str, conclusion: str, references: str) -> str:
        """Format the complete essay in HTML"""
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{self.outline.title}</title>
            <style>
                .academic-essay {{
                    max-width: 800px;
                    margin: 2rem auto;
                    padding: 2rem;
                    font-family: 'Times New Roman', Times, serif;
                    line-height: 1.6;
                }}
                .essay-header {{
                    text-align: center;
                    margin-bottom: 2rem;
                }}
                .essay-section {{
                    margin-bottom: 1.5rem;
                }}
                .section-title {{
                    color: #333;
                    margin-bottom: 1rem;
                }}
                .references {{
                    margin-top: 2rem;
                    border-top: 1px solid #ccc;
                    padding-top: 1rem;
                }}
            </style>
        </head>
        <body>
            <article class="academic-essay">
                <header class="essay-header">
                    <h1>{self.outline.title}</h1>
                    <p class="essay-meta">Date: {timestamp}</p>
                </header>
                
                {self.format_section(introduction, "Introduction")}
                
                {main_content}
                
                {self.format_section(conclusion, "Conclusion")}
                
                <section class="references">
                    <h2>References</h2>
                    {references}
                </section>
            </article>
        </body>
        </html>
        """
        return html_template

# async def generate_section_content(
#     client: OpenAI,
#     section_title: str,
#     key_points: List[str],
#     word_count: int,
#     previous_content: str = "",
#     context: Dict = None,
#     citation_tracker: CitationTracker = None
# ) -> str:
#     """Generate content for a specific section"""
#     try:
#         prompt = f"""
#         Generate a {word_count}-word section for an academic essay.
        
#         Section Title: {section_title}
#         Key Points to Cover:
#         {json.dumps(key_points, indent=2)}
        
#         Previous Content Context:
#         {previous_content[:500] if previous_content else "No previous content"}
        
#         Additional Context:
#         Writing Style: {context.get('writing_style')}
#         Target Audience: {context.get('target_audience')}
#         Reference Style: {context.get('reference_style')}
        
#         Requirements:
#         1. Use proper academic language and tone
#         2. Include appropriate in-text citations in {context.get('reference_style')} format
#         3. Ensure smooth transitions between paragraphs
#         4. Don't repeat information from the previous content
#         5. Maintain coherent flow with previous sections
        
#         Return the content as plain text with natural paragraph breaks.
#         """
        
#         response = client.chat.completions.create(
#             model="gpt-4",
#             messages=[
#                 {"role": "system", "content": "You are an academic writing assistant. Provide clear, well-structured content."},
#                 {"role": "user", "content": prompt}
#             ],
#             temperature=0.7,
#             max_tokens=min(4000, word_count * 2)
#         )
        
#         content = response.choices[0].message.content
        
#         # Extract citations from the generated content
#         if citation_tracker:
#             citation_tracker.extract_citations(content, context.get('reference_style'))
        
#         return content
#     except Exception as e:
#         logger.error(f"Error generating section part: {str(e)}")
#         raise HTTPException(status_code=500, detail="Error generating section")

# # [Previous generate_introduction, generate_main_sections, generate_conclusion functions remain the same]

async def save_essay_to_file(essay_content: str, topic: str) -> str:
    """Save the generated essay to a file and return the file path"""
    try:
        # Create results directory if it doesn't exist
        results_folder = "results"
        os.makedirs(results_folder, exist_ok=True)
        
        # Generate unique filename using timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_topic = re.sub(r'[^\w\s-]', '', topic).replace(' ', '_')
        file_name = f"{safe_topic}_{timestamp}.html"
        file_path = os.path.join(results_folder, file_name)
        
        # Save the file
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(essay_content)
            
        logger.info(f"Essay saved successfully to {file_path}")
        return file_path
        
    except Exception as e:
        logger.error(f"Error saving essay to file: {str(e)}")
        raise HTTPException(status_code=500, detail="Error saving essay to file")

# async def generate_introduction(
#     client: OpenAI,
#     outline: EssayOutline,
#     context: Dict,
#     citation_tracker: CitationTracker
# ) -> str:
#     """Generate the introduction section"""
#     return await generate_section_content(
#         client,
#         outline.introduction.title,
#         outline.introduction.key_points,
#         outline.introduction.word_count,
#         "",
#         context,
#         citation_tracker
#     )

# async def generate_main_sections(
#     client: OpenAI,
#     outline: EssayOutline,
#     context: Dict,
#     previous_content: str,
#     citation_tracker: CitationTracker
# ) -> str:
#     """Generate all main sections of the essay"""
#     main_content = ""
#     for section in outline.main_sections:
#         section_content = await generate_section_content(
#             client,
#             section.title,
#             section.key_points,
#             section.word_count,
#             previous_content + main_content,
#             context,
#             citation_tracker
#         )
#         main_content += section_content
        
#         # Generate subsections if they exist
#         if section.subsections:
#             for subsection in section.subsections:
#                 subsection_content = await generate_section_content(
#                     client,
#                     subsection.title,
#                     subsection.key_points,
#                     math.ceil(section.word_count / len(section.subsections)),
#                     previous_content + main_content,
#                     context,
#                     citation_tracker
#                 )
#                 main_content += subsection_content
    
#     return main_content

# async def generate_conclusion(
#     client: OpenAI,
#     outline: EssayOutline,
#     context: Dict,
#     previous_content: str,
#     citation_tracker: CitationTracker
# ) -> str:
#     """Generate the conclusion section"""
#     return await generate_section_content(
#         client,
#         outline.conclusion.title,
#         outline.conclusion.key_points,
#         outline.conclusion.word_count,
#         previous_content,
#         context,
#         citation_tracker
#     )

# async def generate_references(
#     client: OpenAI,
#     outline: EssayOutline,
#     context: Dict,
#     citations: List[str]
# ) -> str:
#     """Generate the references section based on collected citations"""
#     if not outline.references_section:
#         return ""
        
#     prompt = f"""
#     Generate a references section based on the in-text citations used in the essay.
#     Format according to {outline.reference_style} style.
    
#     Citations used in the essay:
#     {json.dumps(citations, indent=2)}
    
#     Requirements:
#     1. Create full references for each unique citation
#     2. Format according to {outline.reference_style} guidelines
#     3. Sort references alphabetically
#     4. Include all necessary components (authors, year, title, etc.)
#     5. Return in HTML format with appropriate tags
    
#     Return the references in clean HTML format.
#     """
    
#     response = client.chat.completions.create(
#         model="gpt-4",
#         messages=[
#             {"role": "system", "content": "You are an academic writing assistant. Generate a properly formatted reference list."},
#             {"role": "user", "content": prompt}
#         ],
#         temperature=0.7
#     )
    
#     return response.choices[0].message.content

# async def generate_final_essay(
#     outline: EssayOutline,
#     answers: List[Answer]
# ) -> Tuple[str, str]:
#     """
#     Generate the final essay and save it to a file
#     Returns: Tuple of (essay_content, file_path)
#     """
#     try:
#         client = OpenAI(api_key=OPENAI_API_KEY)
#         citation_tracker = CitationTracker()
#         html_formatter = HTMLFormatter(outline)
        
#         # Prepare context
#         context = {
#             "writing_style": outline.writing_style,
#             "target_audience": outline.target_audience,
#             "reference_style": outline.reference_style,
#             "answers": {a.question_type: a.answer for a in answers}
#         }
        
#         # Generate content
#         introduction = await generate_introduction(client, outline, context, citation_tracker)
        
#         main_content = await generate_main_sections(
#             client,
#             outline,
#             context,
#             introduction,
#             citation_tracker
#         )
        
#         conclusion = await generate_conclusion(
#             client,
#             outline,
#             context,
#             introduction + main_content,
#             citation_tracker
#         )
        
#         references = await generate_references(
#             client,
#             outline,
#             context,
#             citation_tracker.get_all_citations()
#         )
        
#         # Format the essay in HTML
#         formatted_essay = html_formatter.format_essay(
#             introduction,
#             main_content,
#             conclusion,
#             references
#         )
        
#         # Save the essay to a file
#         file_path = await save_essay_to_file(formatted_essay, outline.title)
        
#         return formatted_essay
        
#     except Exception as e:
#         logger.error(f"Error generating essay: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Error generating essay: {str(e)}")


async def create_essay_outline(request: AnswersRequest) -> EssayOutline:
    """
    Create a detailed essay outline based on the answers and context provided
    """
    try:
        # Fetch the session document from MongoDB using session_id
        session_document = session_questions_collection.find_one({"session_id": request.session_id})

        if not session_document:
            raise HTTPException(status_code=404, detail="Session not found")

        # Extract instructions and file content from the document
        instructions = session_document.get("instructions", "")
        file_content = session_document.get("file_content", "")

        # Extract the topic and citation style from answers
        topic = next((answer.answer for answer in request.answers if answer.question_type == "topic"), "")
        citation_style = next((answer.answer for answer in request.answers if answer.question_type == "reference"), "apa7")

        # Use OpenAI to refine the topic if needed
        refined_topic = await refine_topic(request,instructions,file_content)

        # Fetch references from Springer
        references_response = await fetch_springer_articles(refined_topic)
        selected_references = references_response.references[:]  # Limit to top 5 references

        # Organize answers by question type
        answers_by_type = {}
        for answer in request.answers:
            answers_by_type[answer.question_type] = {
                'question': answer.question,
                'answer': answer.answer
            }
        
        # Construct prompt for OpenAI to generate outline
        prompt = f"""
        Create a detailed academic essay outline based on the following information:

        Essay Topic: {refined_topic}
        Essay Instructions: {instructions}
        
        Context from Questions and Answers:
        {json.dumps(answers_by_type, indent=2)}
        
        File Content Summary:
        {file_content[:500]}

        Create a comprehensive outline following this structure (respond in JSON format):
        {{
            "title": "Refined Essay Title",
            "target_audience": "Based on audience answer",
            "writing_style": "Based on style answer",
            "reference_style": "{citation_style}",
            "total_word_count": 2000,
            "introduction": {{
                "title": "Introduction",
                "key_points": ["Contextual background", "Thesis statement"],
                "word_count": 250
            }},
            "main_sections": [
                {{
                    "title": "First Main Topic",
                    "key_points": ["Key argument 1", "Supporting evidence"],
                    "subsections": [
                        {{
                            "title": "Detailed Subsection",
                            "key_points": ["Specific point", "Analysis"]
                        }}
                    ],
                    "word_count": 500
                }},
                {{
                    "title": "Second Main Topic",
                    "key_points": ["Key argument 2", "Comparative analysis"],
                    "word_count": 500
                }}
            ],
            "conclusion": {{
                "title": "Conclusion",
                "key_points": ["Summary of key points", "Future implications"],
                "word_count": 250
            }}
        }}

        Ensure:
        1. The outline reflects the essay's specific context
        2. Main sections are substantive and interconnected
        3. Key points are specific and actionable
        4. Word counts are distributed appropriately
        5. The structure supports a comprehensive exploration of the topic
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an academic writing assistant. Provide the outline in valid JSON format."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        # Parse and validate JSON response
        outline_content = json.loads(response.choices[0].message.content)
        
        # Convert to EssayOutline model
        outline = EssayOutline(**outline_content)
        
        return outline
    
    except Exception as e:
        logger.error(f"Error creating outline: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating outline")

async def refine_topic(request, instructions, file_content) -> str:
    """Refine the topic using OpenAI for better article search"""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an academic topic refinement assistant."},
                {"role": "user", "content": f"Analyse the given context or information from the user: {instructions} and {file_content}, and this {request}. Provide the expected topic name the user wants to discuss. Only the topic name, nothing else."}
            ],
            temperature=0.7
        )

        # Parse the response and extract the topic name
        response_content = response.choices[0].message.content.strip()
        # Split by basic keywords or whitespace to extract the core topic name
        topic_name = response_content.split(":")[0] if ":" in response_content else response_content
        #topic_name = topic_name.strip().split()  # Take the first keyword for reference
        return topic_name

    except Exception as e:
        logger.error(f"Error refining topic: {str(e)}")
        return "topic"

    
async def generate_final_essay(
    outline: EssayOutline,
    answers: List[Answer]
) -> str:
    """
    Generate the final essay and save it to a file
    Returns: Formatted essay content
    """
    try:
        # Fetch references dynamically
        references_response = await fetch_springer_articles(outline.title.split(":")[0])
        selected_references = references_response.references[:]  # Limit to top 5 references

        # Convert selected references to EssayReferenceObject
        essay_references = [
            EssayReferenceObject(
                AuthorName=ref.AuthorName, 
                TitleName=ref.TitleName, 
                Year=ref.Year, 
                Publisher=ref.Publisher
            ) for ref in selected_references
        ]

        # Generate references using the existing function
        references = await generate_references(
            essay_references, 
            outline.reference_style.lower()
        )
        
        # Generate content for each section
        context = {
            "writing_style": outline.writing_style,
            "target_audience": outline.target_audience,
            "reference_style": outline.reference_style,
        }

        # Use improved section generation functions
        introduction = await generate_section(
            client, 
            outline.introduction, 
            context, 
            selected_references
        )
        
        main_content = await generate_main_sections(
            client,
            outline.main_sections,
            context,
            selected_references
        )
        
        conclusion = await generate_section(
            client,
            outline.conclusion,
            context,
            selected_references
        )

        # Combine sections with proper formatting
        essay_content = f"""
        <h1>{outline.title}</h1>

        <h2>Introduction</h2>
        {introduction}

        <h2>Main Body</h2>
        {main_content}

        <h2>Conclusion</h2>
        {conclusion}

        <h2>References</h2>
        {references}
        """

        await save_essay_to_file(essay_content,outline.title)

        return essay_content
        
    except Exception as e:
        logger.error(f"Error generating essay: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating essay: {str(e)}")

async def generate_section(
    client: OpenAI,
    section: OutlineSection,
    context: Dict,
    references: List[ReferenceObject]
) -> str:
    """Generate content for a specific section"""
    try:
        ref_text = "\n".join([f"- {ref.AuthorName} ({ref.Year}): {ref.TitleName}" for ref in references])
        
        prompt = f"""
        Generate a word academic essay section.

        Section Title: {section.title}
        Key Points to Cover:
        {json.dumps(section.key_points, indent=2)}
        
        Context:
        Writing Style: {context.get('writing_style')}
        Target Audience: {context.get('target_audience')}
        Reference Style: {context.get('reference_style')}
        
        Available References:
        {ref_text}

        Requirements:
        1. Use academic language and tone
        2. Include in-text citations from the available references
        3. Ensure smooth paragraph transitions
        4. Cover all key points comprehensively
        5. Maintain the specified writing style
        6. Format as HTML paragraphs
        """
        
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an academic writing assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        # Convert content to paragraphs
        content = response.choices[0].message.content
        paragraphs = [f"<p>{p.strip()}</p>" for p in content.split('\n\n') if p.strip()]
        
        return "\n".join(paragraphs)
    
    except Exception as e:
        logger.error(f"Error generating section: {str(e)}")
        raise HTTPException(status_code=500, detail="Error generating section")

async def generate_main_sections(
    client: OpenAI,
    main_sections: List[OutlineSection],
    context: Dict,
    references: List[ReferenceObject]
) -> str:
    """Generate content for all main sections"""
    main_content = ""
    for section in main_sections:
        # Generate main section content
        section_content = await generate_section(
            client,
            section,
            context,
            references
        )
        
        # Add section title
        main_content += f"<h3>{section.title}</h3>\n{section_content}\n"
        
        # Generate subsections if they exist
        if section.subsections:
            for subsection in section.subsections:
                subsection_content = await generate_section(
                    client,
                    subsection,
                    context,
                    references
                )
                main_content += f"<h4>{subsection.title}</h4>\n{subsection_content}\n"
    
    return main_content