import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.create_admin import create_admin
from app.database import Base, get_db
from app.main import app
from app.models import User

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    db = TestSession()
    create_admin("admin", "admin", db=db, create_tables=False)
    db.close()
    yield


@pytest.fixture()
def client():
    return TestClient(app)


@pytest.fixture()
def admin_token(client):
    r = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin"},
    )
    assert r.status_code == 200
    # 清除强制改密标记，使后续写测试不受 require_admin 拦截
    db = TestSession()
    admin = db.query(User).filter(User.username == "admin").first()
    if admin:
        admin.must_change_password = False
    db.commit()
    db.close()
    return r.json()["token"]


@pytest.fixture()
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def make_person(client, auth, name="张三", uid="U0000001", **extra):
    body = {"name": name, "uid": uid, "degree_type": "博士", "status": "在读", **extra}
    r = client.post("/api/people", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def make_project(client, auth, name="测试项目", project_no="P0000001", **extra):
    body = {"name": name, "project_no": project_no, "category": "纵向", **extra}
    r = client.post("/api/projects", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()


def make_paper(client, auth, title="A Test Paper", **extra):
    body = {"title": title, "year": 2025, "venue": "Nature", **extra}
    r = client.post("/api/papers", json=body, headers=auth)
    assert r.status_code == 201, r.text
    return r.json()
