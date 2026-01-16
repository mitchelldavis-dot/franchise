"""Export commands for CLI."""

import csv
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from sqlmodel import Session, select

from ..models import get_engine, Lead, Evidence, Document

app = typer.Typer(help="Export leads to various formats")
console = Console()


@app.command()
def csv_export(
    output: Path = typer.Option("leads.csv", help="Output CSV file"),
    lead_type: Optional[str] = typer.Option(None, help="Filter by type (A, B)"),
    min_score: Optional[float] = typer.Option(None, help="Minimum score"),
    florida_only: bool = typer.Option(False, help="Export only Florida leads"),
):
    """Export leads to CSV."""
    console.print(f"[bold blue]Exporting leads to {output}...[/bold blue]")

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(Lead)

        if lead_type:
            stmt = stmt.where(Lead.lead_type == lead_type)
        if min_score:
            stmt = stmt.where(Lead.priority_score >= min_score)
        if florida_only:
            stmt = stmt.where(Lead.is_florida == True)

        leads = session.exec(stmt).all()

        if not leads:
            console.print("[yellow]No leads to export[/yellow]")
            return

        # Write CSV
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                "Lead ID",
                "Type",
                "Handle",
                "Location",
                "City",
                "State",
                "Is Florida",
                "Geo Confidence",
                "Score",
                "Tier",
                "Status",
                "Evidence Count",
                "Budget Hints",
                "Timeline Hints",
                "Created At",
                "URLs",
            ])

            # Data
            for lead in leads:
                # Get evidence
                evidence = session.exec(
                    select(Evidence).where(Evidence.lead_id == lead.lead_id)
                ).all()

                # Get URLs
                urls = []
                for ev in evidence:
                    doc = session.get(Document, ev.doc_id)
                    if doc and doc.url:
                        urls.append(doc.url)

                writer.writerow([
                    lead.lead_id,
                    lead.lead_type.value,
                    lead.canonical_handle or "",
                    lead.location_text or "",
                    lead.location_city or "",
                    lead.location_state or "",
                    "Yes" if lead.is_florida else "No",
                    lead.geo_confidence or "",
                    f"{lead.priority_score:.2f}",
                    lead.tier or "",
                    lead.status.value,
                    len(evidence),
                    "; ".join(lead.extracted_fields.get("budget_hints", [])),
                    "; ".join(lead.extracted_fields.get("timeline_hints", [])),
                    lead.created_at.isoformat(),
                    "; ".join(urls[:5]),  # First 5 URLs
                ])

    console.print(f"[bold green]✓ Exported {len(leads)} leads to {output}[/bold green]")


@app.command()
def hubspot(
    output: Path = typer.Option("leads_hubspot.csv", help="Output CSV file for HubSpot"),
    lead_type: Optional[str] = typer.Option(None, help="Filter by type (A, B)"),
    min_score: float = typer.Option(60.0, help="Minimum score"),
):
    """Export leads in HubSpot import format."""
    console.print(f"[bold blue]Exporting leads in HubSpot format to {output}...[/bold blue]")

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(Lead).where(Lead.priority_score >= min_score)

        if lead_type:
            stmt = stmt.where(Lead.lead_type == lead_type)

        leads = session.exec(stmt).all()

        if not leads:
            console.print("[yellow]No leads to export[/yellow]")
            return

        # Write HubSpot format CSV
        with open(output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)

            # HubSpot header
            writer.writerow([
                "Company name",  # Will use handle
                "City",
                "State/Region",
                "Lead Status",
                "Lead Source",
                "Lead Score",
                "Lead Type",
                "Website URL",
                "Description",
                "Notes",
            ])

            # Data
            for lead in leads:
                # Get first evidence for URL and description
                evidence = session.exec(
                    select(Evidence)
                    .where(Evidence.lead_id == lead.lead_id)
                    .limit(1)
                ).first()

                url = ""
                description = ""
                if evidence:
                    doc = session.get(Document, evidence.doc_id)
                    if doc:
                        url = doc.url or ""
                        description = evidence.snippet[:500]

                # Build notes
                notes = f"Tier: {lead.tier}. "
                if lead.extracted_fields.get("budget_hints"):
                    notes += f"Budget: {', '.join(lead.extracted_fields['budget_hints'])}. "
                if lead.extracted_fields.get("timeline_hints"):
                    notes += f"Timeline: {', '.join(lead.extracted_fields['timeline_hints'])}. "

                writer.writerow([
                    lead.canonical_handle or "Unknown",
                    lead.location_city or "",
                    lead.location_state or "",
                    lead.status.value,
                    "Franchise Radar",
                    int(lead.priority_score),
                    "Franchise Buyer" if lead.lead_type.value == "A" else "Gym Owner Pain",
                    url,
                    description,
                    notes,
                ])

    console.print(f"[bold green]✓ Exported {len(leads)} leads in HubSpot format[/bold green]")


@app.command()
def airtable(
    output: Path = typer.Option("leads_airtable.json", help="Output JSON file for Airtable"),
    lead_type: Optional[str] = typer.Option(None, help="Filter by type (A, B)"),
    min_score: float = typer.Option(60.0, help="Minimum score"),
):
    """Export leads in Airtable-friendly JSON format."""
    console.print(f"[bold blue]Exporting leads in Airtable format to {output}...[/bold blue]")

    engine = get_engine()
    with Session(engine) as session:
        stmt = select(Lead).where(Lead.priority_score >= min_score)

        if lead_type:
            stmt = stmt.where(Lead.lead_type == lead_type)

        leads = session.exec(stmt).all()

        if not leads:
            console.print("[yellow]No leads to export[/yellow]")
            return

        # Build Airtable records
        records = []
        for lead in leads:
            # Get evidence
            evidence = session.exec(
                select(Evidence).where(Evidence.lead_id == lead.lead_id)
            ).all()

            # Get URLs
            urls = []
            for ev in evidence:
                doc = session.get(Document, ev.doc_id)
                if doc and doc.url:
                    urls.append(doc.url)

            record = {
                "fields": {
                    "Lead ID": lead.lead_id,
                    "Type": "Franchise Buyer" if lead.lead_type.value == "A" else "Gym Owner Pain",
                    "Handle": lead.canonical_handle or "",
                    "Location": lead.location_text or "",
                    "City": lead.location_city or "",
                    "State": lead.location_state or "",
                    "Is Florida": lead.is_florida,
                    "Geo Confidence": lead.geo_confidence or "",
                    "Score": lead.priority_score,
                    "Tier": lead.tier or "",
                    "Status": lead.status.value,
                    "Evidence Count": len(evidence),
                    "Budget Hints": lead.extracted_fields.get("budget_hints", []),
                    "Timeline Hints": lead.extracted_fields.get("timeline_hints", []),
                    "URLs": urls[:5],
                    "Created At": lead.created_at.isoformat(),
                }
            }
            records.append(record)

        # Write JSON
        with open(output, "w", encoding="utf-8") as f:
            json.dump({"records": records}, f, indent=2)

    console.print(f"[bold green]✓ Exported {len(leads)} leads in Airtable format[/bold green]")
