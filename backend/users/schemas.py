from pydantic import BaseModel
""" Формат входных и выходных данных API """

class UserCreate(BaseModel):
    """ DTO """
    name: str
    email: str

class UserResponse(BaseModel):
    """ DTO """
    id: int
    name: str
    email: str

    model_config = {
        "from_attributes": True
    }