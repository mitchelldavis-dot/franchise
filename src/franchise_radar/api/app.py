"""Main FastAPI application."""

import os
from datetime import datetime
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, Depends, Query, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select, func
from pydantic import BaseModel

from ..models import (
    get_session,
    init_db,
    Lead,
    Evidence,
    Document,
    Source,
    Run,
    Note,
)
from ..models.database import LeadType, LeadStatus

# Initialize database on startup
init_db()

# Create FastAPI app
app = FastAPI(
    title="Franchise Lead Radar",
    description="API for franchise lead discovery and scoring",
    version="0.1.0",
)

# Setup templates
templates_dir = Path(__file__).parent.parent.parent.parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

# Setup static files
static_dir = Path(__file__).parent.parent.parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


# Pydantic models for requests/responses
class LeadFilter(BaseModel):
    lead_type: Optional[str] = None
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    tier: Optional[str] = None
    location: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    keyword: Optional[str] = None
    is_florida: Optional[bool] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = 50
    offset: int = 0


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    note: Optional[str] = None


class LeadResponse(BaseModel):
    lead_id: int
    lead_type: str
    canonical_handle: Optional[str]
    location_text: Optional[str]
    priority_score: float
    tier: Optional[str]
    status: str
    is_florida: bool
    evidence_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class LeadDetailResponse(LeadResponse):
    location_city: Optional[str]
    location_state: Optional[str]
    geo_confidence: Optional[str]
    geo_why: Optional[str]
    extracted_fields: dict
    evidence: List[dict]

    class Config:
        from_attributes = True


# API Routes

