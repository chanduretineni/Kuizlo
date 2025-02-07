# from fastapi import HTTPException
# from models.request_models import FineTuneModelRequest
# from services.fine_tuned_model import prompt_fine_tuned_model

# async def fine_tune_request(request: FineTuneModelRequest):
#     try:
#         return await prompt_fine_tuned_model(request.prompt_text, request.topic)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))