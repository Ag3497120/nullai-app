from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from backend.app.database.session import get_db
from backend.app.schemas.auth import UserCreate, UserInDB, Token
from backend.app.services.auth_service import AuthService, get_auth_service
from backend.app.utils.jwt_utils import create_access_token

router = APIRouter()

@router.post("/signup", response_model=UserInDB)
def create_user(user: UserCreate, db: Session = Depends(get_db), auth_service: AuthService = Depends(get_auth_service)):
    """
    新規ユーザー登録
    """
    db_user = auth_service.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    created_user = auth_service.create_user(db=db, user=user)
    return UserInDB.from_orm(created_user)


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: Session = Depends(get_db), 
    auth_service: AuthService = Depends(get_auth_service)
):
    """
    ログインしてアクセストークンを取得
    """
    user = auth_service.authenticate_user(db, email=form_data.username, password=form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.id, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}
