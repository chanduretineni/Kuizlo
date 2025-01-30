import os
import time
import re
from openai import OpenAI
import openai
from models.request_models import GenerateEssayRequest, GenerateEssayResponse, EssayReferenceObject
from config import OPENAI_API_KEY
import logging
from nltk.tokenize import sent_tokenize
from pymongo import MongoClient
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

mongo_client = MongoClient("mongodb+srv://chandu:6264@chanduretineni.zfbcc.mongodb.net/?retryWrites=true&w=majority&appName=ChanduRetineni")
db = mongo_client["Kuizlo"]
essays_collection = db["essays"]
session_questions_collection = db["session_questions"]

def format_citation_instruction(citation_style: str) -> str:
    """Generate specific citation formatting instructions based on the style."""
    citation_formats = {
        "apa7": "Use APA 7th edition format for in-text citations (Author, Year). For multiple authors, use '&' for two authors and 'et al.' for three or more.",
        "mla8": "Use MLA 8th edition format for in-text citations (Author page). Include author's last name and page number if available.",
        "harvard": "Use Harvard style in-text citations (Author, Year). For multiple authors, use 'and' for two authors and 'et al.' for three or more.",
        "vancouver": "Use Vancouver style numbered citations [1] in order of appearance.",
        "ieee": "Use IEEE style numbered citations [1] in order of appearance."
    }
    return citation_formats.get(citation_style.lower(), citation_formats["apa7"])


async def generate_text(prompt: str, target_words: int, tolerance: float = 0.15) -> str:
    """Generates text from a prompt, optimized for fewer OpenAI calls and paragraph preservation."""
    try:
        max_words = int(target_words * (1 + tolerance))
        min_words = int(target_words * (1 - tolerance))
        generated_text = ""
        total_sentences = []

        messages = [
            {"role": "system", "content": "You are a professional academic writer. Provide well-structured, coherent text with appropriate transitions and academic language. Use double line breaks to separate substantial paragraphs (at least 30 words each). Preserve section headings using ## for subheadings and ### for main headings."},
            {"role": "user", "content": prompt}
        ]

        while True:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=int(target_words * 1.5),  # Reduced max_tokens slightly
                temperature=0.7,
            )

            partial_text = response.choices[0].message.content
            generated_text += partial_text # directly append partial text for better continuity.
            
            # Extract paragraphs and filter short ones immediately
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n', generated_text) if p.strip()]
            filtered_paragraphs = [p for p in paragraphs if len(p.split()) >= 30]

            # Reconstruct the text from filtered paragraphs.
            generated_text = "\n\n".join(filtered_paragraphs)
            total_sentences = []
            for paragraph in filtered_paragraphs:
                total_sentences.extend(sent_tokenize(paragraph))
            
            current_word_count = len(generated_text.split())

            if current_word_count >= min_words:
                break

            if current_word_count < min_words and len(total_sentences)> 0:
                context = " ".join(total_sentences[-5:]) # Increased context window slightly
                continuation_prompt = f"""Continue the text below, maintaining the same writing style, tone, and academic rigor. Ensure each new paragraph is substantial (at least 30 words). Preserve existing section headings. Previous context: {context}"""

                messages = [
                    messages[0],
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": generated_text},
                    {"role": "user", "content": continuation_prompt}
                ]
            elif current_word_count < min_words and len(total_sentences) == 0:
                continuation_prompt = f"""Continue the text below, maintaining the same writing style, tone, and academic rigor. Ensure each new paragraph is substantial (at least 30 words). Preserve existing section headings."""
                messages = [
                    messages[0],
                    {"role": "user", "content": prompt},
                    {"role": "user", "content": continuation_prompt}
                ]

        # Final word count check and trimming (more efficient)
        final_words = generated_text.split()
        if len(final_words) > max_words:
            generated_text = " ".join(final_words[:max_words])

        logging.info(f"Generated text with {len(generated_text.split())} words (target: {target_words})")
        return generated_text

    except openai.OpenAIError as e:
        logging.error(f"OpenAI API Error: {e}")
        return f"Error: {e}"
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return f"An error occurred: {e}"


