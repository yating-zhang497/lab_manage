from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginRequest, LoginResponse, UserOut
from ..security import (
    create_token,
    hash_password,
    revoke_token,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

LOGIN_FAIL_LIMIT = 5  # 连续失败次数上限
LOGIN_LOCK_MINUTES = 15  # 锁定时间（分钟）


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None:
        raise HTTPException(status_code=401, detail="账号或密码错误")

    # 检查是否被锁定
    if user.login_locked_until and user.login_locked_until > utcnow():
        remaining = int((user.login_locked_until - utcnow()).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=403,
            detail=f"账号已锁定，请 {remaining} 分钟后再试",
        )

    if not verify_password(body.password, user.password_hash):
        # 登录失败，增加计数
        user.login_fail_count += 1
        if user.login_fail_count >= LOGIN_FAIL_LIMIT:
            user.login_locked_until = utcnow() + timedelta(minutes=LOGIN_LOCK_MINUTES)
            db.commit()
            raise HTTPException(
                status_code=403,
                detail=f"连续 {LOGIN_FAIL_LIMIT} 次登录失败，账号已锁定 {LOGIN_LOCK_MINUTES} 分钟",
            )
        db.commit()
        raise HTTPException(status_code=401, detail="账号或密码错误")

    # 登录成功，重置失败计数
    user.login_fail_count = 0
    user.login_locked_until = None
    db.commit()

    token = create_token(db, user)
    return LoginResponse(
        token=token,
        username=user.username,
        role=user.role,
        must_change_password=user.must_change_password,
    )


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db), _=Depends(get_current_user)):
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        revoke_token(db, auth[len("Bearer ") :].strip())
    return {"ok": True}


@router.get("/me", response_model=UserOut)
def me(user=Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少8位")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    db.commit()
    return {"ok": True}
