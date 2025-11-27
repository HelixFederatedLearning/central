from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from .settings import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")

class TokenData(BaseModel):
    sub: str
    role: str

def create_access_token(sub: str, role: str):
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": sub, "role": role, "exp": expire}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm="HS256")

def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        return TokenData(sub=payload["sub"], role=payload.get("role", "admin"))
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def require_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    if user.role not in ("admin", "operator"):  # both can operate
        raise HTTPException(403, "Forbidden")
    return user
