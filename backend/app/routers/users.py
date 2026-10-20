import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import User
from ..schemas import UserOut
from ..security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

SUPER_ADMIN = os.getenv("IM_SUPER_ADMIN", "admin")


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "readonly"


class UserUpdate(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None


class UserCreateOut(BaseModel):
    username: str
    must_change_password: bool = True


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _=Depends(require_admin)):
    users = db.query(User).order_by(User.id).all()
    return users


@router.post("", status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        must_change_password=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserCreateOut(username=user.username, must_change_password=True)


@router.put("/{username}", response_model=UserCreateOut)
def update_user(username: str, body: UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 禁止修改超级管理员的角色
    if username == SUPER_ADMIN and body.role is not None and body.role != "admin":
        raise HTTPException(status_code=403, detail="不能撤销超级管理员的权限")

    if body.password is not None:
        user.password_hash = hash_password(body.password)
        user.must_change_password = True
        user.login_fail_count = 0
        user.login_locked_until = None
    if body.role is not None:
        user.role = body.role
    db.commit()
    return UserCreateOut(username=user.username, must_change_password=user.must_change_password)


@router.delete("/{username}")
def delete_user(username: str, db: Session = Depends(get_db), _=Depends(require_admin)):
    if username == SUPER_ADMIN:
        raise HTTPException(status_code=403, detail="不能删除超级管理员账号")

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    db.delete(user)
    db.commit()
    return {"ok": True}
