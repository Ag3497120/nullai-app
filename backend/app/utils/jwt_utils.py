from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from backend.app.config import settings
from backend.app.schemas.auth import TokenData

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """JWTアクセストークンを生成する"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[TokenData]:
    """JWTトークンを検証し、ペイロードを返す"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None:
            return None
        return TokenData(
            user_id=user_id,
            role=role,
            is_expert=payload.get("is_expert", False),
            orcid_id=payload.get("orcid_id"),
            display_name=payload.get("display_name")
        )
    except JWTError:
        return None
