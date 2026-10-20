"""创建初始管理员账号。

用法: python -m app.create_admin [username]
默认用户名 admin，初始密码与用户名相同，登录后应尽快修改。
"""

import sys
from typing import Optional

from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import User
from .security import hash_password


def create_admin(
    username: str,
    password: str,
    db: Optional[Session] = None,
    create_tables: bool = True,
) -> bool:
    """创建管理员，已存在则跳过。返回是否实际创建。"""
    if create_tables:
        Base.metadata.create_all(bind=engine)
    own_session = db is None
    if own_session:
        db = SessionLocal()
    try:
        if db.query(User).filter(User.username == username).first():
            print(f"用户 {username} 已存在，跳过创建")
            return False
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role="admin",
                must_change_password=True,
            )
        )
        db.commit()
        print(f"管理员 {username} 创建成功（初始密码与账号相同，请尽快修改）")
        return True
    finally:
        if own_session:
            db.close()


if __name__ == "__main__":
    uname = sys.argv[1] if len(sys.argv) > 1 else "admin"
    create_admin(uname, uname)
