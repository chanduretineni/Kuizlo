import os
import time
import re
from openai import OpenAI
import openai
from models.request_models import GenerateEssayRequest, GenerateEssayResponse, Reference, ReferenceObject
from config import OPENAI_API_KEY
import logging
from nltk.tokenize import sent_tokenize
#any errors with nltk please download the punkt dataset by using below command in terminal.
# python -m nltk.downloader punkt_tab
client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



async def generate_text(prompt: str, target_words: int, tolerance: float = 0.15) -> str:
    try:
        max_words = int(target_words * (1 + tolerance))
        generated_text = ""
        sentences = []

        while len(generated_text.split()) < max_words:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(target_words * 1.5),
                temperature=0.7,
            )
            partial_text = response.choices[0].message.content
            sentences.extend(sent_tokenize(partial_text))
            generated_text = " ".join(sentences)

            # Break if the generated text is long enough
            if len(generated_text.split()) >= target_words:
                break

        # Adjust to the max_words limit while respecting sentence boundaries
        final_sentences = []
        word_count = 0
        for sentence in sentences:
            word_count += len(sentence.split())
            if word_count > max_words:
                break
            final_sentences.append(sentence)

        return " ".join(final_sentences)
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API Error: {e}")
        return f"Error: {e}"
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return f"An error occurred: {e}"


async def generate_introduction(topic: str, references: list[ReferenceObject], target_words, citation_style: str) -> str:
    ref_text = "\n".join([f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}." for ref in references])
    prompt = f"""Write an introduction for an essay on \"{topic}\". Aim for {target_words} words.
                    Include:
                    - A hook to grab the reader's attention.
                    - Background information providing context.
                    - A clear research question or problem statement.
                    - A concise thesis statement.
                    Use the following references (for context and in text citations):
                    {ref_text}, {citation_style}"""
    return await generate_text(prompt, target_words)

async def generate_body_paragraph(topic: str, references: list[ReferenceObject], target_words: int, target_total_words: int, citation_style: str) -> str:
    ref_text = "\n".join([f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}." for ref in references])
    prompt = f"""Write the body of an essay on \"{topic}\". Aim for {target_words} words. Use the following references (for context and in text citations): {ref_text} , {citation_style}
    The essay should be around {target_total_words} words."""
    return await generate_text(prompt, target_words)

async def generate_conclusion(thesis_statement: str, key_points: list[str], target_words: int,citation_style: str, implication: str = None) -> str:
    prompt = f"""Write a conclusion of approximately {target_words} words.
Restate the thesis (paraphrased): {thesis_statement}
Summarize these key points:
{chr(10).join([f'- {point}' for point in key_points])}"""
    if implication:
        prompt += f"\nDiscuss this implication or suggestion for future research: {implication} and include in text citations if required {citation_style}"
    return await generate_text(prompt, target_words)

async def generate_references(references: list[ReferenceObject], citation_style: str) -> str:
    """
    Generate a list of references in the requested citation style.

    :param references: List of ReferenceObject containing details of the references.
    :param citation_style: The citation style to use (e.g., APA7, MLA8, Harvard, Vancouver, IEEE).
    :return: A formatted string of references.
    """
    try:
        formatted_references = []

        for ref in references:
            if citation_style.lower() == "apa7":
                formatted_references.append(
                    f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}. {ref.Publisher}."
                )
            elif citation_style.lower() == "mla8":
                formatted_references.append(
                    f"{ref.AuthorName}. \"{ref.TitleName}.\" {ref.Publisher}, {ref.Year}."
                )
            elif citation_style.lower() == "harvard":
                formatted_references.append(
                    f"{ref.AuthorName} ({ref.Year}) {ref.TitleName}. {ref.Publisher}."
                )
            elif citation_style.lower() == "vancouver":
                formatted_references.append(
                    f"{ref.AuthorName}. {ref.TitleName}. {ref.Publisher}; {ref.Year}."
                )
            elif citation_style.lower() == "ieee":
                formatted_references.append(
                    f"{ref.AuthorName}, \"{ref.TitleName},\" {ref.Publisher}, {ref.Year}."
                )
            else:  # Default to APA7
                formatted_references.append(
                    f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}. {ref.Publisher}."
                )

        return "\n".join(formatted_references)

    except Exception as e:
        logging.error(f"Error generating references: {e}")
        return f"Error generating references: {e}"
    

def process_essay(essay_text: str) -> str:
    """
    Process the raw essay text to structure it with clear headings and subheadings.

    :param essay_text: The raw essay text with ### and ** used as markers.
    :return: A structured essay text with proper headings and subheadings.
    """
    # Replace ### with main headings
    essay_text = re.sub(r"###\s*(.*)", r"\n\n# \1\n", essay_text)

    # Replace ** with subheadings
    essay_text = re.sub(r"\*\*\s*(.*)\s*\*\*", r"\n## \1\n", essay_text)

    return essay_text



async def generate_essay_logic(request: GenerateEssayRequest):
    try:
        start_time = time.time()
        intro_words = int(request.wordCount * 0.15)
        conclusion_words = int(request.wordCount * 0.15)
        body_words = request.wordCount - intro_words - conclusion_words

        introduction = await generate_introduction(request.topic, request.selected_references, intro_words,request.citationStyle)
        body = await generate_body_paragraph(request.topic, request.selected_references, body_words, request.wordCount,request.citationStyle)
        conclusion = await generate_conclusion(request.topic, request.selected_references, conclusion_words,request.citationStyle)

        references_section = await generate_references(request.selected_references, request.citationStyle)

        # Combine components into raw essay text
        essay_text = f"### Introduction\n\n{introduction}\n\n### Body\n\n{body}\n\n### Conclusion\n\n{conclusion}\n\n### References\n\n{references_section}"

        # Process the essay text to structure it
        processed_essay = process_essay(essay_text)

        results_folder = "results"
        os.makedirs(results_folder, exist_ok=True)
        file_name = os.path.join(results_folder, f"{request.topic.replace(' ', '_')}.txt")
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(essay_text)

        end_time = time.time()
        execution_time = end_time - start_time
        logging.info(f"Essay generation executed in {execution_time:.2f} seconds for {len(essay_text.split())} words.")

        return GenerateEssayResponse(essay=essay_text, file_path=file_name)
    except Exception as e:
        logging.error(f"Error in essay generation logic: {e}")
        return GenerateEssayResponse(essay=f"Error: {e}", file_path=None)
