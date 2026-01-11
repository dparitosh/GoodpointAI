from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from core.auth import create_access_token, jwt_secret, verify_admin_credentials


router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/token")
async def token(form_data: OAuth2PasswordRequestForm = Depends()):
    if not jwt_secret():
        raise HTTPException(status_code=500, detail="JWT secret not configured")

    ok = verify_admin_credentials(form_data.username, form_data.password)
    if not ok:
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    access_token = create_access_token(subject=form_data.username, roles=["admin"], expires_in_minutes=120)
    return {"access_token": access_token, "token_type": "bearer"}
