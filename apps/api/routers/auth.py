"""Login + the get_current_user dependency."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from apps.api.core import security

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)


class LoginReq(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(req: LoginReq):
    users = security.load_users()
    u = users.get(req.username)
    if not u or not security.verify_password(req.password, u.get("password", "")):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = security.create_token(req.username, u.get("name", req.username), u.get("role", "user"))
    return {
        "access_token": token,
        "user": {"username": req.username, "name": u.get("name"), "role": u.get("role", "user")},
    }


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return security.decode_token(creds.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