# Update the introduction generation prompt
async def generate_introduction(topic: str, references: list[EssayReferenceObject], target_words: int, citation_style: str) -> str:
    ref_text = "\n".join([f"- {ref.AuthorName} ({ref.Year}): {ref.TitleName}" for ref in references])
    citation_instruction = format_citation_instruction(citation_style)
    # Calculate words per paragraph based on total words
    paragraph_distribution = {
        'hook': int(target_words * 0.25),
        'context': int(target_words * 0.4),
        'thesis': int(target_words * 0.35)
    }
    
    prompt = f"""Write an academic essay introduction on "{topic}". Target length: {target_words} words.

Precise Paragraph Composition:
1. First Paragraph (Hook): {paragraph_distribution['hook']} words
   - Create a compelling opening that grabs reader's attention
   - Use a thought-provoking statement, statistic, or provocative question
   - Directly relate to the essay topic
   - Establish initial context
   - AVOID any concluding statements or phrases

2. Second Paragraph (Background Context): {paragraph_distribution['context']} words
   - Provide comprehensive background information
   - Use 2-3 citations from the provided references
   - Explain the historical, theoretical, or current landscape of the topic
   - Demonstrate scholarly understanding
   - AVOID summative or concluding language

3. Final Paragraph (Thesis and Direction): {paragraph_distribution['thesis']} words
   - Clearly state the research question or main argument
   - Outline the key points that will be explored in the body
   - Provide a roadmap for the essay's structure
   - End with a strong, precise thesis statement
   - EXPLICITLY AVOID any phrases like "in conclusion" or summary statements

Citation Requirements:
- {citation_instruction}
- Minimum 2-3 in-text citations from the following references:
{ref_text}

Formatting:
- Use double line breaks between paragraphs
- Each paragraph should be 100-150 words
- Ensure clear visual separation between paragraphs

Available references (use ONLY these):
{ref_text}

Additional guidelines:
- Maintain formal academic tone
- Ensure smooth transitions between paragraphs
- Don't include introduction heading
- Use specific examples/statistics from the references when possible
- Citations must be from the provided reference list only
- STRICTLY AVOID any concluding language or summary statements

Remember: Use double line breaks (two newline characters) between paragraphs for clear separation."""

    return await generate_text(prompt, target_words)

# Update the conclusion generation prompt
async def generate_conclusion(topic: str, references: list[EssayReferenceObject], target_words: int, citation_style: str) -> str:
    ref_text = "\n".join([f"- {ref.AuthorName} ({ref.Year}): {ref.TitleName}" for ref in references])
    citation_instruction = format_citation_instruction(citation_style)
    # Calculate words per paragraph based on total words
    paragraph_distribution = {
        'summary': int(target_words * 0.35),
        'implications': int(target_words * 0.35),
        'future_research': int(target_words * 0.3)
    }

    prompt = f"""Write a conclusion for an academic essay on "{topic}". Target length: {target_words} words.

Precise Paragraph Composition:
1. First Paragraph (Summary and Reaffirmation): {paragraph_distribution['summary']} words
   - Concisely restate the thesis
   - Summarize the key arguments presented in the body
   - Reflect on the main findings
   - Do NOT simply copy earlier text verbatim

2. Second Paragraph (Broader Implications): {paragraph_distribution['implications']} words
   - Discuss the wider significance of the research
   - Explain how the findings contribute to the broader field
   - Use 1-2 citations to support broader context
   - Connect the specific research to larger academic discourse

3. Final Paragraph (Future Directions): {paragraph_distribution['future_research']} words
   - Suggest potential avenues for future research
   - Highlight unanswered questions or limitations of current research
   - End with a forward-looking, thought-provoking statement
   - Demonstrate the ongoing relevance of the topic

Citation Requirements:
- {citation_instruction}
- Optional 1-2 citations from the following references:
{ref_text}

Formatting:
- Use double line breaks between paragraphs
- Each paragraph should be 100-150 words
- Ensure clear visual separation between paragraphs

Available references (use ONLY these):
{ref_text}

Additional guidelines:
- Don't introduce new arguments
- Connect back to the introduction
- Maintain academic tone
- Citations must be from the provided reference list only
- Don't include conclusion heading

Remember: Use double line breaks (two newline characters) between paragraphs for clear separation."""

    return await generate_text(prompt, target_words)
async def generate_references(references: list[EssayReferenceObject], citation_style: str) -> str:
    """Generate a list of references in the requested citation style."""
    try:
        citation_format = {
            "apa7": lambda ref: f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}. {ref.Publisher}.",
            "mla8": lambda ref: f"{ref.AuthorName}. \"{ref.TitleName}.\" {ref.Publisher}, {ref.Year}.",
            "harvard": lambda ref: f"{ref.AuthorName} ({ref.Year}) {ref.TitleName}. {ref.Publisher}.",
            "vancouver": lambda ref, idx: f"{idx}. {ref.AuthorName}. {ref.TitleName}. {ref.Publisher}; {ref.Year}.",
            "ieee": lambda ref, idx: f"[{idx}] {ref.AuthorName}, \"{ref.TitleName},\" {ref.Publisher}, {ref.Year}."
        }

        style = citation_style.lower()
        if style in ["vancouver", "ieee"]:
            formatted_refs = [citation_format[style](ref, idx) for idx, ref in enumerate(references, 1)]
        else:
            formatted_refs = [citation_format[style](ref) for ref in references]

        return "\n\n".join(sorted(formatted_refs))

    except Exception as e:
        logging.error(f"Error generating references: {e}")
        return f"Error generating references: {e}"

