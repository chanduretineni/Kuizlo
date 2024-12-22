import os
from openai import OpenAI
import openai
from models.request_models import GenerateEssayRequest, GenerateEssayResponse, Reference, ReferenceObject
from config import OPENAI_API_KEY
import logging

client = OpenAI(api_key=OPENAI_API_KEY)

# async def generate_essay_logic(request: GenerateEssayRequest):
#     references_text = "\n".join(
#         [f"{ref.id}: {ref.author} ({ref.year}). {ref.title}." for ref in request.selected_references]
#     )

#     # Base prompt for GPT
#     base_prompt = f"""
#     Write a detailed 2000-word essay on the topic: "{request.topic}". 
#     Use the following references for your citations in APA format:

#     References:
#     {references_text}

#     - Include in-text citations (e.g., Author, Year) that correspond to the provided references.
#     - End the essay with a properly formatted References section based on the APA style.
#     - Format the essay into clear paragraphs. Each paragraph should be focused on one idea, ensuring that the essay reads smoothly and is easy to follow.
#     """

#     essay_parts = []
#     max_tokens_per_request = 750
#     generated_word_count = 0
#     target_word_count = 2000

#     # Generate essay iteratively
#     while generated_word_count < target_word_count:
#         continuation_prompt = base_prompt + "\n\nContinue from the last paragraph:\n" + "\n".join(essay_parts[-1:])
#         response = client.chat.completions.create(model="gpt-4o-mini",
#         messages=[
#             {"role": "system", "content": "You are an expert academic writer."},
#             {"role": "user", "content": continuation_prompt}
#         ],
#         temperature=0.7,
#         max_tokens=max_tokens_per_request)
#         part = response.choices[0].message.content
#         essay_parts.append(part)
#         generated_word_count = sum(len(p.split()) for p in essay_parts)

#     # Finalize the essay text
#     essay_text = " ".join(essay_parts)
#     essay_text = " ".join(essay_text.split()[:target_word_count])

#     # Save the essay to a file
#     results_folder = "results"
#     os.makedirs(results_folder, exist_ok=True)
#     file_name = os.path.join(results_folder, f"{request.topic.replace(' ', '_')}.txt")
#     with open(file_name, "w", encoding="utf-8") as file:
#         file.write(essay_text)

#     return GenerateEssayResponse(essay=essay_text, file_path=file_name)


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def generate_introduction(topic: str, references: list[ReferenceObject], target_words: int = 200) -> str:
    try:
        generated_word_count = 0
        introduction = ""
        while generated_word_count < target_words:
            ref_text = "\n".join([f"{ref.AuthorName} ({ref.Year}). {ref.TitleName}." for ref in references])
            prompt = f"""Write an introduction for an essay on \"{topic}\". Aim for {target_words} words.
                            Include:
                            - A hook to grab the reader's attention.
                            - Background information providing context.
                            - A clear research question or problem statement.
                            - A concise thesis statement.
                            Use the following references (for context and later citations):
                            {ref_text}"""
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(target_words * 1.5),
                temperature=0.7
            )
            generated_text = response.choices[0].message.content
            introduction += generated_text
            generated_word_count = len(introduction.split())
        return introduction
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API Error in introduction: {e}")
        return f"Error generating introduction: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred in introduction: {e}")
        return f"An unexpected error occurred in introduction: {e}"


async def generate_body_paragraph(topic: str, references: list[Reference], target_words: int, target_total_words: int, generated_words: int) -> str:
    try:
        generated_word_count = 0
        body_paragraph = ""
        while generated_word_count < target_words:
            ref_text = "\n".join([f"{ref.id}: {ref.author} ({ref.year}). {ref.title}." for ref in references])
            prompt = f"""Write the body of an essay on \"{topic}\". Aim for {target_words} words. Use the following references (for context and later citations): {ref_text}
            The essay should be around {target_total_words} words. Currently around {generated_words} words are generated. 
            Do not write introduction or conclusion. Just focus on the body of the essay."""
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(target_words * 1.5),
                temperature=0.7
            )
            generated_text = response.choices[0].message.content
            body_paragraph += generated_text
            generated_word_count = len(body_paragraph.split())
        return body_paragraph
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API Error in body paragraph: {e}")
        return f"Error generating body paragraph: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred in body paragraph: {e}")
        return f"An unexpected error occurred in body paragraph: {e}"


async def generate_conclusion(thesis_statement: str, key_points: list[str], implication: str = None, target_words: int = 200) -> str:
    try:
        generated_word_count = 0
        conclusion = ""
        while generated_word_count < target_words:
            prompt = f"""Write a conclusion of approximately {target_words} words.
Restate the thesis (paraphrased): {thesis_statement}
Summarize these key points:
{chr(10).join([f'- {point}' for point in key_points])}"""

            if implication:
                prompt += f"Discuss this implication or suggestion for future research: {implication}"

            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=int(target_words * 1.5),
                temperature=0.7
            )
            generated_text = response.choices[0].message.content
            conclusion += generated_text
            generated_word_count = len(conclusion.split())
        return conclusion
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API Error in conclusion: {e}")
        return f"Error generating conclusion: {e}"
    except Exception as e:
        logging.error(f"An unexpected error occurred in conclusion: {e}")
        return f"An unexpected error occurred in conclusion: {e}"

async def generate_essay_logic(request: GenerateEssayRequest):
    try:
        introduction = await generate_introduction(request.topic, request.selected_references, request.intro_words)
        generated_words = len(introduction.split())

        body = await generate_body_paragraph(request.topic, request.selected_references, request.body_words, request.wordCount, generated_words)
        generated_words += len(body.split())

        conclusion = await generate_conclusion(request.topic, request.selected_references, request.conclusion_words)
        generated_words += len(conclusion.split())

        essay_text = f"{introduction}\n\n{body}\n\n{conclusion}"

        results_folder = "results"
        os.makedirs(results_folder, exist_ok=True)
        file_name = os.path.join(results_folder, f"{request.topic.replace(' ', '_')}.txt")
        with open(file_name, "w", encoding="utf-8") as file:
            file.write(essay_text)

        return GenerateEssayResponse(essay=essay_text, file_path=file_name)

    except Exception as e:
        logging.error(f"An error occurred in essay generation: {e}")
        return GenerateEssayResponse(essay=f"An error occurred during essay generation: {e}", file_path=None)