"""行内附件（projects/people/ip/awards）路由测试。"""

import io
import zipfile

from conftest import TestSession, make_person, make_project

from app.models import User
from app.security import create_token, hash_password


def make_simple_pdf(text: str) -> bytes:
    content = f"BT /F1 12 Tf 50 700 Td ({text}) Tj ET".encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n"
    out += str(xref_pos).encode() + b"\n%%EOF"
    return out


def readonly_auth():
    """创建一个 readonly 用户并返回其 auth headers。"""
    db = TestSession()
    u = User(username="reader", password_hash=hash_password("pw"), role="readonly")
    db.add(u)
    db.commit()
    db.refresh(u)
    token = create_token(db, u)
    db.close()
    return {"Authorization": f"Bearer {token}"}


def _upload(client, auth, entity, entity_id, files):
    return client.post(
        f"/api/attachments/{entity}/{entity_id}",
        files=files,
        headers=auth,
    )


def test_upload_list_download_delete(client, auth):
    proj = make_project(client, auth)
    pid = proj["id"]
    pdf1, pdf2 = make_simple_pdf("hello"), make_simple_pdf("world")

    r = _upload(
        client, auth, "projects", pid,
        [("files", ("contract_a.pdf", pdf1, "application/pdf")),
         ("files", ("contract_b.pdf", pdf2, "application/pdf"))],
    )
    assert r.status_code == 200, r.text
    assert [f["status"] for f in r.json()["files"]] == ["ok", "ok"]

    # list
    r = client.get(f"/api/attachments/projects/{pid}", headers=auth)
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 2
    assert all(x["entity_type"] == "projects" and x["entity_id"] == pid for x in rows)

    aid = rows[0]["id"]

    # serve file
    r = client.get(f"/api/attachments/{aid}/file", headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")

    # delete one
    r = client.delete(f"/api/attachments/{aid}", headers=auth)
    assert r.status_code == 200
    r = client.get(f"/api/attachments/projects/{pid}", headers=auth)
    assert len(r.json()) == 1


def test_download_by_records_zip(client, auth):
    p1 = make_project(client, auth, name="项目甲", project_no="P001")
    p2 = make_project(client, auth, name="项目乙", project_no="P002")
    _upload(client, auth, "projects", p1["id"],
            [("files", ("a.pdf", make_simple_pdf("a"), "application/pdf"))])
    _upload(client, auth, "projects", p2["id"],
            [("files", ("b.pdf", make_simple_pdf("b"), "application/pdf"))])

    r = client.post(
        "/api/attachments/download-by-records",
        json={"entity": "projects", "ids": [p1["id"], p2["id"]]},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    names = zf.namelist()
    assert len(names) == 2
    # 按记录名分文件夹
    assert any(n.startswith("项目甲/") for n in names)
    assert any(n.startswith("项目乙/") for n in names)


def test_batch_download_by_ids(client, auth):
    proj = make_project(client, auth)
    r = _upload(client, auth, "projects", proj["id"],
                [("files", ("a.pdf", make_simple_pdf("a"), "application/pdf")),
                 ("files", ("b.pdf", make_simple_pdf("b"), "application/pdf"))])
    ids = [f["attachment_id"] for f in r.json()["files"]]
    r = client.post("/api/attachments/batch-download", json={"attachment_ids": ids}, headers=auth)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    assert len(zf.namelist()) == 2


def test_isolation_from_papers_library(client, auth):
    """实体附件不应出现在论文 PDF 库列表里。"""
    proj = make_project(client, auth)
    _upload(client, auth, "projects", proj["id"],
            [("files", ("entity_only.pdf", make_simple_pdf("x"), "application/pdf"))])
    r = client.get("/api/pdfs", headers=auth)
    assert r.status_code == 200
    assert all(row["filename"] != "entity_only.pdf" for row in r.json()["rows"])


def test_pdf_statuses_filter(client, auth):
    """?statuses=unmatched 只返回未关联论文的 PDF；?statuses=matched 只返回已关联的。"""
    from app.models import Attachment
    from conftest import make_paper

    paper = make_paper(client, auth, title="滤波测试论文")
    db = TestSession()
    db.add(Attachment(att_type="pdf", filename="linked.pdf", store_path="/tmp/linked.pdf",
                     sha256="aaa", size=10, paper_id=paper["id"]))
    db.add(Attachment(att_type="pdf", filename="orphan.pdf", store_path="/tmp/orphan.pdf",
                     sha256="bbb", size=10, paper_id=None))
    db.commit()
    db.close()

    # 不带筛选：两条都在
    all_rows = client.get("/api/pdfs", headers=auth).json()["rows"]
    names = {r["filename"] for r in all_rows}
    assert {"linked.pdf", "orphan.pdf"} <= names

    # 未关联筛选：只剩 orphan
    unmatched = client.get("/api/pdfs?statuses=unmatched", headers=auth).json()["rows"]
    assert [r["filename"] for r in unmatched] == ["orphan.pdf"]
    assert all(r["paper_id"] is None for r in unmatched)

    # 已关联筛选：只剩 linked
    matched = client.get("/api/pdfs?statuses=matched", headers=auth).json()["rows"]
    assert [r["filename"] for r in matched] == ["linked.pdf"]
    assert all(r["paper_id"] is not None for r in matched)

    # 多值同时传（重复键，前端数组序列化后的形态）
    both = client.get("/api/pdfs?statuses=unmatched&statuses=matched", headers=auth).json()["rows"]
    assert {r["filename"] for r in both} == {"linked.pdf", "orphan.pdf"}


def test_readonly_cannot_upload_but_can_list(client, auth):
    proj = make_project(client, auth)
    ro = readonly_auth()
    # 上传被拒
    r = _upload(client, ro, "projects", proj["id"],
                [("files", ("a.pdf", make_simple_pdf("a"), "application/pdf"))])
    assert r.status_code == 403
    # 列表与下载允许
    r = client.get(f"/api/attachments/projects/{proj['id']}", headers=ro)
    assert r.status_code == 200


def test_unsupported_type_skipped(client, auth):
    proj = make_project(client, auth)
    r = _upload(client, auth, "projects", proj["id"],
                [("files", ("note.txt", b"hello", "text/plain"))])
    assert r.status_code == 200
    assert r.json()["files"][0]["status"] == "skipped"


def test_non_pdf_formats_accepted(client, auth):
    """Word / Excel / 图片 应被接受（不再限定 PDF）。"""
    proj = make_project(client, auth)
    r = _upload(client, auth, "projects", proj["id"],
                [("files", ("doc.docx", b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
                 ("files", ("pic.png", b"\x89PNG\r\n\x1a\n", "image/png")),
                 ("files", ("sheet.xlsx", b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))])
    assert r.status_code == 200, r.text
    assert [f["status"] for f in r.json()["files"]] == ["ok", "ok", "ok"]

    # 图片应按正确 content-type 提供下载/预览
    rows = client.get(f"/api/attachments/projects/{proj['id']}", headers=auth).json()
    png = next(x for x in rows if x["filename"] == "pic.png")
    fr = client.get(f"/api/attachments/{png['id']}/file", headers=auth)
    assert fr.status_code == 200
    assert fr.headers["content-type"] == "image/png"


def test_upload_to_missing_record_404(client, auth):
    r = _upload(client, auth, "projects", 999999,
                [("files", ("a.pdf", make_simple_pdf("a"), "application/pdf"))])
    assert r.status_code == 404


def test_award_attachments(client, auth):
    r = client.post(
        "/api/awards",
        json={"award_name": "测试奖"},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    award_id = r.json()["id"]

    r = _upload(client, auth, "awards", award_id,
                [("files", ("cert.pdf", make_simple_pdf("cert"), "application/pdf"))])
    assert r.status_code == 200, r.text

    r = client.get(f"/api/attachments/awards/{award_id}", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # 实体附件按 att_id 下载
    aid = r.json()[0]["id"]
    r = client.get(f"/api/attachments/{aid}/file", headers=auth)
    assert r.status_code == 200


def test_invalid_entity_400(client, auth):
    r = client.get("/api/attachments/widgets/1", headers=auth)
    assert r.status_code == 400


def test_one_pdf_per_paper_on_link(client, auth):
    """手动关联 PDF 时，论文已有 PDF 的，旧关联被解除——一篇论文最多一个 PDF。"""
    from app.models import Attachment
    from conftest import make_paper

    paper = make_paper(client, auth, title="单PDF约束论文")
    db = TestSession()
    db.add(Attachment(att_type="pdf", filename="old.pdf", store_path="/tmp/old.pdf",
                     sha256="old1", size=10, paper_id=paper["id"]))
    db.commit()
    old_id = db.query(Attachment).filter(Attachment.filename == "old.pdf").first().id
    db.add(Attachment(att_type="pdf", filename="new.pdf", store_path="/tmp/new.pdf",
                     sha256="new1", size=10, paper_id=None))
    db.commit()
    new_id = db.query(Attachment).filter(Attachment.filename == "new.pdf").first().id
    db.close()

    # 把 new.pdf 关联到该论文 → old.pdf 应被解除
    r = client.put(f"/api/pdfs/{new_id}/link", json={"paper_id": paper["id"]}, headers=auth)
    assert r.status_code == 200, r.text
    linked = [a for a in client.get("/api/pdfs", headers=auth).json()["rows"] if a["paper_id"] == paper["id"]]
    assert len(linked) == 1
    assert linked[0]["id"] == new_id


def test_batch_link_keeps_only_one_per_paper(client, auth):
    """批量关联多条 PDF 到同一论文时，只保留最后一条。"""
    from app.models import Attachment
    from conftest import make_paper

    paper = make_paper(client, auth, title="批量单PDF论文")
    db = TestSession()
    ids = []
    for i in range(3):
        db.add(Attachment(att_type="pdf", filename=f"b{i}.pdf", store_path=f"/tmp/b{i}.pdf",
                         sha256=f"b{i}", size=10, paper_id=None))
    db.commit()
    ids = [a.id for a in db.query(Attachment).filter(Attachment.filename.like("b%")).all()]
    db.close()

    r = client.put("/api/pdfs/batch-link", json={"attachment_ids": ids, "paper_id": paper["id"]}, headers=auth)
    assert r.status_code == 200, r.text
    linked = [a for a in client.get("/api/pdfs", headers=auth).json()["rows"] if a["paper_id"] == paper["id"]]
    assert len(linked) == 1
    assert linked[0]["id"] == ids[-1]


def test_malformed_date_does_not_500_list(client, auth):
    """pub_date 存了非法日期字符串（如仅年份"2025"）时，论文列表不应 500。"""
    from app.models import Attachment, Paper, normalize_title
    from conftest import TestSession

    db = TestSession()
    db.add(Paper(title="非法日期论文", title_norm=normalize_title("非法日期论文"),
                 pub_date="2025", year=2025))
    db.commit()
    db.close()

    r = client.get("/api/papers", headers=auth)
    assert r.status_code == 200, r.text
    p = next((x for x in r.json() if x["title"] == "非法日期论文"), None)
    assert p is not None
    # 非法日期宽容加载为 None，不抛错
    assert p["pub_date"] is None
