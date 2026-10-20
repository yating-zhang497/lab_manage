from conftest import make_paper, make_person, make_project

import pytest


@pytest.fixture()
def setup(client, auth):
    teacher = make_person(client, auth, name="王老师", uid="T100", english_name="Wang, Wu")
    student = make_person(client, auth, name="李同学", uid="S200", english_name="Li, Si")
    p1 = make_project(client, auth, name="NSFC项目", project_no="T2125006")
    p2 = make_project(client, auth, name="深圳项目", project_no="KCXFZ20240903")
    paper1 = make_paper(
        client, auth, title="通讯作者论文", year=2024,
        authors=[
            {"author_name": "Li, Si", "person_id": student["id"], "seq": 1},
            {"author_name": "Wang, Wu", "person_id": teacher["id"], "seq": 2, "is_corresponding": True},
        ],
        funding=[
            {"project_id": p1["id"], "funding_no": "T2125006", "seq": 1},
            {"project_id": p2["id"], "funding_no": "KCXFZ20240903", "seq": 2},
        ],
    )
    paper2 = make_paper(
        client, auth, title="一作论文", year=2025,
        authors=[{"author_name": "Wang, Wu", "person_id": teacher["id"], "seq": 1}],
        funding=[{"project_id": p1["id"], "funding_no": "T2125006", "seq": 2}],
    )
    paper3 = make_paper(
        client, auth, title="致谢提及论文", year=2025,
        acknowledgements="This work was supported by grant T2125006.",
        authors=[{"author_name": "External Person", "seq": 1}],
    )
    return {"teacher": teacher, "student": student, "p1": p1, "p2": p2,
            "paper1": paper1, "paper2": paper2, "paper3": paper3}


def titles(client, auth, query):
    return [p["title"] for p in client.get(f"/api/papers?{query}", headers=auth).json()]


def test_filter_by_author_role(client, auth, setup):
    tid = setup["teacher"]["id"]
    assert set(titles(client, auth, f"person_id={tid}")) == {"通讯作者论文", "一作论文"}
    assert titles(client, auth, f"person_id={tid}&author_role=corresponding") == ["通讯作者论文"]
    assert titles(client, auth, f"person_id={tid}&author_role=first") == ["一作论文"]
    assert set(titles(client, auth, f"person_id={tid}&author_role=first_or_corresponding")) == {
        "通讯作者论文", "一作论文"
    }
    # 不指定人员时按角色全局筛选也生效
    assert titles(client, auth, "author_role=corresponding") == ["通讯作者论文"]


def test_filter_by_funding_seq_and_ack_text(client, auth, setup):
    p1 = setup["p1"]["id"]
    assert set(titles(client, auth, f"project_id={p1}")) == {"通讯作者论文", "一作论文"}
    assert titles(client, auth, f"project_id={p1}&funding_seq=1") == ["通讯作者论文"]
    assert titles(client, auth, f"project_id={p1}&funding_seq=2") == ["一作论文"]
    # 致谢文本兜底：未录入关系的论文也能筛出
    got = titles(client, auth, f"project_id={p1}&include_ack_text=true")
    assert set(got) == {"通讯作者论文", "一作论文", "致谢提及论文"}


def test_filter_by_author_and_year(client, auth, setup):
    """某作者某年发表的全部论文。"""
    tid = setup["teacher"]["id"]
    # 王老师 2024 只有"通讯作者论文"
    assert titles(client, auth, f"person_id={tid}&year=2024") == ["通讯作者论文"]
    # 王老师 2025 只有"一作论文"
    assert titles(client, auth, f"person_id={tid}&year=2025") == ["一作论文"]
    # 王老师 2024+2025 两篇
    got = titles(client, auth, f"person_id={tid}&years=2024&years=2025")
    assert set(got) == {"通讯作者论文", "一作论文"}


