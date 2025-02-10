import io
import logging
import base64
from typing import  Tuple, List
from zipfile import ZipFile
import fitz  
import docx  
from openai import OpenAI
from fastapi import  HTTPException
from models.request_models import AnswerResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
import os
import re
import json
from datetime import datetime
from config import OPENAI_API_KEY


# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def encode_image_bytes(image_bytes: bytes) -> str:
    """
    Encodes image bytes into a Base64 string.
    """
    return base64.b64encode(image_bytes).decode("utf-8")


def answer_question(content: str, image: bytes = None, images: list = None) -> str:
    """
    Sends a request to the OpenAI API with the given text content and optional image(s).
    The payload uses a multi-modal format where the 'user' message's content is a list
    of items. Each item is either a text piece or an image (sent as a base64 data URL).
    """
    # Build the message content list.
    message_content = []
    if content:
        message_content.append({
            "type": "text",
            "text": content
        })
    if image:
        base64_image = encode_image_bytes(image)
        message_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
        })
    if images:
        for img in images:
            base64_img = encode_image_bytes(img)
            message_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
            })

    # Construct the payload with the system message and user message.
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": message_content},
        ]
    }

    try:
        response = client.chat.completions.create(**payload)
        # Adjust extraction if the response format is different.
        answer = response.choices[0].message.content
        return answer
    except Exception as e:
        raise Exception(f"OpenAI API error: {str(e)}")


async def extract_text_and_images(file_extension: str, file_io: io.BytesIO) -> Tuple[str, List[bytes]]:
    """
    Extract text and images from PDF or DOCX files.
    Returns a tuple: (extracted_text, list_of_image_bytes)
    """
    extracted_text = ""
    images = []

    if file_extension == 'pdf':
        try:
            file_io.seek(0)
            doc = fitz.open(stream=file_io, filetype="pdf")
            for page in doc:
                extracted_text += page.get_text() + "\n"
                image_list = page.get_images(full=True)
                for img in image_list:
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    # Convert image to PNG bytes.
                    if pix.n < 5:  # GRAY or RGB
                        img_bytes = pix.tobytes("png")
                    else:  # CMYK: convert to RGB first.
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                        img_bytes = pix.tobytes("png")
                    images.append(img_bytes)
            return extracted_text, images
        except Exception as e:
            logger.error(f"Error extracting PDF content: {str(e)}")
            raise HTTPException(status_code=500, detail="Error processing PDF file")

    elif file_extension == 'docx':
        try:
            file_io.seek(0)
            document = docx.Document(file_io)
            extracted_text = "\n".join([para.text for para in document.paragraphs])
            file_io.seek(0)
            with ZipFile(file_io) as docx_zip:
                # In DOCX, images are stored under the "word/media" folder.
                for file_name in docx_zip.namelist():
                    if file_name.startswith("word/media/"):
                        images.append(docx_zip.read(file_name))
            return extracted_text, images
        except Exception as e:
            logger.error(f"Error extracting DOCX content: {str(e)}")
            raise HTTPException(status_code=500, detail="Error processing DOCX file")
    else:
        raise HTTPException(status_code=400, detail="Unsupported file extension for extraction")



def create_pdf_from_response(answer: str, question_type: str = None) -> str:
    """
    Creates a PDF document from the API response with proper formatting.
    
    Args:
        answer (str): The response from the API
        question_type (str): Optional type of question (math, science, definition, etc.)
    
    Returns:
        str: Path to the generated PDF file
    """
    # Create results directory if it doesn't exist
    results_dir = "results"
    os.makedirs(results_dir, exist_ok=True)
    
    # Generate filename based on question type and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    question_type = question_type or "response"
    filename = f"{question_type}_{timestamp}_answer.pdf"
    filepath = os.path.join(results_dir, filename)
    
    # Create PDF document
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Create styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        alignment=1  # Center alignment
    )
    
    content_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=12,
        leading=14,
        spaceAfter=12
    )
    
    # Initialize story (content elements)
    story = []
    
    # Add title
    title = question_type.replace("_", " ").title()
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))
    
    # Process and format the answer
    try:
        # Check if the answer is a JSON string
        answer_dict = json.loads(answer) if isinstance(answer, str) and answer.strip().startswith("{") else {"answer": answer}
        
        # Extract the answer text
        answer_text = answer_dict.get("answer", answer)
        
        # Format LaTeX expressions
        # Replace \[ ... \] with styled paragraphs
        equations = re.split(r'(\\\[.*?\\\])', answer_text, flags=re.DOTALL)
        
        for part in equations:
            if part.strip():
                if part.startswith('\\[') and part.endswith('\\]'):
                    # Create centered equation style
                    equation_style = ParagraphStyle(
                        'Equation',
                        parent=styles['Normal'],
                        fontSize=12,
                        alignment=1,
                        spaceAfter=12,
                        spaceBefore=12
                    )
                    # Clean up LaTeX for PDF rendering
                    equation = part.replace('\\[', '').replace('\\]', '')
                    equation = equation.replace('\\', '')  # Remove LaTeX commands
                    story.append(Paragraph(equation, equation_style))
                else:
                    # Regular text paragraphs
                    paragraphs = part.split('\n')
                    for para in paragraphs:
                        if para.strip():
                            # Clean up inline LaTeX
                            para = re.sub(r'\\\(.*?\\\)', lambda m: m.group(0).replace('\\(', '').replace('\\)', ''), para)
                            story.append(Paragraph(para, content_style))
    
        # Build PDF
        doc.build(story)
        return filepath
        
    except Exception as e:
        # If any error occurs during JSON parsing or PDF creation, 
        # fall back to simple text rendering
        story.append(Paragraph(answer, content_style))
        doc.build(story)
        return filepath

