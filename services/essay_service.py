import os
import time
import re
from openai import OpenAI
import openai
from models.request_models import GenerateEssayRequest, GenerateEssayResponse, EssayReferenceObject
from config import OPENAI_API_KEY
import logging
from nltk.tokenize import sent_tokenize
from services.essay_generation_with_instructions import save_essay_to_file
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

# async def generate_text(prompt: str, target_words: int, tolerance: float = 0.15) -> str:
#     """
#     Generate text while maintaining coherence for longer content.
    
#     Args:
#         prompt: The initial prompt for text generation
#         target_words: Desired word count
#         tolerance: Allowed deviation from target word count (e.g., 0.15 = ±15%)
    
#     Returns:
#         Generated text meeting the word count requirements
#     """
#     try:
#         max_words = int(target_words * (1 + tolerance))
#         min_words = int(target_words * (1 - tolerance))
#         generated_text = ""
#         sentences = []
        
#         # Initialize conversation with full context
#         messages = [
#             {"role": "system", "content": "You are a professional academic writer. Provide well-structured, coherent text with appropriate transitions and academic language."},
#             {"role": "user", "content": prompt}
#         ]

#         while True:
#             response = client.chat.completions.create(
#                 model="gpt-4",
#                 messages=messages,
#                 max_tokens=int(target_words * 2),  # Increased token limit for better context
#                 temperature=0.7,
#             )
            
#             partial_text = response.choices[0].message.content
#             current_sentences = sent_tokenize(partial_text)
#             sentences.extend(current_sentences)
#             generated_text = " ".join(sentences)
#             current_word_count = len(generated_text.split())
            
#             # Check if we've reached the target word count
#             if current_word_count >= min_words:
#                 break
                
#             # If we need more content, update the prompt for continuation
#             if current_word_count < min_words:
#                 # Get the last 2-3 sentences for context
#                 context = " ".join(sentences[-3:])
#                 continuation_prompt = f"""{prompt}

# Additional Continuation Instructions:
# - Continue the text coherently from the previous context
# - Maintain the exact same writing style, tone, and academic rigor
# - Use the same citation and structural guidelines from the original prompt
# - Previous context: {context}
# - Current word count: {current_word_count}
# - Target word count: {target_words}

# Continue writing to seamlessly reach the target word count while maintaining the original text's flow and academic standards."""
                
#                 messages = [
#                     messages[0],  # System message
#                     {"role": "user", "content": prompt},  # Original full prompt
#                     {"role": "assistant", "content": generated_text},  # Previous generated content
#                     {"role": "user", "content": continuation_prompt}  # Enhanced continuation prompt
#                 ]

#         # Trim excess content while maintaining coherence
#         final_sentences = []
#         word_count = 0
        
#         for sentence in sentences:
#             sentence_words = len(sentence.split())
#             if word_count + sentence_words > max_words:
#                 # Only add the sentence if we're further from target without it
#                 if abs(target_words - word_count) > abs(target_words - (word_count + sentence_words)):
#                     final_sentences.append(sentence     )
#                 break
#             final_sentences.append(sentence)
#             word_count += sentence_words

#         final_text = " ".join(final_sentences)
#         logging.info(f"Generated text with {len(final_text.split())} words (target: {target_words})")
#         return final_text

#     except openai.OpenAIError as e:
#         logging.error(f"OpenAI API Error: {e}")
#         return f"Error: {e}"
#     except Exception as e:
#         logging.error(f"Unexpected Error: {e}")
#         return f"An error occurred: {e}"

async def generate_text(prompt: str, target_words: int, tolerance: float = 0.15) -> str:
    try:
        max_words = int(target_words * (1 + tolerance))
        min_words = int(target_words * (1 - tolerance))
        generated_paragraphs = []
        total_sentences = []
        
        # Initialize conversation with full context
        messages = [
            {"role": "system", "content": "You are a professional academic writer. Provide well-structured, coherent text with appropriate transitions and academic language. Use double line breaks to separate paragraphs. Ensure each paragraph is substantial and meaningful. Preserve section headings."},
            {"role": "user", "content": prompt}
        ]

        while True:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                max_tokens=4000,
                temperature=0.7,
            )
            
            partial_text = response.choices[0].message.content
            
            # Preserve headings and split paragraphs
            sections = re.split(r'(\n*(?:##\s*.*\n+))', partial_text)
            processed_sections = []
            
            for i in range(0, len(sections), 2):
                # Add back the heading if it exists
                if i+1 < len(sections):
                    processed_sections.append(sections[i+1].strip())
                
                # Process paragraphs
                paragraphs = [p.strip() for p in re.split(r'\n\s*\n', sections[i]) if p.strip()]
                
                # Filter paragraphs, keeping those with at least 30 words
                filtered_paragraphs = []
                for paragraph in paragraphs:
                    if len(paragraph.split()) >= 30:
                        filtered_paragraphs.append(paragraph)
                        total_sentences.extend(sent_tokenize(paragraph))
                
                # Add filtered paragraphs
                if filtered_paragraphs:
                    processed_sections.append('\n\n'.join(filtered_paragraphs))
            
            # Join processed sections
            generated_text = '\n\n'.join(processed_sections)
            current_word_count = len(generated_text.split())
            
            # Check if we've reached the target word count
            if current_word_count >= min_words:
                break
                
            # If we need more content, update the prompt for continuation
            if current_word_count < min_words:
                context = " ".join(total_sentences[-3:])
                continuation_prompt = f"""{prompt}

Additional Continuation Instructions:
- Continue the text coherently from the previous context
- Maintain the exact same writing style, tone, and academic rigor
- Preserve existing section headings
- Ensure each new paragraph is substantial (at least 30 words)
- Previous context: {context}
- Current word count: {current_word_count}
- Target word count: {target_words}

Continue writing to seamlessly reach the target word count."""
                
                messages = [
                    messages[0],  # System message
                    {"role": "user", "content": prompt},  # Original full prompt
                    {"role": "assistant", "content": generated_text},  # Previous generated content
                    {"role": "user", "content": continuation_prompt}  # Enhanced continuation prompt
                ]

        # Trim excess content while maintaining coherence
        final_text = generated_text
        
        # Ensure we don't exceed max words
        words = final_text.split()
        if len(words) > max_words:
            final_text = " ".join(words[:max_words])
        
        logging.info(f"Generated text with {len(final_text.split())} words (target: {target_words})")
        return final_text

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