@app.get("/")
async def root(request: Request):
    """Root endpoint - serves the web UI."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/leads", response_model=List[LeadResponse])
async def get_leads(
    lead_type: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    tier: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    is_florida: Optional[bool] = Query(None),
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    session: Session = Depends(get_session),
):
    """Get leads with filters."""
    stmt = select(Lead)

    # Apply filters
    if lead_type:
        stmt = stmt.where(Lead.lead_type == lead_type)
    if min_score:
        stmt = stmt.where(Lead.priority_score >= min_score)
    if tier:
        stmt = stmt.where(Lead.tier == tier)
    if location:
        stmt = stmt.where(
            (Lead.location_text.contains(location)) |
            (Lead.location_city.contains(location))
        )
    if status:
        stmt = stmt.where(Lead.status == status)
    if is_florida is not None:
        stmt = stmt.where(Lead.is_florida == is_florida)

    # Order and paginate
    stmt = stmt.order_by(Lead.priority_score.desc()).offset(offset).limit(limit)

    leads = session.exec(stmt).all()

    # Add evidence count
    response = []
    for lead in leads:
        evidence_count = session.exec(
            select(func.count(Evidence.evidence_id)).where(Evidence.lead_id == lead.lead_id)
        ).one()

        response.append(
            LeadResponse(
                lead_id=lead.lead_id,
                lead_type=lead.lead_type.value,
                canonical_handle=lead.canonical_handle,
                location_text=lead.location_text,
                priority_score=lead.priority_score,
                tier=lead.tier,
                status=lead.status.value,
                is_florida=lead.is_florida,
                evidence_count=evidence_count,
                created_at=lead.created_at,
            )
        )

    return response


@app.get("/api/leads/{lead_id}", response_model=LeadDetailResponse)
async def get_lead(
    lead_id: int,
    session: Session = Depends(get_session),
):
    """Get lead detail with evidence."""
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Get evidence
    evidence_records = session.exec(
        select(Evidence).where(Evidence.lead_id == lead_id)
    ).all()

    evidence_list = []
    for ev in evidence_records:
        doc = session.get(Document, ev.doc_id)
        evidence_list.append({
            "evidence_id": ev.evidence_id,
            "snippet": ev.snippet,
            "reasons": ev.reasons,
            "score": ev.score,
            "tier": ev.tier,
            "url": doc.url if doc else None,
            "source": session.get(Source, doc.source_id).name if doc else None,
            "published_at": doc.published_at.isoformat() if doc and doc.published_at else None,
        })

    evidence_count = len(evidence_list)

    return LeadDetailResponse(
        lead_id=lead.lead_id,
        lead_type=lead.lead_type.value,
        canonical_handle=lead.canonical_handle,
        location_text=lead.location_text,
        location_city=lead.location_city,
        location_state=lead.location_state,
        geo_confidence=lead.geo_confidence,
        geo_why=lead.geo_why,
        priority_score=lead.priority_score,
        tier=lead.tier,
        status=lead.status.value,
        is_florida=lead.is_florida,
        extracted_fields=lead.extracted_fields,
        evidence=evidence_list,
        evidence_count=evidence_count,
        created_at=lead.created_at,
    )


@app.patch("/api/leads/{lead_id}")
async def update_lead(
    lead_id: int,
    update: LeadUpdate,
    session: Session = Depends(get_session),
):
    """Update lead status and add notes."""
    lead = session.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if update.status:
        try:
            lead.status = LeadStatus(update.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update.status}")

    if update.note:
        note = Note(
            lead_id=lead_id,
            note_text=update.note,
            created_by="api_user",
        )
        session.add(note)

    lead.updated_at = datetime.utcnow()
    session.commit()

    return {"status": "success", "lead_id": lead_id}


@app.get("/api/stats")
async def get_stats(session: Session = Depends(get_session)):
    """Get application statistics."""
    # Count leads
    total_leads = session.exec(select(func.count(Lead.lead_id))).one()
    buyer_leads = session.exec(
        select(func.count(Lead.lead_id)).where(Lead.lead_type == LeadType.FRANCHISE_BUYER)
    ).one()
    owner_leads = session.exec(
        select(func.count(Lead.lead_id)).where(Lead.lead_type == LeadType.OWNER_PAIN)
    ).one()
    florida_leads = session.exec(
        select(func.count(Lead.lead_id)).where(Lead.is_florida == True)
    ).one()

    # Count documents
    total_docs = session.exec(select(func.count(Document.doc_id))).one()
    unprocessed_docs = session.exec(
        select(func.count(Document.doc_id)).where(Document.processed == False)
    ).one()

    # Count sources
    active_sources = session.exec(
        select(func.count(Source.source_id)).where(Source.enabled == True)
    ).one()

    # Recent runs
    recent_runs = session.exec(
        select(Run).order_by(Run.started_at.desc()).limit(5)
    ).all()

    return {
        "leads": {
            "total": total_leads,
            "franchise_buyers": buyer_leads,
            "owner_pain": owner_leads,
            "florida": florida_leads,
        },
        "documents": {
            "total": total_docs,
            "unprocessed": unprocessed_docs,
        },
        "sources": {
            "active": active_sources,
        },
        "recent_runs": [
            {
                "run_id": run.run_id,
                "source": session.get(Source, run.source_id).name,
                "status": run.status.value,
                "started_at": run.started_at.isoformat(),
                "stats": run.stats,
            }
            for run in recent_runs
        ],
    }


@app.get("/api/export/csv")
async def export_csv(
    lead_type: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    session: Session = Depends(get_session),
):
    """Export leads as CSV."""
    import csv
    import io

    stmt = select(Lead)
    if lead_type:
        stmt = stmt.where(Lead.lead_type == lead_type)
    if min_score:
        stmt = stmt.where(Lead.priority_score >= min_score)

    leads = session.exec(stmt).all()

    # Generate CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "Lead ID", "Type", "Handle", "Location", "Score", "Tier", "Status", "Evidence Count"
    ])

    # Data
    for lead in leads:
        evidence_count = session.exec(
            select(func.count(Evidence.evidence_id)).where(Evidence.lead_id == lead.lead_id)
        ).one()

        writer.writerow([
            lead.lead_id,
            lead.lead_type.value,
            lead.canonical_handle or "",
            lead.location_text or "",
            f"{lead.priority_score:.2f}",
            lead.tier or "",
            lead.status.value,
            evidence_count,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@app.post("/api/import")
async def import_file(
    file: UploadFile = File(...),
    source_name: str = Query("manual"),
    session: Session = Depends(get_session),
):
    """Import leads from CSV or JSON file."""
    from ..ingest.manual_import import ManualImportAdapter

    # Save file temporarily
    temp_path = f"/tmp/{file.filename}"
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Import
    adapter = ManualImportAdapter({})

    try:
        if file.filename.endswith(".csv"):
            documents = adapter.import_from_csv(temp_path, source_name)
        elif file.filename.endswith(".json"):
            documents = adapter.import_from_json(temp_path, source_name)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        # Store documents (similar to CLI import)
        from ..models.database import SourceType

        stmt = select(Source).where(Source.name == f"manual_{source_name}")
        source_record = session.exec(stmt).first()

        if not source_record:
            source_record = Source(
                name=f"manual_{source_name}",
                type=SourceType.MANUAL_IMPORT,
                enabled=True,
                config={"source_name": source_name},
            )
            session.add(source_record)
            session.commit()
            session.refresh(source_record)

        doc_count = 0
        for doc in documents:
            stmt = select(Document).where(
                Document.source_id == source_record.source_id,
                Document.external_id == doc.external_id,
            )
            existing = session.exec(stmt).first()

            if not existing:
                db_doc = Document(
                    source_id=source_record.source_id,
                    external_id=doc.external_id,
                    url=doc.url,
                    author_handle=doc.author_handle,
                    title=doc.title,
                    body=doc.body,
                    published_at=doc.published_at,
                    raw_json=doc.raw_json,
                    processed=False,
                )
                session.add(db_doc)
                doc_count += 1

        session.commit()

        return {
            "status": "success",
            "documents_imported": doc_count,
            "total_documents": len(documents),
        }

    finally:
        # Clean up temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
