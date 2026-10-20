from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ArchiveOut(ORMModel):
    id: int
    entity: str
    filename: str
    size_bytes: Optional[int]
    is_auto: bool
    created_by: Optional[str]
    created_at: datetime


class AttachmentOut(ORMModel):
    id: int
    filename: str
    size: int
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    created_at: datetime


class BatchByRecordsIn(BaseModel):
    entity: str
    ids: List[int]


class BatchByIdsIn(BaseModel):
    attachment_ids: List[int]


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str
    role: str
    must_change_password: bool


class UserOut(ORMModel):
    id: int
    username: str
    role: str
    person_id: Optional[int] = None
    must_change_password: bool


class NameVariantIn(BaseModel):
    name_text: str
    kind: Optional[str] = None


class NameVariantOut(NameVariantIn, ORMModel):
    id: int


class PersonBase(BaseModel):
    uid: str
    name: Optional[str] = None
    english_name: Optional[str] = None
    degree_type: Optional[str] = None
    status: Optional[str] = None
    current_activity: Optional[str] = None
    research_direction: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    extra: Optional[dict] = None

    @field_validator("uid")
    @classmethod
    def strip_uid(cls, v: str) -> str:
        v = v.strip()
        if "." in v and v.replace(".", "").replace("e+", "").isdigit():
            raise ValueError("学号/工号疑似为科学计数法，请使用原始文本格式")
        if not v:
            raise ValueError("学号/工号不能为空")
        return v


class PersonCreate(PersonBase):
    name_variants: List[NameVariantIn] = []


class PersonUpdate(PersonBase):
    uid: Optional[str] = None
    name: Optional[str] = None
    name_variants: Optional[List[NameVariantIn]] = None


class PersonOut(PersonBase, ORMModel):
    id: int
    created_at: datetime
    extra: dict = {}
    name_variants: List[NameVariantOut] = []


class ProjectMemberIn(BaseModel):
    person_id: int
    role: Optional[str] = None
    note: Optional[str] = None


class ProjectMemberOut(ProjectMemberIn, ORMModel):
    id: int
    person_name: Optional[str] = None


class ProjectBase(BaseModel):
    project_no: str
    name: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    status: Optional[str] = None
    budget_no: Optional[str] = None
    targets: Optional[str] = None
    targets_done: Optional[str] = None
    budget_total: Optional[float] = None
    budget_ours: Optional[float] = None
    budget_received: Optional[float] = None
    notes: Optional[str] = None
    extra: Optional[dict] = None


class ProjectCreate(ProjectBase):
    members: List[ProjectMemberIn] = []


class ProjectUpdate(ProjectBase):
    project_no: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    source: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    duration: Optional[str] = None
    status: Optional[str] = None
    budget_no: Optional[str] = None
    targets: Optional[str] = None
    targets_done: Optional[str] = None
    budget_total: Optional[float] = None
    budget_ours: Optional[float] = None
    budget_received: Optional[float] = None
    notes: Optional[str] = None


class ProjectOut(ProjectBase, ORMModel):
    id: int
    created_at: datetime
    extra: dict = {}
    members: List[ProjectMemberOut] = []


class PaperAuthorIn(BaseModel):
    seq: int = 0
    author_name: str
    person_id: Optional[int] = None
    is_corresponding: bool = False
    affiliation: Optional[str] = None


class PaperAuthorOut(PaperAuthorIn, ORMModel):
    id: int
    person_name: Optional[str] = None


class PaperFundingIn(BaseModel):
    project_id: Optional[int] = None
    funding_no: Optional[str] = None
    seq: int = 0
    source: str = "manual"
    confirmed: bool = True


class PaperFundingOut(PaperFundingIn, ORMModel):
    id: int
    project_name: Optional[str] = None


