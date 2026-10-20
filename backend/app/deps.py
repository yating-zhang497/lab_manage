from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .security import find_user_by_token


def get_current_user(request: Request, db: Session = Depends(get_db)):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录")
    user = find_user_by_token(db, auth[len("Bearer ") :].strip())
    if user is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    return user


def require_admin(user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="请先修改初始密码后再操作")
    return user
