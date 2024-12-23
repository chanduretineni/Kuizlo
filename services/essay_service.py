import os
import time
from openai import OpenAI
import openai
from models.request_models import GenerateEssayRequest, GenerateEssayResponse, Reference, ReferenceObject
from config import OPENAI_API_KEY
import logging

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def generate_text(prompt: str, target_words: int, tolerance: float = 0.15) -> str:
    try:
        max_words = int(target_words * (1 + tolerance))
        generated_text = ""
        while len(generated_text.split()) < max_words:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(target_words * 1.5),
                temperature=0.7,
            )
            generated_text += response.choices[0].message.content
            if len(generated_text.split()) >= target_words:
                break
        return " ".join(generated_text.split()[:max_words])
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API Error: {e}")
        return f"Error: {e}"
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return f"An error occurred: {e}"

async def generate_introduction(topic: str, references: list[ReferenceObject], target_words: int = 200) -> str:
    ref_text = "\n".join([f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}." for ref in references])
    prompt = f"""Write an introduction for an essay on \"{topic}\". Aim for {target_words} words.
                    Include:
                    - A hook to grab the reader's attention.
                    - Background information providing context.
                    - A clear research question or problem statement.
                    - A concise thesis statement.
                    Use the following references (for context and later citations):
                    {ref_text}"""
    return await generate_text(prompt, target_words)

async def generate_body_paragraph(topic: str, references: list[ReferenceObject], target_words: int, target_total_words: int) -> str:
    ref_text = "\n".join([f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}." for ref in references])
    prompt = f"""Write the body of an essay on \"{topic}\". Aim for {target_words} words. Use the following references (for context and later citations): {ref_text}
    The essay should be around {target_total_words} words."""
    return await generate_text(prompt, target_words)

async def generate_conclusion(thesis_statement: str, key_points: list[str], target_words: int, implication: str = None) -> str:
    prompt = f"""Write a conclusion of approximately {target_words} words.
Restate the thesis (paraphrased): {thesis_statement}
Summarize these key points:
{chr(10).join([f'- {point}' for point in key_points])}"""
    if implication:
        prompt += f"\nDiscuss this implication or suggestion for future research: {implication}"
    return await generate_text(prompt, target_words)

async def generate_essay_logic(request: GenerateEssayRequest):
    try:
        start_time = time.time()
        intro_words = int(request.wordCount * 0.15)
        conclusion_words = int(request.wordCount * 0.15)
        body_words = request.wordCount - intro_words - conclusion_words

        introduction = await generate_introduction(request.topic, request.selected_references, intro_words)
        body = await generate_body_paragraph(request.topic, request.selected_references, body_words, request.wordCount)
        conclusion = await generate_conclusion(request.topic, request.selected_references, conclusion_words)

        essay_text = f"{introduction}\n\n{body}\n\n{conclusion}"

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
