"""Main CLI application."""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track
from loguru import logger
from sqlmodel import Session, select

from ..models import init_db, get_engine, Source, Document, Lead, Run, RunStatus
from ..models.database import SourceType, LeadType
from ..config import get_config
from ..ingest import RedditAdapter, RSSAdapter, WebCrawler, YouTubeAdapter
from ..ingest.manual_import import ManualImportAdapter
from ..scoring import score_franchise_buyer, score_owner_pain
from ..extraction import extract_entities
from ..dedupe import deduplicate_leads
from . import export_commands
from . import demo_commands

# Create CLI app
app = typer.Typer(
    name="franchise-radar",
    help="Franchise Lead Radar - Discover and score franchise opportunities",
)

# Add subcommands
app.add_typer(export_commands.app, name="export")
app.add_typer(demo_commands.app, name="demo")

console = Console()


@app.command()
def init():
    """Initialize the database."""
    console.print("[bold green]Initializing database...[/bold green]")
    init_db()
    console.print("[bold green]✓ Database initialized successfully[/bold green]")


@app.command()
def ingest(
    source: str = typer.Option(..., help="Source to ingest from (reddit, rss, web_crawl, youtube)"),
    since: Optional[str] = typer.Option(None, help="Time window (e.g., 24h, 7d)"),
    limit: Optional[int] = typer.Option(None, help="Max documents to ingest"),
    seeds: Optional[Path] = typer.Option(None, help="File with seed URLs for web crawl"),
):
    """Ingest data from a source."""
    # Parse since parameter
    since_dt = None
    if since:
        since_dt = parse_time_window(since)

    # Run ingestion
    asyncio.run(run_ingestion(source, since_dt, limit, seeds))