async def generate_body_paragraph(topic: str, references: list[EssayReferenceObject], target_words: int, target_total_words: int, citation_style: str) -> str:
    ref_text = "\n".join([f"- {ref.AuthorName} ({ref.Year}): {ref.TitleName}" for ref in references])
    citation_instruction = format_citation_instruction(citation_style)
    
    # Calculate number of main points based on total words
    num_main_points = max(3, min(7, target_total_words // 500))
    words_per_point = target_words // num_main_points
    
    prompt = f"""Write the body paragraphs for an academic essay on "{topic}". Target length: {target_words} words.

Structure requirements:
1. Present {num_main_points} distinct arguments as separate sections
2. Each section must:
   - Begin with a clear topic sentence introducing the main point
   - Provide evidence and examples with citations
   - End with a transition to the next point
   - AVOID any concluding or summary statements
   - AVOID using words like "in conclusion," "to summarize," "in summary"

Key constraints:
- DO NOT include any concluding sections or summaries
- DO NOT use "Conclusion" or "Summary" as subheadings
- DO NOT make statements about "overall findings" or "final thoughts"
- Each section should focus solely on its specific argument
- Leave all concluding thoughts for the separate conclusion section

Formatting requirements:
- Use double line breaks between sections
- Start each section with a descriptive subheading (in plain text)
- Ensure clear visual separation between sections

Citations: {citation_instruction}

Available references:
{ref_text}

Additional guidelines:
- Use appropriate transition phrases between sections
- Include counter-arguments where relevant
- Balance theoretical discussion with practical examples
- Citations must be from the provided reference list only
- Each section should focus on analyzing and supporting its main point
- Maintain academic tone throughout
- End each section by transitioning to the next topic, not by summarizing"""

    return await generate_text(prompt, target_words)

def process_essay(essay_text: str) -> str:
    """Process the raw essay text to structure it with clear HTML headings and subheadings."""
    # First, normalize line endings
    essay_text = essay_text.replace('\r\n', '\n')
    
    # Replace ### with <h3> (main headings)
    essay_text = re.sub(r"###\s*(.*)", r"<h3>\1</h3>", essay_text)
    
    # Replace ## with <h4> (subheadings)
    essay_text = re.sub(r"##\s*(.*)", r"<h4>\1</h4>", essay_text)
    
    # Replace ** with <h4> (alternative subheadings)
    essay_text = re.sub(r"\*\*\s*(.*?)\s*\*\*", r"<h4>\1</h4>", essay_text)
    
    # Split into paragraphs (handling both single and double line breaks)
    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', essay_text) if p.strip()]
    
    # Process each paragraph
    processed_paragraphs = []
    for p in paragraphs:
        if any(p.startswith(tag) for tag in ['<h3', '<h4']):
            processed_paragraphs.append(p)  # Don't wrap headings in <p> tags
        else:
            # Remove any remaining markdown-style headings within paragraphs
            p = re.sub(r'^##\s*', '', p)
            processed_paragraphs.append(f"<p>{p.strip()}</p>")
    
    # Join with proper spacing
    return "\n\n".join(processed_paragraphs)

async def generate_essay_logic(request: GenerateEssayRequest) -> GenerateEssayResponse:
    try:
        start_time = time.time()
        
        # Calculate section word counts
        intro_words = int(request.wordCount * 0.15)
        conclusion_words = int(request.wordCount * 0.15)
        body_words = request.wordCount - intro_words - conclusion_words

        # Generate each section
        introduction = await generate_introduction(
            request.topic, 
            request.selected_references, 
            intro_words,
            request.citationStyle
        )
        
        body = await generate_body_paragraph(
            request.topic, 
            request.selected_references, 
            body_words,
            request.wordCount,
            request.citationStyle
        )
        
        conclusion = await generate_conclusion(
            request.topic,
            request.selected_references,
            conclusion_words,
            request.citationStyle
        )

        references_section = await generate_references(
            request.selected_references, 
            request.citationStyle
        )

        # Combine sections
        essay_text = f"""### Introduction\n\n{introduction}\n\n
                        ### Body\n\n{body}\n\n
                        ### Conclusion\n\n{conclusion}\n\n
                        ### References\n\n{references_section}"""

        # Process and format essay
        processed_essay = process_essay(essay_text)

        # Save to file
        results_folder = "results"
        os.makedirs(results_folder, exist_ok=True)
        sanitized_topic = re.sub(r'[^\w\s-]', '', request.topic)
        file_name = os.path.join(results_folder, f"{sanitized_topic}_{int(time.time())}.html")
        
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(processed_essay)

        # Log completion
        end_time = time.time()
        execution_time = end_time - start_time
        word_count = len(processed_essay.split())
        logging.info(f"Essay generation completed in {execution_time:.2f} seconds. Word count: {word_count}")

        return GenerateEssayResponse(essay=processed_essay)
    except Exception as e:
        logging.error(f"Error in essay generation logic: {e}")
        return GenerateEssayResponse(essay=f"Error: {e}")