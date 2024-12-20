from pydantic import BaseModel
from typing import List

class QueryRequest(BaseModel):
    query: str

class Reference(BaseModel):
    id: str
    title: str
    author: str
    year: int

class GenerateEssayRequest(BaseModel):
    topic: str
    selected_references: List[Reference]
    intro_words: int = 300
    body_words: int = 2000
    conclusion_words: int = 300
    target_total_words: int = 2000

class GenerateEssayResponse(BaseModel):
    essay: str
    file_path: str

class HumanizeEssay(BaseModel):
    essay_txt : str
class HumanizeEssayResponse(BaseModel):
    humanized_essay : str
    provided_input : str