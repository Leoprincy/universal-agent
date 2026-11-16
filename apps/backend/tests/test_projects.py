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

    all_items, total = service.list_projects()
    assert len(all_items) == 2
    assert total == 2

    mobile_items, mobile_total = service.list_projects(category="mobile_app")
    assert len(mobile_items) == 1
    assert mobile_total == 1
    assert mobile_items[0].name == "App 1"


def test_list_projects_status_filtering(db_session):
    service = ProjectService(db_session)
    p1 = service.create_project(ProjectCreate(name="Active App"))
    p2 = service.create_project(ProjectCreate(name="Paused App"))
    service.update_project(p2.id, ProjectUpdate(status="paused"))

    active_items, active_total = service.list_projects(status="active")
    assert active_total == 1
    assert active_items[0].name == "Active App"

    paused_items, paused_total = service.list_projects(status="paused")
    assert paused_total == 1
    assert paused_items[0].name == "Paused App"


def test_list_projects_pagination(db_session):
    service = ProjectService(db_session)
    for i in range(10):
        service.create_project(ProjectCreate(name=f"Project {i:02d}"))

    # First page: limit 3, offset 0
    page1, total = service.list_projects(limit=3, offset=0)
    assert total == 10
    assert len(page1) == 3

    # Second page: limit 3, offset 3
    page2, total = service.list_projects(limit=3, offset=3)
    assert total == 10
    assert len(page2) == 3
    # Check stable distinct pages
    page1_ids = {p.id for p in page1}
    page2_ids = {p.id for p in page2}
    assert page1_ids.isdisjoint(page2_ids)

    # Offset at boundary: offset 9
    boundary_page, total = service.list_projects(limit=5, offset=9)
    assert total == 10
    assert len(boundary_page) == 1

    # Out of range offset: offset 20
    empty_page, total = service.list_projects(limit=5, offset=20)
    assert total == 10
    assert len(empty_page) == 0


def test_list_projects_pagination_combined_with_filters(db_session):
    service = ProjectService(db_session)
    for i in range(5):
        service.create_project(ProjectCreate(name=f"Mobile App {i}", category="mobile_app"))
    for i in range(3):
        service.create_project(ProjectCreate(name=f"SaaS App {i}", category="saas"))

    items, total = service.list_projects(category="mobile_app", limit=2, offset=0)
    assert total == 5
    assert len(items) == 2
    assert all(p.category == "mobile_app" for p in items)

    items_p2, total_p2 = service.list_projects(category="mobile_app", limit=2, offset=2)
    assert total_p2 == 5
    assert len(items_p2) == 2


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


def test_update_missing_project_raises_not_found(db_session):
    service = ProjectService(db_session)
    with pytest.raises(NotFoundError):
        service.update_project("non-existent-id", ProjectUpdate(name="New"))


def test_slug_generation_bounded_collision(db_session):
    service = ProjectService(db_session)
    # Generate same base name multiple times
    p1 = service.create_project(ProjectCreate(name="Test Item"))
    p2 = service.create_project(ProjectCreate(name="Test Item"))
    assert p1.slug == "test-item"
    assert p2.slug == "test-item-1"


def test_project_owner_isolation(db_session):
    service = ProjectService(db_session)
    p_team_a = service.create_project(ProjectCreate(name="Team A App"), owner="team-a")
    p_team_b = service.create_project(ProjectCreate(name="Team B App"), owner="team-b")

    # Team A list only sees Team A
    items_a, total_a = service.list_projects(owner="team-a")
    assert total_a == 1
    assert items_a[0].id == p_team_a.id

    # Team B list only sees Team B
    items_b, total_b = service.list_projects(owner="team-b")
    assert total_b == 1
    assert items_b[0].id == p_team_b.id

    # Team B cannot fetch Team A's project
    with pytest.raises(NotFoundError):
        service.get_project(p_team_a.id, owner="team-b")

    # Team B cannot update Team A's project
    with pytest.raises(NotFoundError):
        service.update_project(p_team_a.id, ProjectUpdate(name="Hacked"), owner="team-b")

    # Team B cannot delete Team A's project
    with pytest.raises(NotFoundError):
        service.delete_project(p_team_a.id, owner="team-b")
