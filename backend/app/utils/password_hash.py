from passlib.context import CryptContext

# bcryptアルゴリズムを使用してパスワードをハッシュ化
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def _truncate_password(password: str) -> str:
    """bcryptの72バイト制限に対応するためパスワードを切り詰める"""
    # UTF-8エンコードして72バイトに制限
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    return password_bytes.decode('utf-8', errors='ignore')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """平文のパスワードとハッシュ化されたパスワードを比較する"""
    truncated_password = _truncate_password(plain_password)
    return pwd_context.verify(truncated_password, hashed_password)

def get_password_hash(password: str) -> str:
    """パスワードをハッシュ化する"""
    truncated_password = _truncate_password(password)
    return pwd_context.hash(truncated_password)
