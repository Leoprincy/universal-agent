from datetime import datetime
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ConflictError, NotFoundError
from app.database.models import Base, Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.project import ProjectService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def test_create_and_get_project(db_session):
    service = ProjectService(db_session)
    data = ProjectCreate(
        name="Android Part-Time Jobs App",
        description="A mobile platform connecting students with local part-time jobs.",
        category="mobile_app",
        target_audience="College students and local small businesses",
        metadata={"platform": "Android", "min_sdk": 26},
    )
    created = service.create_project(data)

    assert created.id is not None
    assert created.name == "Android Part-Time Jobs App"
    assert created.slug == "android-part-time-jobs-app"
    assert created.status == "active"
    assert created.category == "mobile_app"
    assert created.metadata_json == {"platform": "Android", "min_sdk": 26}
    assert isinstance(created.created_at, datetime)

    # Fetch by ID
    by_id = service.get_project(created.id)
    assert by_id.id == created.id

    # Fetch by slug
    by_slug = service.get_project("android-part-time-jobs-app")
    assert by_slug.id == created.id


def test_create_project_auto_suffixes_colliding_slug(db_session):
    service = ProjectService(db_session)
    p1 = service.create_project(ProjectCreate(name="Growth Engine"))
    p2 = service.create_project(ProjectCreate(name="Growth Engine"))

    assert p1.slug == "growth-engine"
    assert p2.slug == "growth-engine-1"


def test_create_project_explicit_duplicate_slug_raises_conflict(db_session):
    service = ProjectService(db_session)
    service.create_project(ProjectCreate(name="Project A", slug="custom-slug"))
    with pytest.raises(ConflictError):
        service.create_project(ProjectCreate(name="Project B", slug="custom-slug"))


def test_list_projects_with_filters(db_session):
    service = ProjectService(db_session)
    service.create_project(ProjectCreate(name="App 1", category="mobile_app"))
    service.create_project(ProjectCreate(name="App 2", category="saas"))

    all_items = service.list_projects()
    assert len(all_items) == 2

    mobile_items = service.list_projects(category="mobile_app")
    assert len(mobile_items) == 1
    assert mobile_items[0].name == "App 1"


def test_update_and_delete_project(db_session):
    service = ProjectService(db_session)
    p = service.create_project(ProjectCreate(name="Old Name"))

    updated = service.update_project(
        p.id,
        ProjectUpdate(name="New Name", status="paused", description="Updated description"),
    )
    assert updated.name == "New Name"
    assert updated.status == "paused"
    assert updated.description == "Updated description"

    service.delete_project(p.id)
    with pytest.raises(NotFoundError):
        service.get_project(p.id)