async def run_ingestion(
    source: str,
    since: Optional[datetime],
    limit: Optional[int],
    seeds: Optional[Path],
):
    """Run ingestion async."""
    config = get_config()
    engine = get_engine()

    console.print(f"[bold blue]Starting ingestion from {source}...[/bold blue]")

    # Get or create source record
    with Session(engine) as session:
        stmt = select(Source).where(Source.name == source)
        source_record = session.exec(stmt).first()

        if not source_record:
            source_type = SourceType(source)
            source_record = Source(
                name=source,
                type=source_type,
                enabled=True,
                config=config.get("sources", {}).get(source, {}),
            )
            session.add(source_record)
            session.commit()
            session.refresh(source_record)

        # Create run record
        run = Run(
            source_id=source_record.source_id,
            status=RunStatus.RUNNING,
            stats={},
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        run_id = run.run_id

    try:
        # Initialize adapter
        adapter_config = config.get("sources", {}).get(source, {})

        # Load seed URLs for web crawler
        if source == "web_crawl" and seeds:
            with open(seeds) as f:
                seed_urls = [line.strip() for line in f if line.strip()]
            adapter_config["seed_urls"] = seed_urls

        adapter = None
        if source == "reddit":
            adapter = RedditAdapter(adapter_config)
        elif source == "rss":
            adapter = RSSAdapter(adapter_config)
        elif source == "web_crawl":
            adapter = WebCrawler(adapter_config)
        elif source == "youtube":
            adapter = YouTubeAdapter(adapter_config)
        else:
            console.print(f"[bold red]Unknown source: {source}[/bold red]")
            return

        # Validate config
        if not adapter.validate_config():
            console.print(f"[bold red]Invalid configuration for {source}[/bold red]")
            return

        # Ingest documents
        documents = await adapter.ingest(since=since, limit=limit)

        # Store documents
        with Session(engine) as session:
            doc_count = 0
            for doc in documents:
                # Check if already exists
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

            # Update run
            run = session.get(Run, run_id)
            run.ended_at = datetime.utcnow()
            run.status = RunStatus.COMPLETED
            run.stats = {
                "documents_ingested": doc_count,
                "documents_total": len(documents),
                "duplicates_skipped": len(documents) - doc_count,
            }
            session.commit()

        console.print(f"[bold green]✓ Ingested {doc_count} new documents[/bold green]")

    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        with Session(engine) as session:
            run = session.get(Run, run_id)
            run.ended_at = datetime.utcnow()
            run.status = RunStatus.FAILED
            run.error = {"message": str(e)}
            session.commit()

        console.print(f"[bold red]✗ Ingestion failed: {e}[/bold red]")


@app.command()
def score(
    lead_type: str = typer.Option("all", help="Type of lead to score (buyer, owner, all)"),
    min_score: float = typer.Option(40.0, help="Minimum score threshold"),
):
    """Score unprocessed documents and create leads."""
    console.print("[bold blue]Starting scoring...[/bold blue]")

    engine = get_engine()
    with Session(engine) as session:
        # Get unprocessed documents
        stmt = select(Document).where(Document.processed == False)
        documents = session.exec(stmt).all()

        if not documents:
            console.print("[yellow]No unprocessed documents found[/yellow]")
            return

        console.print(f"Processing {len(documents)} documents...")

        # Score documents
        buyer_results = {}
        owner_results = {}

        for doc in track(documents, description="Scoring..."):
            # Extract entities
            entities = extract_entities(
                text=doc.body,
                title=doc.title,
                author_handle=doc.author_handle,
                url=doc.url,
            )

            # Score for franchise buyer
            if lead_type in ["buyer", "all"]:
                result = score_franchise_buyer(
                    text=doc.body,
                    title=doc.title,
                    source=session.get(Source, doc.source_id).name,
                    published_at=doc.published_at,
                )

                # Add entity data to result
                result.extracted_fields.update(entities)

                if result.score >= min_score:
                    buyer_results[doc.doc_id] = result

            # Score for owner pain
            if lead_type in ["owner", "all"]:
                result = score_owner_pain(
                    text=doc.body,
                    title=doc.title,
                    source=session.get(Source, doc.source_id).name,
                    published_at=doc.published_at,
                )

                # Add entity data to result
                result.extracted_fields.update(entities)

                if result.score >= min_score:
                    owner_results[doc.doc_id] = result

            # Mark as processed
            doc.processed = True

        session.commit()

        # Deduplicate and create leads
        buyer_leads = []
        owner_leads = []

        if buyer_results:
            console.print(f"\nCreating {len(buyer_results)} franchise buyer leads...")
            buyer_leads = deduplicate_leads(
                session,
                list(buyer_results.keys()),
                LeadType.FRANCHISE_BUYER,
                buyer_results,
            )

        if owner_results:
            console.print(f"Creating {len(owner_results)} owner pain leads...")
            owner_leads = deduplicate_leads(
                session,
                list(owner_results.keys()),
                LeadType.OWNER_PAIN,
                owner_results,
            )

        console.print(f"\n[bold green]✓ Created {len(buyer_leads)} buyer leads[/bold green]")
        console.print(f"[bold green]✓ Created {len(owner_leads)} owner pain leads[/bold green]")


@app.command()
def import_data(
    file: Path = typer.Argument(..., help="CSV or JSON file to import"),
    source_name: str = typer.Option("manual", help="Name for this import source"),
):
    """Import data from CSV or JSON file."""
    console.print(f"[bold blue]Importing from {file}...[/bold blue]")

    if not file.exists():
        console.print(f"[bold red]File not found: {file}[/bold red]")
        return

    adapter = ManualImportAdapter({})

    # Determine file type
    if file.suffix.lower() == ".csv":
        documents = adapter.import_from_csv(str(file), source_name)
    elif file.suffix.lower() == ".json":
        documents = adapter.import_from_json(str(file), source_name)
    else:
        console.print(f"[bold red]Unsupported file type: {file.suffix}[/bold red]")
        console.print("Supported types: .csv, .json")
        return

    if not documents:
        console.print("[yellow]No documents imported[/yellow]")
        return

    # Store documents
    engine = get_engine()
    with Session(engine) as session:
        # Get or create source
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

        # Add documents
        doc_count = 0
        for doc in documents:
            # Check for duplicates
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

    console.print(f"[bold green]✓ Imported {doc_count} documents[/bold green]")


@app.command()
def list_leads(
    lead_type: Optional[str] = typer.Option(None, help="Filter by type (A, B)"),
    min_score: Optional[float] = typer.Option(None, help="Minimum score"),
    florida_only: bool = typer.Option(False, help="Show only Florida leads"),
    limit: int = typer.Option(20, help="Number of leads to show"),
):
    """List leads."""
    engine = get_engine()
    with Session(engine) as session:
        stmt = select(Lead)

        if lead_type:
            stmt = stmt.where(Lead.lead_type == lead_type)
        if min_score:
            stmt = stmt.where(Lead.priority_score >= min_score)
        if florida_only:
            stmt = stmt.where(Lead.is_florida == True)

        stmt = stmt.order_by(Lead.priority_score.desc()).limit(limit)
        leads = session.exec(stmt).all()

        if not leads:
            console.print("[yellow]No leads found[/yellow]")
            return

        # Create table
        table = Table(title=f"Top {len(leads)} Leads")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Handle", style="green")
        table.add_column("Location", style="blue")
        table.add_column("Score", style="yellow")
        table.add_column("Tier", style="red")
        table.add_column("Status")

        for lead in leads:
            table.add_row(
                str(lead.lead_id),
                lead.lead_type.value,
                lead.canonical_handle or "N/A",
                lead.location_text or "Unknown",
                f"{lead.priority_score:.1f}",
                lead.tier or "N/A",
                lead.status.value,
            )

        console.print(table)


@app.command()
def config_template(
    output: Path = typer.Option("import_template.csv", help="Output file path"),
    format: str = typer.Option("csv", help="Format: csv or json"),
):
    """Generate import template."""
    adapter = ManualImportAdapter({})

    if format == "csv":
        content = adapter.get_template_csv()
    elif format == "json":
        content = adapter.get_template_json()
    else:
        console.print(f"[bold red]Unknown format: {format}[/bold red]")
        return

    with open(output, "w") as f:
        f.write(content)

    console.print(f"[bold green]✓ Template saved to {output}[/bold green]")


def parse_time_window(window: str) -> datetime:
    """Parse time window string (e.g., 24h, 7d) to datetime."""
    import re

    match = re.match(r"(\d+)([hdw])", window)
    if not match:
        raise ValueError(f"Invalid time window: {window}")

    value = int(match.group(1))
    unit = match.group(2)

    if unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    elif unit == "w":
        delta = timedelta(weeks=value)
    else:
        raise ValueError(f"Invalid time unit: {unit}")

    return datetime.utcnow() - delta


if __name__ == "__main__":
    app()