def format_response_to_pdf(response: str, file_prefix: str = None) -> str:
    """
    Wrapper function to handle the PDF generation process.
    
    Args:
        response (str): The API response to format
        file_prefix (str): Optional prefix for the filename (e.g., 'math', 'science')
    
    Returns:
        str: Path to the generated PDF file
    """
    try:
        # Determine the type of content
        content_type = file_prefix or "general"
        if "\\[" in response or "\\(" in response:
            content_type = "math_problem"
        
        # Generate PDF
        pdf_path = create_pdf_from_response(response, content_type)
        return pdf_path
        
    except Exception as e:
        raise Exception(f"Error generating PDF: {str(e)}")
    

def clean_latex_formatting(text: str) -> str:
    """
    Removes LaTeX formatting from text while preserving line breaks and
    mathematical content.
    
    Args:
        text (str): Text containing LaTeX formatting
        
    Returns:
        str: Cleaned text with LaTeX formatting removed but structure preserved
    """
    # First, normalize newlines
    text = text.replace('\r\n', '\n')
    
    # Remove display math delimiters \[ \]
    cleaned_text = re.sub(r'\\\[(.*?)\\\]', r'\1', text, flags=re.DOTALL)
    
    # Remove inline math delimiters \( \)
    cleaned_text = re.sub(r'\\\((.*?)\\\)', r'\1', cleaned_text)
    
    # Remove common LaTeX commands while preserving the content
    latex_commands = [
        (r'\\frac\{(.*?)\}\{(.*?)\}', r'\1/\2'),  # Convert fractions to division
        (r'\\sqrt\{(.*?)\}', r'√(\1)'),           # Convert square root
        (r'\\cdot', r'×'),                        # Convert multiplication dot
        (r'\\times', r'×'),                       # Convert times symbol
        (r'\\div', r'÷'),                         # Convert division symbol
        (r'\\pm', r'±'),                          # Convert plus-minus symbol
        (r'\\leq', r'≤'),                         # Convert less than or equal
        (r'\\geq', r'≥'),                         # Convert greater than or equal
        (r'\\neq', r'≠'),                         # Convert not equal
        (r'\\alpha', r'α'),                       # Convert alpha
        (r'\\beta', r'β'),                        # Convert beta
        (r'\\theta', r'θ'),                       # Convert theta
        (r'\\pi', r'π'),                          # Convert pi
        (r'\\boxed\{(.*?)\}', r'\1'),            # Remove boxed command
    ]
    
    for pattern, replacement in latex_commands:
        cleaned_text = re.sub(pattern, replacement, cleaned_text)
    
    # Remove any remaining backslashes
    cleaned_text = cleaned_text.replace('\\', '')
    
    # Split into lines and clean each line while preserving structure
    lines = cleaned_text.split('\n')
    cleaned_lines = []
    
    previous_line_empty = False
    for line in lines:
        # Clean up horizontal whitespace
        cleaned_line = re.sub(r' +', ' ', line.strip())
        
        # Preserve single empty lines but collapse multiple empty lines
        if cleaned_line:
            cleaned_lines.append(cleaned_line)
            previous_line_empty = False
        elif not previous_line_empty:
            cleaned_lines.append('')
            previous_line_empty = True
    
    # Join lines with newlines
    return '\n'.join(cleaned_lines)