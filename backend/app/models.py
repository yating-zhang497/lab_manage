import re
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from .database import Base


class LenientDate(TypeDecorator):
    """日期列的宽容加载：DB 里存了非法日期（如仅年份"2025"、半截"2025-06"）时
    返回 None，而不是让 SQLAlchemy 内置 str_to_date 抛错导致整条查询 500。

    用 String 作 impl 绕开内置 Date 处理器，自行解析 ISO 日期；合法值照常返回 date。
    """
    impl = String
    cache_ok = True

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, date):
            return value
        try:
            return date.fromisoformat(str(value))
        except (ValueError, TypeError):
            return None

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, date):
            return value.isoformat()
        return str(value)



def normalize_title(title: str) -> str:
    return re.sub(r"[\W_]+", "", title.lower())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(16), default="readonly")
    person_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("people.id"), nullable=True
    )
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    # 登录失败计数：连续失败次数，达到5次后锁定15分钟
    login_fail_count: Mapped[int] = mapped_column(Integer, default=0)
    login_locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class FieldDef(TimestampMixin, Base):
    """自定义字段定义：每个模块(people/projects/papers/ip)可动态增删字段。"""

    __tablename__ = "field_defs"
    __table_args__ = (UniqueConstraint("entity", "key", name="uq_field_def"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(16), index=True)
    key: Mapped[str] = mapped_column(String(48))
    label: Mapped[str] = mapped_column(String(64))
    dtype: Mapped[str] = mapped_column(String(16), default="text")
    options: Mapped[Optional[str]] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    show_in_list: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class Token(TimestampMixin, Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)


class Person(TimestampMixin, Base):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    english_name: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    degree_type: Mapped[Optional[str]] = mapped_column(String(16))
    status: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    current_activity: Mapped[Optional[str]] = mapped_column(String(64))
    research_direction: Mapped[Optional[str]] = mapped_column(Text)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    email: Mapped[Optional[str]] = mapped_column(String(128))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    extra_json: Mapped[Optional[str]] = mapped_column(Text)

    name_variants = relationship(
        "PersonNameVariant", back_populates="person", cascade="all, delete-orphan"
    )
    award_links = relationship(
        "AwardRecipient", back_populates="person", cascade="all, delete-orphan"
    )


class PersonNameVariant(Base):
    __tablename__ = "person_name_variants"

    id: Mapped[int] = mapped_column(primary_key=True)
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id"), index=True
    )
    name_text: Mapped[str] = mapped_column(String(128))
    kind: Mapped[Optional[str]] = mapped_column(String(32))

    person = relationship("Person", back_populates="name_variants")


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(256), index=True, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    source: Mapped[Optional[str]] = mapped_column(String(128))
    start_date: Mapped[Optional[str]] = mapped_column(String(16))
    end_date: Mapped[Optional[str]] = mapped_column(String(16))
    duration: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    budget_no: Mapped[Optional[str]] = mapped_column(String(64))
    targets: Mapped[Optional[str]] = mapped_column(Text)
    targets_done: Mapped[Optional[str]] = mapped_column(Text)
    budget_total: Mapped[Optional[float]] = mapped_column(Float)
    budget_ours: Mapped[Optional[float]] = mapped_column(Float)
    budget_received: Mapped[Optional[float]] = mapped_column(Float)
    # 已下线字段：旧库该列为 NOT NULL 无默认值，保留映射(default=False)仅为兼容存量库，不对外暴露
    watch: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    extra_json: Mapped[Optional[str]] = mapped_column(Text)

    members = relationship(
        "ProjectMember", back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "person_id", name="uq_proj_person"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"), index=True
    )
    person_id: Mapped[int] = mapped_column(ForeignKey("people.id"), index=True)
    role: Mapped[Optional[str]] = mapped_column(String(16))
    note: Mapped[Optional[str]] = mapped_column(String(256))

    project = relationship("Project", back_populates="members")
    person = relationship("Person")


class Paper(TimestampMixin, Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    title_norm: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    doi: Mapped[Optional[str]] = mapped_column(
        String(128), unique=True, index=True, nullable=True
    )
    bib_key: Mapped[Optional[str]] = mapped_column(String(128))
    bib_raw: Mapped[Optional[str]] = mapped_column(Text)
    authors_raw: Mapped[Optional[str]] = mapped_column(Text)
    venue: Mapped[Optional[str]] = mapped_column(String(256), index=True)
    venue_abbr: Mapped[Optional[str]] = mapped_column(String(64))
    venue_type: Mapped[Optional[str]] = mapped_column(String(16), index=True)
    year: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    volume: Mapped[Optional[str]] = mapped_column(String(16))
    issue: Mapped[Optional[str]] = mapped_column(String(16))
    pages: Mapped[Optional[str]] = mapped_column(String(32))
    pub_date: Mapped[Optional[date]] = mapped_column(LenientDate)
    address: Mapped[Optional[str]] = mapped_column(String(128))
    publisher: Mapped[Optional[str]] = mapped_column(String(128))
    ccf_class: Mapped[Optional[str]] = mapped_column(String(8), index=True)
    th_cpl_class: Mapped[Optional[str]] = mapped_column(String(16))
    ack_index: Mapped[Optional[str]] = mapped_column(String(128))
    acknowledgements: Mapped[Optional[str]] = mapped_column(Text)
    corresponding_text: Mapped[Optional[str]] = mapped_column(Text, default=None)
    extract_status: Mapped[Optional[str]] = mapped_column(String(16), default=None)
    abstract: Mapped[Optional[str]] = mapped_column(Text)
    evaluation: Mapped[Optional[str]] = mapped_column(Text)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(512))
    demo_url: Mapped[Optional[str]] = mapped_column(String(512))
    extra_json: Mapped[Optional[str]] = mapped_column(Text)

    authors = relationship(
        "PaperAuthor",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperAuthor.seq",
    )
    funding = relationship(
        "PaperFunding",
        back_populates="paper",
        cascade="all, delete-orphan",
        order_by="PaperFunding.seq",
    )