def test_filter_by_author_year_and_role(client, auth, setup):
    """某作者某年作为通讯/一作发表的论文。"""
    tid = setup["teacher"]["id"]
    # 王老师 2024 作为通讯作者 → "通讯作者论文"
    assert titles(client, auth, f"person_id={tid}&year=2024&author_role=corresponding") == ["通讯作者论文"]
    # 王老师 2025 作为第一作者 → "一作论文"
    assert titles(client, auth, f"person_id={tid}&year=2025&author_role=first") == ["一作论文"]
    # 王老师 2024 作为第一作者 → 无（2024年只是通讯，不是一作）
    assert titles(client, auth, f"person_id={tid}&year=2024&author_role=first") == []


def test_filter_by_project_returns_all_annotated_papers(client, auth, setup):
    """标注了某个项目的全部论文。"""
    p1 = setup["p1"]["id"]
    p2 = setup["p2"]["id"]
    # 项目1关联了两篇论文
    assert set(titles(client, auth, f"project_id={p1}")) == {"通讯作者论文", "一作论文"}
    # 项目2只关联了一篇
    assert titles(client, auth, f"project_id={p2}") == ["通讯作者论文"]


def test_export_by_ids_keeps_order(client, auth, setup):
    ids = [setup["paper2"]["id"], setup["paper1"]["id"]]
    r = client.post(
        "/api/export/preview",
        json={"type": "papers", "columns": ["title"], "ids": ids},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 2
    assert [row["title"] for row in body["rows"]] == ["一作论文", "通讯作者论文"]

    r = client.post(
        "/api/export/custom",
        json={"type": "papers", "columns": ["title", "year"], "ids": ids},
        headers=auth,
    )
    assert r.status_code == 200 and r.content[:2] == b"PK"

    r = client.get(
        f"/api/export/papers.bib?ids={setup['paper1']['id']},{setup['paper3']['id']}",
        headers=auth,
    )
    text = r.content.decode("utf-8")
    assert "通讯作者论文" in text and "致谢提及论文" in text and "一作论文" not in text


def test_export_by_empty_ids_returns_nothing(client, auth, setup):
    # 空 id 列表应导出空结果，而非回退到"无筛选"导出全部
    r = client.post(
        "/api/export/preview",
        json={"type": "papers", "columns": ["title"], "ids": []},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 0
    assert body["rows"] == []


def test_corresponding_author_export_columns(client, auth, setup):
    r = client.post(
        "/api/export/preview",
        json={
            "type": "papers",
            "columns": ["title", "corresponding_name", "corresponding_uid"],
            "ids": [setup["paper1"]["id"], setup["paper2"]["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    rows = {row["title"]: row for row in r.json()["rows"]}
    # paper1 有通讯作者（王老师, uid=T100）
    assert rows["通讯作者论文"]["corresponding_name"] == "王老师"
    assert rows["通讯作者论文"]["corresponding_uid"] == "T100"
    # paper2 没有通讯作者
    assert rows["一作论文"]["corresponding_name"] is None
    assert rows["一作论文"]["corresponding_uid"] is None


def test_project_no_columns_derived_from_funding(client, auth, setup):
    r = client.post(
        "/api/export/preview",
        json={
            "type": "papers",
            "columns": ["title", "project_no_1", "project_seq_1", "project_no_2", "project_seq_2"],
            "ids": [setup["paper1"]["id"], setup["paper2"]["id"]],
        },
        headers=auth,
    )
    rows = {row["title"]: row for row in r.json()["rows"]}
    # 两个标注：编号+对应排序一一对应（位置型列为标量，一行一篇论文）
    assert rows["通讯作者论文"]["project_no_1"] == "T2125006"
    assert rows["通讯作者论文"]["project_seq_1"] == 1
    assert rows["通讯作者论文"]["project_no_2"] == "KCXFZ20240903"
    assert rows["通讯作者论文"]["project_seq_2"] == 2
    # 只有二标的论文：项目编号1 对应排序应为 2
    assert rows["一作论文"]["project_no_1"] == "T2125006"
    assert rows["一作论文"]["project_seq_1"] == 2


def test_export_paper_funding_dim_expands_one_row_per_funding(client, auth, setup):
    """论文-项目维度（project_nos/funding_seqs/funding_nos）按一行一条标注展开。"""
    r = client.post(
        "/api/export/preview",
        json={
            "type": "papers",
            "columns": ["title", "project_nos", "funding_seqs", "funding_nos"],
            "ids": [setup["paper1"]["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    # 一篇论文有两个基金标注 → 展开成两行
    assert len(rows) == 2
    by_seq = {row["funding_seqs"]: row for row in rows}
    assert by_seq[1]["project_nos"] == "T2125006"
    assert by_seq[1]["funding_nos"] == "T2125006"
    assert by_seq[2]["project_nos"] == "KCXFZ20240903"
    assert by_seq[2]["funding_nos"] == "KCXFZ20240903"
    # 论文标量字段在每行重复
    assert all(row["title"] == "通讯作者论文" for row in rows)


def test_snapshot_fields_removed_from_field_defs(client, auth, setup):
    fields = client.get("/api/fields?entity=papers", headers=auth).json()
    keys = {f["key"] for f in fields}
    assert not {"project_no_1", "project_no_2", "project_no_3"} & keys
    # 导出仍提供派生列
    cols = client.get("/api/export/columns?type=papers", headers=auth).json()
    assert "project_no_1" in {c["key"] for c in cols}


def test_import_paper_creates_funding_rows(client, auth, setup):
    # 作者列含逗号，需引号包裹；项目编号2留空验证位置信息保留
    csv = (
        "论文题目,所有作者名排序,期刊/会议名称,年份,项目编号1,项目编号2\n"
        'Import Funding Paper,"Zhang, San; Wang, Wu",Science,2025,T2125006,\n'
    )
    r = client.post(
        "/api/import/papers",
        files={"file": ("p.csv", csv.encode("utf-8"), "text/csv")},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok_count"] == 1

    papers = client.get("/api/papers", headers=auth).json()
    paper = [p for p in papers if p["title"] == "Import Funding Paper"][0]
    detail = client.get(f"/api/papers/{paper['id']}", headers=auth).json()
    assert len(detail["funding"]) == 1
    f = detail["funding"][0]
    assert f["project_id"] == setup["p1"]["id"]
    assert f["seq"] == 1
    assert f["source"] == "import"
    assert "project_no_1" not in (detail["extra"] or {})


def test_dynamic_position_columns_adjust_to_data(client, auth, setup):
    """论文有3个基金标注时，导出目录应自动出现 project_no_3。"""
    p3 = make_project(client, auth, name="第三个项目", project_no="GPT20260001")
    paper = make_paper(
        client, auth,
        title="三标注论文",
        year=2026,
        funding=[
            {"project_id": setup["p1"]["id"], "funding_no": "T2125006", "seq": 1},
            {"project_id": setup["p2"]["id"], "funding_no": "KCXFZ20240903", "seq": 2},
            {"project_id": p3["id"], "funding_no": "GPT20260001", "seq": 3},
        ],
    )
    # 导出目录应包含 project_no_3（根据当前数据动态生成）
    cols = client.get("/api/export/columns?type=papers", headers=auth).json()
    keys = {c["key"] for c in cols}
    assert "project_no_1" in keys
    assert "project_no_2" in keys
    assert "project_no_3" in keys

    # 导出值也应正确
    r = client.post(
        "/api/export/preview",
        json={
            "type": "papers",
            "columns": ["title", "project_no_1", "project_no_2", "project_no_3"],
            "ids": [paper["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    row = r.json()["rows"][0]
    assert row["project_no_1"] == "T2125006"
    assert row["project_no_2"] == "KCXFZ20240903"
    assert row["project_no_3"] == "GPT20260001"


def test_export_project_papers_one_row_per_paper(client, auth, setup):
    """项目-论文维度：一个项目下多篇资助论文，一行一条论文，每行写项目名称/编号+标注顺序。"""
    r = client.post(
        "/api/export/preview",
        json={
            "type": "projects",
            "columns": ["project_no", "name", "paper_titles", "funding_seqs"],
            "ids": [setup["p1"]["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    # p1 资助了两篇论文 → 展开成两行
    assert len(rows) == 2
    # 每行都写上项目编号与项目名称（标量字段重复）
    assert all(row["project_no"] == "T2125006" and row["name"] == "NSFC项目" for row in rows)
    # 每行一条论文标题 + 对应标注顺序
    by_seq = {row["funding_seqs"]: row for row in rows}
    assert by_seq[1]["paper_titles"] == "通讯作者论文"
    assert by_seq[2]["paper_titles"] == "一作论文"


def test_export_project_no_papers_keeps_one_row(client, auth, setup):
    """项目在论文维度下无资助论文时，仍保留一行（关联列留空）。"""
    empty = make_project(client, auth, name="无资助项目", project_no="EMPTY0001")
    r = client.post(
        "/api/export/preview",
        json={
            "type": "projects",
            "columns": ["project_no", "name", "paper_titles", "funding_seqs"],
            "ids": [empty["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["project_no"] == "EMPTY0001"
    assert rows[0]["paper_titles"] is None
    assert rows[0]["funding_seqs"] is None


def test_export_project_members_one_row_per_member(client, auth, setup):
    """项目-成员维度：一行一条成员，每行写项目编号+成员姓名/学号/角色。"""
    proj = make_project(client, auth, name="成员项目", project_no="MEMB0001")
    client.post(
        f"/api/projects/{proj['id']}/members",
        json={"person_id": setup["teacher"]["id"], "role": "负责人"},
        headers=auth,
    )
    client.post(
        f"/api/projects/{proj['id']}/members",
        json={"person_id": setup["student"]["id"], "role": "学生"},
        headers=auth,
    )
    r = client.post(
        "/api/export/preview",
        json={
            "type": "projects",
            "columns": ["project_no", "name", "member_names", "member_uids", "member_roles"],
            "ids": [proj["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert len(rows) == 2
    assert all(row["project_no"] == "MEMB0001" for row in rows)
    by_name = {row["member_names"]: row for row in rows}
    assert by_name["王老师"]["member_uids"] == "T100"
    assert by_name["王老师"]["member_roles"] == "负责人"
    assert by_name["李同学"]["member_uids"] == "S200"
    assert by_name["李同学"]["member_roles"] == "学生"


def test_export_paper_authors_dim_one_row_per_author(client, auth, setup):
    """论文-作者维度：一行一条作者，通讯作者列按该作者是否为通讯填充。"""
    r = client.post(
        "/api/export/preview",
        json={
            "type": "papers",
            "columns": ["title", "team_names", "team_uids", "corresponding_names"],
            "ids": [setup["paper1"]["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    # paper1 有两位作者 → 两行
    assert len(rows) == 2
    by_name = {row["team_names"]: row for row in rows}
    # 第一作者（学生）非通讯 → corresponding_names 为空
    assert by_name["李同学"]["team_uids"] == "S200"
    assert by_name["李同学"]["corresponding_names"] is None
    # 第二作者（老师）是通讯 → corresponding_names 填其姓名
    assert by_name["王老师"]["team_uids"] == "T100"
    assert by_name["王老师"]["corresponding_names"] == "王老师"


def test_export_no_dim_keeps_one_row_per_entity(client, auth, setup):
    """未选任何多值维度列时，仍是一个实体一行（位置型/标量列不受影响）。"""
    r = client.post(
        "/api/export/preview",
        json={
            "type": "projects",
            "columns": ["project_no", "name", "paper_count"],
            "ids": [setup["p1"]["id"], setup["p2"]["id"]],
        },
        headers=auth,
    )
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert len(rows) == 2  # 两个项目各一行
    by_no = {row["project_no"]: row for row in rows}
    assert by_no["T2125006"]["paper_count"] == 2
    assert by_no["KCXFZ20240903"]["paper_count"] == 1


def test_list_returns_extract_status_and_extra(client, auth, setup):
    """列表接口应返回 extract_status 与 extra，使前端按 show_in_list 渲染对应列。"""
    make_paper(client, auth, title="已提取论文", year=2026, extract_status="已提取")
    papers = client.get("/api/papers", headers=auth).json()
    paper = next(p for p in papers if p["title"] == "已提取论文")
    # extract_status 字段定义 show_in_list=True，列表必须带回来
    assert paper["extract_status"] == "已提取"
    # extra 也应返回（自定义字段才能在列表显示），无自定义字段时为空 dict
    assert paper.get("extra") == {}
