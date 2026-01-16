"""Demo commands for testing without API keys."""

import random
from datetime import datetime, timedelta

import typer
from rich.console import Console
from sqlmodel import Session

from ..models import get_engine, init_db, Source, Document, Lead, Evidence
from ..models.database import SourceType, LeadType, LeadStatus, GeoConfidence

app = typer.Typer(help="Demo and testing commands")
console = Console()


DEMO_POSTS = [
    {
        "title": "Looking for gym franchise opportunities in Miami",
        "body": "I'm interested in buying a gym franchise in Miami, FL. My budget is around $250k and I'm looking to start within the next 6 months. Any recommendations for good franchises?",
        "handle": "fitness_entrepreneur_123",
        "lead_type": "A",
        "location": "Miami, FL",
    },
    {
        "title": "Best boutique fitness franchises under $300k?",
        "body": "I'm leaving corporate and want to be my own boss. Looking at boutique fitness franchises in Orlando. What are the best options under $300k? Preferably something like yoga or pilates.",
        "handle": "orlando_dreamer",
        "lead_type": "A",
        "location": "Orlando, FL",
    },
    {
        "title": "Need help - my gym is struggling",
        "body": "I own a small gym in Tampa and we're really struggling. Member churn is killing us - people keep cancelling. Our Facebook ads stopped working and we can't get new leads. Any advice?",
        "handle": "tampa_gym_owner",
        "lead_type": "B",
        "location": "Tampa, FL",
    },
    {
        "title": "Yoga studio marketing problems",
        "body": "My yoga studio in Jacksonville has been stuck at 80 members for 6 months. We need help with marketing and operations. Our intro offer isn't converting well. What should we do?",
        "handle": "yoga_studio_jax",
        "lead_type": "B",
        "location": "Jacksonville, FL",
    },
    {
        "title": "Franchise discovery day experience",
        "body": "Just went to a franchise discovery day for a fitness franchise. The FDD shows Item 19 earnings are pretty good. Looking at territory in Fort Lauderdale. Anyone have experience with multi-unit fitness franchises?",
        "handle": "franchise_researcher",
        "lead_type": "A",
        "location": "Fort Lauderdale, FL",
    },
    {
        "title": "CrossFit box losing members",
        "body": "Our CrossFit gym in St. Petersburg is losing members. We're down from 150 to 90 members in the last year. Need help with retention strategies and maybe better software. Using Zen Planner but not happy with it.",
        "handle": "crossfit_owner_stpete",
        "lead_type": "B",
        "location": "St. Petersburg, FL",
    },
    {
        "title": "Looking at F45 franchise",
        "body": "Considering an F45 franchise in West Palm Beach. I have $400k liquid capital and net worth of $800k. Is this a good opportunity? Timeline is this year if possible.",
        "handle": "fitness_investor_wpb",
        "lead_type": "A",
        "location": "West Palm Beach, FL",
    },
    {
        "title": "Pilates studio software issues",
        "body": "My pilates studio uses Mindbody and we're having so many issues. Schedule is a mess, front desk staff struggling, and our Google Business Profile was suspended. Need recommendations for better systems.",
        "handle": "pilates_owner_miami",
        "lead_type": "B",
        "location": "Miami, FL",
    },
]


@app.command()
def create(
    count: int = typer.Option(10, help="Number of demo leads to create"),
):
    """Create demo data for testing."""
    console.print(f"[bold blue]Creating {count} demo leads...[/bold blue]")

    # Initialize DB
    init_db()

    engine = get_engine()
    with Session(engine) as session:
        # Create demo source
        source = Source(
            name="demo",
            type=SourceType.MANUAL_IMPORT,
            enabled=True,
            config={"demo": True},
        )
        session.add(source)
        session.commit()
        session.refresh(source)

        leads_created = 0
        for i in range(count):
            # Pick random demo post
            demo = random.choice(DEMO_POSTS)

            # Create document
            doc = Document(
                source_id=source.source_id,
                external_id=f"demo_{i}_{demo['handle']}",
                url=f"https://demo.example.com/post/{i}",
                author_handle=demo["handle"],
                title=demo["title"],
                body=demo["body"],
                published_at=datetime.utcnow() - timedelta(days=random.randint(1, 30)),
                raw_json={"demo": True},
                processed=True,
            )
            session.add(doc)
            session.commit()
            session.refresh(doc)

            # Create lead
            city, state = demo["location"].split(", ")
            score = random.uniform(60.0, 95.0)

            lead = Lead(
                lead_type=LeadType.FRANCHISE_BUYER if demo["lead_type"] == "A" else LeadType.OWNER_PAIN,
                canonical_handle=demo["handle"],
                location_text=demo["location"],
                location_city=city,
                location_state=state,
                geo_confidence=GeoConfidence.HIGH,
                geo_why="Explicit city mention",
                is_florida=True,
                priority_score=score,
                tier="Ready" if score >= 80 else "Comparing" if score >= 60 else "Researching",
                status=LeadStatus.NEW,
                extracted_fields={
                    "budget_hints": ["$250k", "$400k"] if demo["lead_type"] == "A" else [],
                    "timeline_hints": ["within 6 months", "this year"] if demo["lead_type"] == "A" else [],
                    "source_count": 1,
                },
            )
            session.add(lead)
            session.commit()
            session.refresh(lead)

            # Create evidence
            evidence = Evidence(
                lead_id=lead.lead_id,
                doc_id=doc.doc_id,
                snippet=demo["body"][:300],
                reasons=[
                    "First-person intent detected",
                    "Location signals: Florida",
                    "Question format detected",
                ],
                score=score,
                tier=lead.tier,
                extracted_fields={"demo": True},
            )
            session.add(evidence)
            session.commit()

            leads_created += 1

    console.print(f"[bold green]✓ Created {leads_created} demo leads[/bold green]")
    console.print("\nTry these commands:")
    console.print("  python -m franchise_radar list-leads")
    console.print("  python -m franchise_radar export csv --output demo_leads.csv")


@app.command()
def clear():
    """Clear all demo data."""
    console.print("[bold yellow]Clearing demo data...[/bold yellow]")

    engine = get_engine()
    with Session(engine) as session:
        # Delete demo source and all related data
        from sqlmodel import delete
        from ..models import Source

        stmt = delete(Source).where(Source.name == "demo")
        session.exec(stmt)
        session.commit()

    console.print("[bold green]✓ Demo data cleared[/bold green]")