class PaperBase(BaseModel):
    title: str
    doi: Optional[str] = None
    bib_key: Optional[str] = None
    bib_raw: Optional[str] = None
    authors_raw: Optional[str] = None
    venue: Optional[str] = None
    venue_abbr: Optional[str] = None
    venue_type: Optional[str] = None
    year: Optional[int] = None
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    pub_date: Optional[date] = None
    address: Optional[str] = None
    publisher: Optional[str] = None
    ccf_class: Optional[str] = None
    th_cpl_class: Optional[str] = None
    ack_index: Optional[str] = None
    acknowledgements: Optional[str] = None
    corresponding_text: Optional[str] = None
    extract_status: Optional[str] = None
    abstract: Optional[str] = None
    evaluation: Optional[str] = None
    notes: Optional[str] = None
    url: Optional[str] = None
    demo_url: Optional[str] = None
    extra: Optional[dict] = None


class PaperCreate(PaperBase):
    authors: List[PaperAuthorIn] = []
    funding: List[PaperFundingIn] = []


class PaperUpdate(PaperBase):
    title: Optional[str] = None


class PaperOut(PaperBase, ORMModel):
    id: int
    created_at: datetime
    extra: dict = {}
    authors: List[PaperAuthorOut] = []
    funding: List[PaperFundingOut] = []


class PaperListItem(PaperBase, ORMModel):
    # 列表返回全部标量字段 + extra，与人员/项目一致；
    # 前端按字段定义的 show_in_list 决定渲染哪些列（如 extract_status）。
    id: int
    extra: dict = {}


class IPInventorIn(BaseModel):
    seq: int = 0
    inventor_name: str
    person_id: Optional[int] = None
    is_first: bool = False


class IPInventorOut(IPInventorIn, ORMModel):
    id: int
    person_name: Optional[str] = None


class IPFundingIn(BaseModel):
    project_id: Optional[int] = None
    funding_no: Optional[str] = None


class IPFundingOut(IPFundingIn, ORMModel):
    id: int
    project_name: Optional[str] = None


class IPBase(BaseModel):
    ip_type: str
    title: str
    grant_date: Optional[date] = None
    applicant: Optional[str] = None
    notes: Optional[str] = None
    extra: Optional[dict] = None

    @field_validator("ip_type")
    @classmethod
    def check_type(cls, v: str) -> str:
        # ip_type 选项由字段管理配置，此处仅做基础校验
        return (v or "").strip()

    @field_validator("title")
    @classmethod
    def check_title(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("产权名称不能为空")
        return v.strip()


class IPCreate(IPBase):
    inventors: List[IPInventorIn] = []
    funding: List[IPFundingIn] = []


class IPUpdate(IPBase):
    ip_type: Optional[str] = None
    title: Optional[str] = None


class IPOut(IPBase, ORMModel):
    id: int
    created_at: datetime
    extra: dict = {}
    inventors: List[IPInventorOut] = []
    funding: List[IPFundingOut] = []


class AwardRecipientIn(BaseModel):
    seq: int = 0
    recipient_name: str
    person_id: Optional[int] = None
    rank: Optional[str] = None


class AwardRecipientOut(AwardRecipientIn, ORMModel):
    id: int
    person_name: Optional[str] = None


class AwardBase(BaseModel):
    award_name: str
    level: Optional[str] = None
    award_date: Optional[date] = None
    cert_no: Optional[str] = None
    issuer: Optional[str] = None
    summary: Optional[str] = None
    pr_url: Optional[str] = None
    all_awardees: Optional[str] = None
    extra: Optional[dict] = None

    @field_validator("award_name")
    @classmethod
    def _non_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("奖项名称不能为空")
        return v.strip()


class AwardCreate(AwardBase):
    recipients: List[AwardRecipientIn] = []


class AwardUpdate(AwardBase):
    award_name: Optional[str] = None
    recipients: Optional[List[AwardRecipientIn]] = None


class AwardOut(AwardBase, ORMModel):
    id: int
    created_at: datetime
    batch_id: Optional[str] = None
    extra: dict = {}


class AwardDetailOut(AwardOut):
    recipients: List[AwardRecipientOut] = []
