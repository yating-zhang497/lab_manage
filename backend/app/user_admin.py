"""用户管理CLI工具。

用法:
  # 创建管理员
  python -m app.user_admin create-admin <username> [password]

  # 重置用户密码
  python -m app.user_admin reset-password <username> [new_password]

  # 列出所有用户
  python -m app.user_admin list

  # 删除用户（谨慎使用）
  python -m app.user_admin delete <username>

示例:
  python -m app.user_admin create-admin newadmin123 MySecurePass123
  python -m app.user_admin reset-password admin mynewpassword
  python -m app.user_admin list
"""

import secrets
import sys
from typing import Optional

from sqlalchemy.orm import Session

from .database import Base, SessionLocal, engine
from .models import User
from .security import hash_password


def _get_db():
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def _generate_password(length: int = 12) -> str:
    """生成随机安全密码。"""
    return secrets.token_urlsafe(length)[:length]


def create_admin(username: str, password: Optional[str] = None) -> bool:
    """创建管理员账号。密码必须显式提供。"""
    if not password:
        print("错误: 创建管理员必须提供密码")
        print("用法: python -m app.user_admin create-admin <username> <password>")
        return False
    db = _get_db()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"用户 '{username}' 已存在（角色: {existing.role}）")
            if existing.role != "admin":
                existing.role = "admin"
                existing.must_change_password = True
                db.commit()
                print(f"已将 '{username}' 提升为管理员")
            return False

        db.add(User(
            username=username,
            password_hash=hash_password(password),
            role="admin",
            must_change_password=True,
        ))
        db.commit()
        print(f"✓ 管理员 '{username}' 创建成功")
        print(f"  首次登录后需修改密码")
        return True
    finally:
        db.close()


def reset_password(username: str, new_password: Optional[str] = None) -> bool:
    """重置用户密码。若未提供密码则自动生成随机密码。"""
    db = _get_db()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"错误: 用户 '{username}' 不存在")
            return False

        pwd = new_password or _generate_password()
        user.password_hash = hash_password(pwd)
        user.must_change_password = True
        user.login_fail_count = 0  # 重置登录失败计数
        user.login_locked_until = None
        db.commit()
        print(f"✓ 用户 '{username}' 密码已重置")
        if new_password:
            print(f"  新密码: {pwd}")
        else:
            print(f"  随机密码: {pwd}")
        print(f"  首次登录后需修改密码")
        return True
    finally:
        db.close()


def list_users() -> None:
    """列出所有用户。"""
    db = _get_db()
    try:
        users = db.query(User).all()
        if not users:
            print("暂无用户")
            return
        print(f"{'用户名':<20} {'角色':<10} {'首次登录需改密':<15}")
        print("-" * 50)
        for u in users:
            print(f"{u.username:<20} {u.role:<10} {'是' if u.must_change_password else '否':<15}")
    finally:
        db.close()


def delete_user(username: str) -> bool:
    """删除用户（不可恢复）。"""
    db = _get_db()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"错误: 用户 '{username}' 不存在")
            return False
        db.delete(user)
        db.commit()
        print(f"✓ 用户 '{username}' 已删除")
        return True
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "create-admin":
        if len(sys.argv) < 3:
            print("错误: 请提供用户名\n用法: python -m app.user_admin create-admin <username> [password]")
            sys.exit(1)
        username = sys.argv[2]
        password = sys.argv[3] if len(sys.argv) > 3 else None
        create_admin(username, password)

    elif cmd == "reset-password":
        if len(sys.argv) < 3:
            print("错误: 请提供用户名\n用法: python -m app.user_admin reset-password <username> [new_password]")
            sys.exit(1)
        username = sys.argv[2]
        password = sys.argv[3] if len(sys.argv) > 3 else None
        reset_password(username, password)

    elif cmd == "list":
        list_users()

    elif cmd == "delete":
        if len(sys.argv) < 3:
            print("错误: 请提供用户名\n用法: python -m app.user_admin delete <username>")
            sys.exit(1)
        username = sys.argv[2]
        confirm = input(f"确认删除用户 '{username}'？(y/N): ")
        if confirm.lower() == "y":
            delete_user(username)
        else:
            print("已取消")

    else:
        print(f"未知命令: {cmd}")
        print(__doc__)
        sys.exit(1)