class PaperAuthor(Base):
    __tablename__ = "paper_authors"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    author_name: Mapped[str] = mapped_column(String(128), index=True)
    person_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("people.id"), nullable=True, index=True
    )
    is_corresponding: Mapped[bool] = mapped_column(Boolean, default=False)
    affiliation: Mapped[Optional[str]] = mapped_column(String(256))

    paper = relationship("Paper", back_populates="authors")
    person = relationship("Person")


class PaperFunding(Base):
    __tablename__ = "paper_funding"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    funding_no: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[Optional[str]] = mapped_column(String(16), default="manual")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)

    paper = relationship("Paper", back_populates="funding")
    project = relationship("Project")


class IntellectualProperty(TimestampMixin, Base):
    __tablename__ = "intellectual_property"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_type: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    grant_date: Mapped[Optional[date]] = mapped_column(LenientDate)
    applicant: Mapped[Optional[str]] = mapped_column(String(256))
    notes: Mapped[Optional[str]] = mapped_column(Text)
    extra_json: Mapped[Optional[str]] = mapped_column(Text)

    inventors = relationship(
        "IPInventor",
        back_populates="ip",
        cascade="all, delete-orphan",
        order_by="IPInventor.seq",
    )
    funding = relationship(
        "IPFunding", back_populates="ip", cascade="all, delete-orphan"
    )


class IPInventor(Base):
    __tablename__ = "ip_inventors"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_id: Mapped[int] = mapped_column(
        ForeignKey("intellectual_property.id"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer, default=0)
    inventor_name: Mapped[str] = mapped_column(String(128))
    person_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("people.id"), nullable=True, index=True
    )
    is_first: Mapped[bool] = mapped_column(Boolean, default=False)

    ip = relationship("IntellectualProperty", back_populates="inventors")
    person = relationship("Person")


class IPFunding(Base):
    __tablename__ = "ip_funding"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_id: Mapped[int] = mapped_column(
        ForeignKey("intellectual_property.id"), index=True
    )
    project_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    funding_no: Mapped[Optional[str]] = mapped_column(String(64))

    ip = relationship("IntellectualProperty", back_populates="funding")
    project = relationship("Project")


class AwardRecord(TimestampMixin, Base):
    __tablename__ = "award_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    award_name: Mapped[str] = mapped_column(String(256), index=True)
    level: Mapped[Optional[str]] = mapped_column(String(16))
    award_date: Mapped[Optional[date]] = mapped_column(LenientDate)
    cert_no: Mapped[Optional[str]] = mapped_column(String(64))
    issuer: Mapped[Optional[str]] = mapped_column(String(128))
    summary: Mapped[Optional[str]] = mapped_column(Text)
    pr_url: Mapped[Optional[str]] = mapped_column(String(512))
    all_awardees: Mapped[Optional[str]] = mapped_column(Text)
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    extra_json: Mapped[Optional[str]] = mapped_column(Text)

    recipients = relationship(
        "AwardRecipient", back_populates="award", cascade="all, delete-orphan"
    )


class AwardRecipient(Base):
    __tablename__ = "award_recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    award_id: Mapped[int] = mapped_column(ForeignKey("award_records.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    recipient_name: Mapped[str] = mapped_column(String(128), index=True)
    person_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("people.id"), nullable=True, index=True
    )
    rank: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    award = relationship("AwardRecord", back_populates="recipients")
    person = relationship("Person", back_populates="award_links")


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"

    id: Mapped[int] = mapped_column(primary_key=True)
    att_type: Mapped[str] = mapped_column(String(16), default="pdf")
    filename: Mapped[str] = mapped_column(String(256))
    store_path: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    size: Mapped[int] = mapped_column(Integer, default=0)
    paper_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("papers.id"), nullable=True, index=True
    )
    uploader_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    # 行内附件：关联到 projects/people/ip/awards 四类实体（论文附件仍用 paper_id，entity_type 保持 NULL）
    entity_type: Mapped[Optional[str]] = mapped_column(String(16), index=True, nullable=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, index=True, nullable=True)


class ImportJob(TimestampMixin, Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_type: Mapped[str] = mapped_column(String(16))
    mode: Mapped[str] = mapped_column(String(16), default="manual")
    filename: Mapped[Optional[str]] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    ok_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    error_detail: Mapped[Optional[str]] = mapped_column(Text)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))


class AIExtraction(TimestampMixin, Base):
    __tablename__ = "ai_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    attachment_id: Mapped[int] = mapped_column(
        ForeignKey("attachments.id"), index=True
    )
    result_json: Mapped[Optional[str]] = mapped_column(Text)
    model: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    confirmer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )


class Archive(Base):
    __tablename__ = "archives"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity: Mapped[str] = mapped_column(String(16), index=True)  # people/projects/papers/ip
    filename: Mapped[str] = mapped_column(String(256))
    file_path: Mapped[str] = mapped_column(String(512))          # 磁盘路径
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer)
    is_auto: Mapped[bool] = mapped_column(Boolean, default=False)  # True=自动触发
    created_by: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
