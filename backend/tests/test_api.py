from conftest import TestSession, make_paper, make_person, make_project


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_login_wrong_password(client):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "wrong"}
    )
    assert r.status_code == 401


def test_requires_auth(client):
    assert client.get("/api/people").status_code == 401


def test_admin_flag_on_first_login(client):
    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin"}
    )
    assert r.json()["must_change_password"] is True


def test_person_crud_and_duplicate_uid(client, auth):
    p = make_person(client, auth, uid="admin")
    assert p["name"] == "张三"

    r = client.post(
        "/api/people", json={"name": "李四", "uid": "admin"}, headers=auth
    )
    assert r.status_code == 409

    r = client.put(
        f"/api/people/{p['id']}",
        json={"status": "毕业", "english_name": "Zhang, San"},
        headers=auth,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "毕业"
    assert r.json()["english_name"] == "Zhang, San"

    assert client.delete(f"/api/people/{p['id']}", headers=auth).status_code == 200
    assert client.get(f"/api/people/{p['id']}", headers=auth).status_code == 404


def test_person_uid_required(client, auth):
    r = client.post("/api/people", json={"name": "没有学号"}, headers=auth)
    assert r.status_code == 422


def test_project_no_required(client, auth):
    r = client.post("/api/projects", json={"name": "没有编号的项目"}, headers=auth)
    assert r.status_code == 422


def test_uid_scientific_notation_rejected(client, auth):
    r = client.post(
        "/api/people", json={"name": "王五", "uid": "2.0241e+09"}, headers=auth
    )
    assert r.status_code == 422


def test_project_member_and_paper_relations(client, auth):
    person = make_person(client, auth, uid="A001")
    project = make_project(client, auth, project_no="T2125006")
    paper = make_paper(
        client,
        auth,
        authors=[
            {
                "author_name": "Zhang, San",
                "person_id": person["id"],
                "seq": 1,
                "is_corresponding": True,
            }
        ],
        funding=[{"project_id": project["id"], "funding_no": "T2125006", "seq": 1}],
    )
    assert paper["authors"][0]["person_name"] == "张三"
    assert paper["funding"][0]["project_name"] == "测试项目"

    r = client.get(f"/api/people/{person['id']}/papers", headers=auth)
    assert r.status_code == 200
    assert r.json()[0]["title"] == "A Test Paper"

    r = client.get(f"/api/projects/{project['id']}/papers", headers=auth)
    assert r.json()[0]["funding_seq"] == 1

    r = client.get(f"/api/papers?person_id={person['id']}", headers=auth)
    assert len(r.json()) == 1
    r = client.get(f"/api/papers?project_id={project['id']}", headers=auth)
    assert len(r.json()) == 1
    r = client.get("/api/papers?person_id=99999", headers=auth)
    assert r.json() == []


def test_rematch_authors_links_unlinked(client, auth):
    """未关联的论文作者经 rematch-authors 后应按姓名/英文名(含变体)回填 person_id，
    之后按 person_id 筛选能查到该论文（修复人员-论文关联失效问题）。"""
    person = make_person(client, auth, uid="A002", english_name="Haohuan Fu")
    # 创建论文时作者不指定 person_id（保持未关联），署名顺序与英文名相反
    make_paper(
        client, auth, title="Rematch Test",
        authors=[{"author_name": "Fu, Haohuan", "seq": 1}],
    )
    # 未匹配前按该人员筛不到这篇论文
    assert client.get(f"/api/papers?person_id={person['id']}", headers=auth).json() == []

    r = client.post("/api/papers/rematch-authors", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["matched"] == 1

    # 回填后按 person_id 能筛到
    rows = client.get(f"/api/papers?person_id={person['id']}", headers=auth).json()
    assert any(p["title"] == "Rematch Test" for p in rows)


def test_auto_match_pdfs_links_unlinked(client, auth):
    """未关联的论文库 PDF 经 auto-match 后应按文件名匹配并回填 paper_id。"""
    from conftest import TestSession
    from app.models import Attachment

    paper = make_paper(client, auth, title="Deep Learning for Weather")
    # 直接插入一个未关联的 PDF 记录（文件名含论文标题），paper_id=None
    db = TestSession()
    att = Attachment(
        att_type="pdf",
        filename="Deep Learning for Weather.pdf",
        store_path="/tmp/dl_weather.pdf",
        sha256="abc",
        size=10,
        paper_id=None,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    aid = att.id
    db.close()

    # 未匹配前 PDF 未关联论文
    assert client.get(f"/api/pdfs/{aid}", headers=auth).json()["paper_id"] is None

    r = client.post("/api/pdfs/auto-match", json={}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["matched"] == 1

    # 回填后已关联到该论文
    pdf = client.get(f"/api/pdfs/{aid}", headers=auth).json()
    assert pdf["paper_id"] == paper["id"]


def test_paper_title_unique(client, auth):
    make_paper(client, auth, title="Deep Learning for HPC")
    r = client.post("/api/papers", json={"title": "deep learning for HPC!"}, headers=auth)
    assert r.status_code == 409


def test_batch_download_pdfs_not_shadowed(client, auth):
    """文献库批量下载不应 422：/batch-download 字面路由若被 /{attachment_id}(int) 遮蔽，
    带有效 token 时会因 int("batch-download") 失败返回 422。"""
    r = client.get("/api/pdfs/batch-download?ids=999999", headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"


def test_award_records(client, auth):
    p1 = make_person(client, auth, name="张金潇", uid="B001")
    p2 = make_person(client, auth, name="许蕴朴", uid="B002")
    r = client.post(
        "/api/awards",
        json={
            "award_name": "第12届全国并行应用挑战赛（PAC）应用赛道特等奖",
            "level": "特等奖",
            "recipients": [
                {"seq": 1, "recipient_name": "张金潇", "person_id": p1["id"]},
                {"seq": 2, "recipient_name": "许蕴朴", "person_id": p2["id"]},
            ],
        },
        headers=auth,
    )
    assert r.status_code == 201, r.text
    award = r.json()
    assert len(award["recipients"]) == 2
    # 按人员筛选
    r = client.get(f"/api/awards?person_id={p1['id']}", headers=auth)
    assert len(r.json()) == 1
    # 人员详情的获奖列表
    r = client.get(f"/api/people/{p1['id']}/awards", headers=auth)
    assert len(r.json()) == 1


def test_ip_patent_flow(client, auth):
    person = make_person(client, auth, uid="C001")
    project = make_project(client, auth, project_no="KC001")
    body = {
        "ip_type": "patent",
        "title": "一种测试方法",
        "inventors": [
            {
                "inventor_name": "Zhang, San",
                "person_id": person["id"],
                "seq": 1,
                "is_first": True,
            }
        ],
        "funding": [{"project_id": project["id"], "funding_no": "KC001"}],
    }
    r = client.post("/api/ip", json=body, headers=auth)
    assert r.status_code == 201, r.text
    ip = r.json()
    assert ip["inventors"][0]["person_name"] == "张三"

    r = client.post(
        "/api/ip",
        json={"ip_type": "patent", "title": "一种测试方法"},
        headers=auth,
    )
    assert r.status_code == 409  # 产权名称为唯一标识

    r = client.get("/api/ip?ip_type=patent", headers=auth)
    assert len(r.json()) == 1


def test_ip_title_required(client, auth):
    r = client.post("/api/ip", json={"ip_type": "software_copyright"}, headers=auth)
    assert r.status_code == 422
    r = client.post(
        "/api/ip", json={"ip_type": "other", "title": "某集成电路布图V1.0"}, headers=auth
    )
    assert r.status_code == 201


def test_ip_inventor_auto_match_and_rematch(client, auth):
    make_person(client, auth, name="王五", uid="C100", english_name="Wang, Wu")
    # 新增时发明人按中文名/英文名自动匹配
    r = client.post(
        "/api/ip",
        json={
            "ip_type": "patent",
            "title": "自动匹配测试专利",
            "inventors": [
                {"inventor_name": "王五", "seq": 1, "is_first": True},
                {"inventor_name": "Wang, Wu", "seq": 2},
                {"inventor_name": "赵七", "seq": 3},
            ],
        },
        headers=auth,
    )
    assert r.status_code == 201, r.text
    inv = r.json()["inventors"]
    assert inv[0]["person_id"] is not None
    assert inv[1]["person_id"] is not None
    assert inv[2]["person_id"] is None  # 入库时人员尚不存在

    # 之后人员库补充了该人员 → 重新匹配可补齐
    make_person(client, auth, name="赵七", uid="C200")
    rr = client.post("/api/ip/rematch-inventors", headers=auth)
    assert rr.status_code == 200, rr.text
    assert rr.json()["matched"] == 1
    detail = client.get(f"/api/ip/{r.json()['id']}", headers=auth).json()
    assert all(v["person_id"] for v in detail["inventors"])


def test_readonly_role_cannot_write(client, auth):
    from app.models import User
    from app.security import hash_password

    db = TestSession()
    db.add(
        User(username="viewer", password_hash=hash_password("viewer"), role="readonly")
    )
    db.commit()
    db.close()

    r = client.post("/api/auth/login", json={"username": "viewer", "password": "viewer"})
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/api/people", headers=headers).status_code == 200
    assert (
        client.post("/api/people", json={"name": "禁止"}, headers=headers).status_code
        == 403
    )


def test_logout_invalidates_token(client, auth):
    assert client.get("/api/people", headers=auth).status_code == 200
    assert client.post("/api/auth/logout", headers=auth).status_code == 200
    assert client.get("/api/people", headers=auth).status_code == 401


def test_change_password(client):
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "admin", "new_password": "brand-new-pass-123"},
        headers={"Authorization": "Bearer bad"},
    )
    assert r.status_code == 401

    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin"}
    )
    headers = {"Authorization": f"Bearer {r.json()['token']}"}
    r = client.post(
        "/api/auth/change-password",
        json={"old_password": "admin", "new_password": "brand-new-pass-123"},
        headers=headers,
    )
    assert r.status_code == 200, r.text

    r = client.post(
        "/api/auth/login", json={"username": "admin", "password": "brand-new-pass-123"}
    )
    assert r.status_code == 200
    assert r.json()["must_change_password"] is False
