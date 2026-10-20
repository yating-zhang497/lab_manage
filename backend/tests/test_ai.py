from io import BytesIO
from types import SimpleNamespace

from conftest import make_paper, make_person, make_project

from app import ai_extract

LLM_RESULT = {
    "author": "Corresponding author: Haohuan Fu (fuhh@sz.tsinghua.edu.cn)",
    "funding_text": (
        "This work was supported by the National Natural Science Foundation of China "
        "(grant T2125006) and Shenzhen Science and Technology Program "
        "KCXFZ20240903093759004."
    ),
    "funding_nos": ["T2125006", "KCXFZ20240903093759004"],
}


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


def fake_person(pid, english_name, variants=()):
    return SimpleNamespace(
        id=pid,
        name="测试",
        english_name=english_name,
        name_variants=[SimpleNamespace(name_text=v) for v in variants],
    )


def fake_project(pid, project_no):
    return SimpleNamespace(id=pid, project_no=project_no)


def test_extract_text_from_real_pdf():
    pdf = make_simple_pdf("Acknowledgments: supported by grant T2125006")
    text = ai_extract.extract_text(BytesIO(pdf))
    assert "T2125006" in text


def test_match_funding_projects():
    projects = [
        fake_project(1, "T2125006"),
        fake_project(2, "KCXFZ20240903093759004"),
        fake_project(3, None),
        fake_project(4, ""),
    ]
    matches = ai_extract.match_funding_projects(LLM_RESULT["funding_text"], projects)
    nos = {m["project_no"] for m in matches}
    assert nos == {"T2125006", "KCXFZ20240903093759004"}
    assert ai_extract.match_funding_projects("Not Found", projects) == []


def test_match_corresponding_variants():
    people = [
        fake_person(1, "Fu, Haohuan"),
        fake_person(2, "Zhang, Jinxiao", variants=["Jin-Xiao Zhang"]),
    ]
    m = ai_extract.match_corresponding(LLM_RESULT["author"], people)
    assert m is not None and m["person_id"] == 1

    m2 = ai_extract.match_corresponding("Jin-xiao Zhang is corresponding", people)
    assert m2 is not None and m2["person_id"] == 2

    assert ai_extract.match_corresponding("Not Found", people) is None
    assert ai_extract.match_corresponding("Somebody Else Entirely", people) is None


def test_clean_name_text():
    cleaned = ai_extract.clean_name_text(
        "Haohuan Fu* (fuhh@sz.tsinghua.edu.cn), Corresponding author"
    )
    assert "@" not in cleaned
    assert "(" not in cleaned
    assert "haohuan" in cleaned.lower()


def test_extract_endpoint_requires_api_key(client, auth, monkeypatch):
    monkeypatch.delenv("IM_LLM_API_KEY", raising=False)
    person = make_person(client, auth, english_name="Fu, Haohuan")
    paper = make_paper(client, auth, authors=[{"author_name": "Fu, Haohuan", "person_id": person["id"]}])
    pdf = make_simple_pdf("hello")
    r = client.post(
        f"/api/papers/{paper['id']}/extract",
        files={"file": ("t.pdf", pdf, "application/pdf")},
        headers=auth,
    )
    assert r.status_code == 400


def test_extract_and_apply_flow(client, auth, monkeypatch):
    monkeypatch.setenv("IM_LLM_API_KEY", "test-key")
    monkeypatch.setattr(ai_extract, "call_llm", lambda prompt, settings: dict(LLM_RESULT))

    fu = make_person(client, auth, name="付昊桓", uid="T001", english_name="Fu, Haohuan")
    p1 = make_project(client, auth, name="NSFC项目", project_no="T2125006")
    p2 = make_project(client, auth, name="深圳科技计划", project_no="KCXFZ20240903093759004")
    paper = make_paper(
        client,
        auth,
        title="An AI Weather Model",
        authors=[{"author_name": "Fu, Haohuan", "person_id": fu["id"], "seq": 1}],
    )

    pdf = make_simple_pdf("An AI Weather Model ... full text ...")
    r = client.post(
        f"/api/papers/{paper['id']}/extract",
        files={"file": ("paper.pdf", pdf, "application/pdf")},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert {m["project_no"] for m in data["funding_matches"]} == {
        "T2125006",
        "KCXFZ20240903093759004",
    }
    assert data["corresponding_match"]["person_id"] == fu["id"]
    ext_id = data["extraction_id"]

    r2 = client.post(f"/api/extractions/{ext_id}/apply", headers=auth)
    assert r2.status_code == 200, r2.text
    out = r2.json()
    assert out["added_funding"] == 2
    assert out["marked_corresponding"] is True

    detail = client.get(f"/api/papers/{paper['id']}", headers=auth).json()
    assert len(detail["funding"]) == 2
    assert all(f["confirmed"] is True and f["source"] == "auto" for f in detail["funding"])
    assert {f["project_id"] for f in detail["funding"]} == {p1["id"], p2["id"]}
    assert {f["seq"] for f in detail["funding"]} == {1, 2}
    assert detail["authors"][0]["is_corresponding"] is True
    assert detail["acknowledgements"].startswith("This work was supported")
    # 通讯作者原文也应写入 corresponding_text 字段（编辑表单才能回填，见 Issue 9）
    assert detail["corresponding_text"].startswith("Corresponding author")

    r3 = client.post(f"/api/extractions/{ext_id}/apply", headers=auth)
    assert r3.json()["added_funding"] == 0

    r4 = client.get(f"/api/papers/{paper['id']}/extractions", headers=auth)
    assert r4.status_code == 200
    assert r4.json()[0]["status"] == "confirmed"
