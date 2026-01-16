"""Tests for deduplication engine."""

import pytest
from sqlmodel import Session, create_engine
from franchise_radar.models import Source, Document, init_db
from franchise_radar.models.database import SourceType
from franchise_radar.dedupe import DedupeEngine


@pytest.fixture
def session():
    """Create test database session."""
    engine = create_engine("sqlite:///:memory:")
    init_db()
    with Session(engine) as session:
        yield session


@pytest.fixture
def test_source(session):
    """Create test source."""
    source = Source(
        name="test",
        type=SourceType.MANUAL_IMPORT,
        enabled=True,
        config={},
    )
    session.add(source)
    session.commit()
    session.refresh(source)
    return source


def test_dedupe_by_url(session, test_source):
    """Test deduplication by exact URL match."""
    # Create documents with same URL
    url = "https://example.com/post1"

    doc1 = Document(
        source_id=test_source.source_id,
        external_id="doc1",
        url=url,
        author_handle="user1",
        title="Title 1",
        body="Content about franchises",
    )
    doc2 = Document(
        source_id=test_source.source_id,
        external_id="doc2",
        url=url,
        author_handle="user2",
        title="Title 2",
        body="More content",
    )

    session.add(doc1)
    session.add(doc2)
    session.commit()

    engine = DedupeEngine(session)
    url_groups = engine.deduplicate_by_url([doc1.doc_id, doc2.doc_id])

    assert len(url_groups) == 1
    assert url in url_groups
    assert len(url_groups[url]) == 2


def test_dedupe_by_handle(session, test_source):
    """Test deduplication by author handle."""
    # Create documents with similar handles
    doc1 = Document(
        source_id=test_source.source_id,
        external_id="doc1",
        url="https://example.com/post1",
        author_handle="fitness_entrepreneur",
        title="Title 1",
        body="Content",
    )
    doc2 = Document(
        source_id=test_source.source_id,
        external_id="doc2",
        url="https://example.com/post2",
        author_handle="fitness_entrepreneur",
        title="Title 2",
        body="More content",
    )

    session.add(doc1)
    session.add(doc2)
    session.commit()

    engine = DedupeEngine(session)
    handle_groups = engine.deduplicate_by_handle([doc1.doc_id, doc2.doc_id])

    assert len(handle_groups) == 1
    canonical_handle = list(handle_groups.keys())[0]
    assert len(handle_groups[canonical_handle]) == 2


def test_dedupe_by_text_similarity(session, test_source):
    """Test deduplication by text similarity."""
    # Create documents with similar content
    content = "Looking for gym franchise opportunities in Miami"

    doc1 = Document(
        source_id=test_source.source_id,
        external_id="doc1",
        url="https://example.com/post1",
        title="Franchise question",
        body=content,
    )
    doc2 = Document(
        source_id=test_source.source_id,
        external_id="doc2",
        url="https://example.com/post2",
        title="Franchise opportunities",
        body=content + " - any recommendations?",
    )

    session.add(doc1)
    session.add(doc2)
    session.commit()

    engine = DedupeEngine(session)
    text_groups = engine.deduplicate_by_text_similarity([doc1.doc_id, doc2.doc_id])

    # Should be grouped together due to high similarity
    assert len(text_groups) == 1
