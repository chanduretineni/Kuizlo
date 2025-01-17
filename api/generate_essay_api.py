from fastapi import HTTPException
from models.request_models import GenerateEssayRequest, HumanizeEssay
from services.essay_service import generate_essay_logic
from services.humanize_essay import humanize_essay_logic

async def generate_essay(request: GenerateEssayRequest):
    try:
        return await generate_essay_logic(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def humanize_essay(request: HumanizeEssay):
    try:
        return humanize_essay_logic(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
async def generate_essay_with_instructions(request: GenerateEssayRequest):
    try:
        return await generate_essay__with_instruction_logic(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))