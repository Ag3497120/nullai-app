from pydantic import BaseModel
from typing import Optional

# --- Token ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: Optional[str] = None
    role: Optional[str] = None
    is_expert: bool = False
    orcid_id: Optional[str] = None
    display_name: Optional[str] = None

# --- User ---
class UserBase(BaseModel):
    email: str

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: str
    role: str

    class Config:
        from_attributes = True
