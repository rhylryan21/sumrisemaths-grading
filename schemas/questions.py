# services/grading/schemas/questions.py
from pydantic import BaseModel


class QuestionOut(BaseModel):
    id: str
    topic: str
    prompt: str
    type: str
