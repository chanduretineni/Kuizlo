from pydantic import BaseModel,Field
from typing import List, Optional

class QueryRequest(BaseModel):
    title: str

# Updated Response Model
class ReferenceObject(BaseModel):
    AuthorName: str
    TitleName: str
    Year : str

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
    intro_words: Optional[int] = Field(default=300, description="Word count for the introduction")
    body_words: Optional[int] = Field(default=2000, description="Word count for the body")
    conclusion_words: Optional[int] = Field(default=300, description="Word count for the conclusion")

class GenerateEssayResponse(BaseModel):
    essay: str

class HumanizeEssay(BaseModel):
    essay_txt : str

class HumanizeEssayResponse(BaseModel):
    humanized_essay : str
