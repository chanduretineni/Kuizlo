from pydantic import BaseModel,Field
from typing import List, Optional

class QueryRequest(BaseModel):
    title: str

# Updated Response Model
class ReferenceObject(BaseModel):
    AuthorName: str
    TitleName: str
    Year : str
    Publisher : str

class QueryResponse(BaseModel):
    references: List[ReferenceObject]


class Reference(BaseModel):
    id: str
    title: str
    author: str
    year: int

class GenerateEssayRequest(BaseModel):
    topic: str
    selected_references: List[ReferenceObject]
    citationStyle: str
    wordCount: int

class GenerateEssayResponse(BaseModel):
    essay: str

class HumanizeEssay(BaseModel):
    essay_txt : str

class HumanizeEssayResponse(BaseModel):
    humanized_essay : str
