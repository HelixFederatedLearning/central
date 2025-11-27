from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..core.security import create_access_token

router = APIRouter()

class LoginReq(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(body: LoginReq):
    # MVP: hardcoded admin (replace with real IdP)
    if body.username == "admin" and body.password == "admin":
        return {"access_token": create_access_token("admin", "admin"), "token_type": "bearer"}
    raise HTTPException(401, "Invalid credentials")
