"""Database models and connections."""

import os
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

from sqlmodel import Field, SQLModel, create_engine, Session, Relationship, JSON, Column
from sqlalchemy import Index


# Enums
class SourceType(str, Enum):
    """Source types for data ingestion."""
    REDDIT = "reddit"
    RSS = "rss"
    WEB_CRAWL = "web_crawl"
    YOUTUBE = "youtube"
    PODCAST = "podcast"
    MANUAL_IMPORT = "manual_import"
    TWITTER = "twitter"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    QUORA = "quora"


class LeadType(str, Enum):
    """Types of leads."""
    FRANCHISE_BUYER = "A"
    OWNER_PAIN = "B"


class LeadStatus(str, Enum):
    """Status of leads."""
    NEW = "new"
    REVIEWING = "reviewing"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    NURTURING = "nurturing"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"
    ARCHIVED = "archived"


class GeoConfidence(str, Enum):
    """Confidence level for geographic data."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RunStatus(str, Enum):
    """Status of ingestion runs."""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


# Models
class Source(SQLModel, table=True):
    """Source configuration for data ingestion."""
    __tablename__ = "sources"

    source_id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    type: SourceType
    enabled: bool = Field(default=True)
    config: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    documents: List["Document"] = Relationship(back_populates="source")
    runs: List["Run"] = Relationship(back_populates="source")


class Document(SQLModel, table=True):
    """Raw documents ingested from sources."""
    __tablename__ = "documents"

    doc_id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.source_id", index=True)
    external_id: str = Field(index=True)  # URL or unique identifier from source
    url: Optional[str] = None
    author_handle: Optional[str] = Field(default=None, index=True)
    title: Optional[str] = None
    body: str
    published_at: Optional[datetime] = Field(default=None, index=True)
    fetched_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    raw_json: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    processed: bool = Field(default=False, index=True)

    # Relationships
    source: Source = Relationship(back_populates="documents")
    evidence: List["Evidence"] = Relationship(back_populates="document")

    __table_args__ = (
        Index("idx_source_external", "source_id", "external_id", unique=True),
    )


class Lead(SQLModel, table=True):
    """Canonical lead records."""
    __tablename__ = "leads"

    lead_id: Optional[int] = Field(default=None, primary_key=True)
    lead_type: LeadType = Field(index=True)
    canonical_handle: Optional[str] = Field(default=None, index=True)
    canonical_name: Optional[str] = None
    location_text: Optional[str] = None
    location_city: Optional[str] = Field(default=None, index=True)
    location_state: Optional[str] = Field(default=None, index=True)
    geo_confidence: Optional[GeoConfidence] = None
    geo_why: Optional[str] = None
    is_florida: bool = Field(default=False, index=True)
    priority_score: float = Field(default=0.0, index=True)
    tier: Optional[str] = None
    status: LeadStatus = Field(default=LeadStatus.NEW, index=True)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    extracted_fields: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    updated_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Relationships
    evidence: List["Evidence"] = Relationship(back_populates="lead")
    notes: List["Note"] = Relationship(back_populates="lead")


class Evidence(SQLModel, table=True):
    """Evidence linking documents to leads."""
    __tablename__ = "evidence"

    evidence_id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="leads.lead_id", index=True)
    doc_id: int = Field(foreign_key="documents.doc_id", index=True)
    snippet: str
    reasons: List[str] = Field(default_factory=list, sa_column=Column(JSON))
    score: float
    tier: str
    extracted_fields: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    lead: Lead = Relationship(back_populates="evidence")
    document: Document = Relationship(back_populates="evidence")


class Run(SQLModel, table=True):
    """Ingestion run tracking."""
    __tablename__ = "runs"

    run_id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="sources.source_id", index=True)
    started_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    ended_at: Optional[datetime] = None
    status: RunStatus = Field(default=RunStatus.RUNNING, index=True)
    stats: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    error: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))

    # Relationships
    source: Source = Relationship(back_populates="runs")


class Config(SQLModel, table=True):
    """Configuration versions."""
    __tablename__ = "configs"

    config_id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    version: str
    yaml_text: str
    is_active: bool = Field(default=False, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Note(SQLModel, table=True):
    """Notes and status history for leads."""
    __tablename__ = "notes"

    note_id: Optional[int] = Field(default=None, primary_key=True)
    lead_id: int = Field(foreign_key="leads.lead_id", index=True)
    note_text: str
    created_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    lead: Lead = Relationship(back_populates="notes")


# Database setup
def get_engine():
    """Get database engine."""
    database_url = os.getenv("DATABASE_URL", "sqlite:///./data/franchise_radar.db")
    # Ensure data directory exists
    if database_url.startswith("sqlite"):
        db_path = database_url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    engine = create_engine(
        database_url,
        echo=os.getenv("ENVIRONMENT") == "development",
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
    )
    return engine


def get_session():
    """Get database session."""
    engine = get_engine()
    with Session(engine) as session:
        yield session


def init_db():
    """Initialize database tables."""
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    print("Database initialized successfully")
