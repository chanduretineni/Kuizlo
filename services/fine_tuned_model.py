from openai import OpenAI
import openai
from config import OPENAI_API_KEY
import logging
from models.request_models import FineTuneModelResponse

client = OpenAI(api_key=OPENAI_API_KEY)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

fine_tuned_model_id = "ft:gpt-3.5-turbo-0613:V9ZlHzpWy3KQAhb6TgBcVyyR"


async def prompt_fine_tuned_model(prompt_text):
    try:
        response = client.chat.completions.create(
            model="ft:gpt-4o-2024-08-06:kuizlo::Am1frrxs",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": str(prompt_text)}
            ],
            max_tokens=150,  
            temperature=0.7   
        )
        
        essay_txt = response.choices[0].message.content
        return FineTuneModelResponse(model_output=essay_txt)
    
    except openai.OpenAIError as e:
        logging.error(f"OpenAI API Error: {e}")
        return f"Error: {e}"
    except Exception as e:
        logging.error(f"Unexpected Error: {e}")
        return f"An error occurred: {e}"
    
