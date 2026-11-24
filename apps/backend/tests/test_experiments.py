"""Phase 7 Milestone 2: experiment lifecycle, outcomes, evaluation, API."""

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db_session
from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import Base
from app.main import create_app
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentOutcomeCreate,
    ExperimentTransition,
    ExperimentUpdate,
    SuccessCriteria,
    SuccessCriterion,
)
from app.schemas.goal import StrategyGoalCreate
from app.schemas.project import ProjectCreate
from app.schemas.strategy import GrowthStrategyCreate
from app.services.experiment import ExperimentService
from app.services.evaluation import evaluate_experiment
from app.services.goal import GoalService
from app.services.project import ProjectService
from app.services.strategy import StrategyService


def _criteria(metric="conversions", comparator="gte", threshold=10.0, **kw):
    return SuccessCriteria(
        criteria=[SuccessCriterion(metric_name=metric, comparator=comparator, threshold=threshold, **kw)]
    )


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys = OFF;")
            Base.metadata.drop_all(bind=conn)


@pytest.fixture
def project(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Exp Project"))


@pytest.fixture
def other_project(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Other Project"))


@pytest.fixture
def strategy(db_session, project):
    return StrategyService(db_session).create_strategy(
        GrowthStrategyCreate(
            name="Exp Strategy",
            strategic_vision="Vision",
            target_audience="Users",
            time_horizon="Q1",
        ),
        project_id=project.id,
        actor="admin",
    )


@pytest.fixture
def other_strategy(db_session, other_project):
    return StrategyService(db_session).create_strategy(
        GrowthStrategyCreate(
            name="Other Strategy",
            strategic_vision="V",
            target_audience="U",
            time_horizon="Q1",
        ),
        project_id=other_project.id,
        actor="admin",
    )


@pytest.fixture
def goal(db_session, strategy, project):
    return GoalService(db_session).create_goal(
        strategy.id,
        StrategyGoalCreate(
            name="Signups",
            metric_name="signups",
            metric_unit="count",
            baseline_value=0,
            target_value=100,
        ),
        project_id=project.id,
        actor="admin",
    )


@pytest.fixture
def service(db_session):
    return ExperimentService(db_session)


def _create_exp(service, strategy, project, **kw):
    return service.create_experiment(
        strategy.id,
        ExperimentCreate(name="Exp 1", success_criteria=_criteria(), **kw),
        project_id=project.id,
        actor="admin",
    )


def _start(service, exp, strategy, project):
    service.transition_experiment(
        exp.id, strategy.id, ExperimentTransition(status="in_review"), project.id, "admin"
    )
    return service.transition_experiment(
        exp.id, strategy.id, ExperimentTransition(status="running"), project.id, "admin"
    )


def _outcome(service, exp, strategy, project, value=12.0, metric="conversions", **kw):
    observed_at = kw.pop("observed_at", datetime.now(timezone.utc))
    return service.record_outcome(
        exp.id,
        strategy.id,
        ExperimentOutcomeCreate(
            metric_name=metric,
            value=value,
            observed_at=observed_at,
            **kw,
        ),
        project_id=project.id,
        actor="admin",
    )


class TestExperimentCRUD:
    def test_create_and_get(self, service, strategy, project):
        exp = _create_exp(service, strategy, project, hypothesis="H")
        assert exp.status == "draft"
        assert exp.strategy_id == strategy.id
        assert exp.project_id == project.id
        fetched = service.get_experiment(exp.id, strategy.id, project_id=project.id)
        assert fetched.id == exp.id

    def test_create_with_goal(self, service, strategy, project, goal):
        exp = _create_exp(service, strategy, project, goal_id=goal.id)
        assert exp.goal_id == goal.id

    def test_create_goal_wrong_strategy_rejected(self, service, strategy, project, db_session, other_strategy, other_project):
        other_goal = GoalService(db_session).create_goal(
            other_strategy.id,
            StrategyGoalCreate(
                name="G", metric_name="m", metric_unit="u",
                baseline_value=0, target_value=1,
            ),
            project_id=other_project.id,
            actor="admin",
        )
        with pytest.raises(NotFoundError):
            _create_exp(service, strategy, project, goal_id=other_goal.id)

    def test_list_and_filter(self, service, strategy, project):
        _create_exp(service, strategy, project)
        _create_exp(service, strategy, project)
        items, total = service.list_experiments(strategy.id, project_id=project.id)
        assert total == 2 and len(items) == 2
        _, t2 = service.list_experiments(strategy.id, project_id=project.id, status="draft")
        assert t2 == 2
        with pytest.raises(UnprocessableEntityError):
            service.list_experiments(strategy.id, project_id=project.id, status="bogus")

    def test_cross_project_isolation(self, service, strategy, project, other_project, other_strategy):
        exp = _create_exp(service, strategy, project)
        with pytest.raises(NotFoundError):
            service.get_experiment(exp.id, other_strategy.id, project_id=other_project.id)
        with pytest.raises(NotFoundError):
            service.get_experiment(exp.id, strategy.id, project_id=other_project.id)

    def test_ends_at_must_be_future(self, service, strategy, project):
        with pytest.raises(UnprocessableEntityError):
            _create_exp(
                service, strategy, project,
                ends_at=datetime.now(timezone.utc) - timedelta(days=1),
            )


class TestLifecycle:
    def test_valid_transitions_and_history(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        exp = _start(service, exp, strategy, project)
        assert exp.status == "running"
        assert exp.started_at is not None
        exp = service.transition_experiment(
            exp.id, strategy.id,
            ExperimentTransition(status="completed"), project.id, "admin",
        )
        assert exp.status == "completed"
        history = service.get_history(exp.id, strategy.id, project_id=project.id)
        statuses = [(h.previous_status, h.new_status) for h in history]
        assert statuses == [
            (None, "draft"),
            ("draft", "in_review"),
            ("in_review", "running"),
            ("running", "completed"),
        ]

    def test_invalid_transitions(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        with pytest.raises(ConflictError):
            service.transition_experiment(
                exp.id, strategy.id,
                ExperimentTransition(status="running"), project.id, "admin",
            )
        with pytest.raises(ConflictError):
            service.transition_experiment(
                exp.id, strategy.id,
                ExperimentTransition(status="draft"), project.id, "admin",
            )

    def test_reason_required_for_revert_and_cancel_running(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        service.transition_experiment(
            exp.id, strategy.id, ExperimentTransition(status="in_review"), project.id, "admin"
        )
        with pytest.raises(UnprocessableEntityError):
            service.transition_experiment(
                exp.id, strategy.id,
                ExperimentTransition(status="draft", reason="short"), project.id, "admin",
            )
        service.transition_experiment(
            exp.id, strategy.id, ExperimentTransition(status="running"), project.id, "admin"
        )
        with pytest.raises(UnprocessableEntityError):
            service.transition_experiment(
                exp.id, strategy.id,
                ExperimentTransition(status="cancelled"), project.id, "admin",
            )

    def test_terminal_states(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        _start(service, exp, strategy, project)
        exp = service.transition_experiment(
            exp.id, strategy.id, ExperimentTransition(status="cancelled", reason="Enough data, stopping early"),
            project.id, "admin",
        )
        with pytest.raises(ConflictError):
            service.transition_experiment(
                exp.id, strategy.id, ExperimentTransition(status="running"), project.id, "admin"
            )

    def test_fields_immutable_after_draft(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        _start(service, exp, strategy, project)
        with pytest.raises(ConflictError):
            service.update_experiment(
                exp.id, strategy.id,
                ExperimentUpdate(name="New name"), project.id, "admin",
            )
        with pytest.raises(ConflictError):
            service.update_experiment(
                exp.id, strategy.id,
                ExperimentUpdate(success_criteria=_criteria(threshold=99)), project.id, "admin",
            )
        # ends_at remains adjustable
        new_end = datetime.now(timezone.utc) + timedelta(days=30)
        updated = service.update_experiment(
            exp.id, strategy.id, ExperimentUpdate(ends_at=new_end), project.id, "admin"
        )
        assert updated.ends_at is not None

    def test_draft_update_allowed(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        updated = service.update_experiment(
            exp.id, strategy.id,
            ExperimentUpdate(name="Renamed", hypothesis="New hyp"),
            project.id, "admin",
        )
        assert updated.name == "Renamed"


class TestOutcomes:
    def test_record_and_list(self, service, strategy, project):
        exp = _start(service, _create_exp(service, strategy, project), strategy, project)
        o = _outcome(service, exp, strategy, project, value=15.0, sample_size=200)
        assert o.source == "manual" and o.actor == "admin"
        items = service.list_outcomes(exp.id, strategy.id, project_id=project.id)
        assert len(items) == 1
        filtered = service.list_outcomes(
            exp.id, strategy.id, project_id=project.id, metric_name="conversions"
        )
        assert len(filtered) == 1

    def test_outcome_rejected_in_draft(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        with pytest.raises(ConflictError):
            _outcome(service, exp, strategy, project)

    def test_observed_at_validation(self, service, strategy, project):
        exp = _start(service, _create_exp(service, strategy, project), strategy, project)
        with pytest.raises(UnprocessableEntityError):
            _outcome(
                service, exp, strategy, project,
                observed_at=datetime.now(timezone.utc) + timedelta(days=1),
            )
        with pytest.raises(UnprocessableEntityError):
            _outcome(
                service, exp, strategy, project,
                observed_at=datetime.now(timezone.utc) - timedelta(days=30),
            )

    def test_supersede_preserves_original(self, service, strategy, project, db_session):
        exp = _start(service, _create_exp(service, strategy, project), strategy, project)
        original = _outcome(service, exp, strategy, project, value=5.0)
        corrected = _outcome(
            service, exp, strategy, project, value=50.0, supersedes_id=original.id
        )
        assert corrected.supersedes_id == original.id
        # Original still exists and is retrievable
        items = service.list_outcomes(exp.id, strategy.id, project_id=project.id)
        assert len(items) == 2
        # Double supersede rejected
        with pytest.raises(ConflictError):
            _outcome(service, exp, strategy, project, value=60.0, supersedes_id=original.id)
        # Supersede of nonexistent outcome rejected
        with pytest.raises(NotFoundError):
            _outcome(service, exp, strategy, project, value=1.0, supersedes_id="nope")


class TestEvaluation:
    def _running_exp(self, service, strategy, project, **crit_kw):
        exp = service.create_experiment(
            strategy.id,
            ExperimentCreate(
                name="Eval Exp",
                success_criteria=SuccessCriteria(
                    criteria=[SuccessCriterion(metric_name="conversions", comparator="gte", threshold=10.0, **crit_kw)]
                ),
            ),
            project_id=project.id,
            actor="admin",
        )
        return _start(service, exp, strategy, project)

    def test_succeeded_gte_boundary(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project)
        _outcome(service, exp, strategy, project, value=10.0, sample_size=50)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "succeeded"
        crit = ev.rationale_json["criteria"][0]
        assert crit["status"] == "pass" and crit["observed_value"] == 10.0
        assert "causation" in ev.rationale_json["note"]

    def test_failed_below_threshold(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project)
        _outcome(service, exp, strategy, project, value=9.99)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "failed"

    def test_lt_comparator(self, service, strategy, project):
        exp = service.create_experiment(
            strategy.id,
            ExperimentCreate(
                name="Churn",
                success_criteria=_criteria(metric="churn", comparator="lt", threshold=5.0),
            ),
            project_id=project.id,
            actor="admin",
        )
        _start(service, exp, strategy, project)
        _outcome(service, exp, strategy, project, metric="churn", value=3.0)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "succeeded"

    def test_missing_outcomes_inconclusive(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "inconclusive"
        assert "no observed outcome" in ev.rationale_json["criteria"][0]["reason"]

    def test_insufficient_sample_inconclusive(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project, min_sample_size=100)
        _outcome(service, exp, strategy, project, value=50.0, sample_size=10)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "inconclusive"
        assert "insufficient sample" in ev.rationale_json["criteria"][0]["reason"]

    def test_incomplete_window_inconclusive(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project, window_days=7)
        _outcome(service, exp, strategy, project, value=99.0)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "inconclusive"
        assert "window incomplete" in ev.rationale_json["criteria"][0]["reason"]

    def test_completed_window_evaluates(self, service, strategy, project, db_session):
        exp = self._running_exp(service, strategy, project, window_days=7)
        # Simulate elapsed window
        exp.started_at = datetime.now(timezone.utc) - timedelta(days=10)
        db_session.commit()
        _outcome(
            service, exp, strategy, project, value=99.0,
            observed_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "succeeded"

    def test_metric_mismatch_inconclusive(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project)
        _outcome(service, exp, strategy, project, metric="other_metric", value=999.0)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "inconclusive"

    def test_superseded_outcome_excluded(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project)
        bad = _outcome(service, exp, strategy, project, value=1.0)
        _outcome(service, exp, strategy, project, value=50.0, supersedes_id=bad.id)
        ev = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert ev.verdict == "succeeded"
        assert ev.rationale_json["criteria"][0]["observed_value"] == 50.0

    def test_reevaluation_appends(self, service, strategy, project):
        exp = self._running_exp(service, strategy, project)
        _outcome(service, exp, strategy, project, value=50.0)
        e1 = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        e2 = service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
        assert e1.id != e2.id and e1.verdict == e2.verdict == "succeeded"
        all_evals = service.list_evaluations(exp.id, strategy.id, project_id=project.id)
        assert len(all_evals) == 2

    def test_evaluate_requires_running_or_completed(self, service, strategy, project):
        exp = _create_exp(service, strategy, project)
        with pytest.raises(ConflictError):
            service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")

    def test_no_criteria_rejected_at_eval(self, service, strategy, project):
        exp = service.create_experiment(
            strategy.id, ExperimentCreate(name="Bare"), project_id=project.id, actor="admin"
        )
        _start(service, exp, strategy, project)
        with pytest.raises(UnprocessableEntityError):
            service.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")


class TestEvaluationEngine:
    """Pure-function edge cases."""

    def _out(self, metric, value, sample=None, at=None):
        class O:
            pass
        o = O()
        o.metric_name = metric
        o.value = value
        o.sample_size = sample
        o.observed_at = at or datetime.now(timezone.utc)
        return o

    def test_empty_criteria_inconclusive(self):
        r = evaluate_experiment([], [], None, None)
        assert r.verdict == "inconclusive"

    def test_multi_criteria_all_pass(self):
        crit = [
            {"metric_name": "a", "comparator": "gt", "threshold": 1},
            {"metric_name": "b", "comparator": "lte", "threshold": 5},
        ]
        outs = [self._out("a", 2), self._out("b", 5)]
        r = evaluate_experiment(crit, outs, datetime.now(timezone.utc) - timedelta(days=1), None)
        assert r.verdict == "succeeded"

    def test_multi_criteria_one_fail(self):
        crit = [
            {"metric_name": "a", "comparator": "gt", "threshold": 1},
            {"metric_name": "b", "comparator": "lt", "threshold": 5},
        ]
        outs = [self._out("a", 2), self._out("b", 9)]
        r = evaluate_experiment(crit, outs, datetime.now(timezone.utc) - timedelta(days=1), None)
        assert r.verdict == "failed"

    def test_latest_outcome_in_window_used(self):
        crit = [{"metric_name": "m", "comparator": "gte", "threshold": 10}]
        old = self._out("m", 1.0, at=datetime.now(timezone.utc) - timedelta(days=2))
        new = self._out("m", 20.0, at=datetime.now(timezone.utc) - timedelta(hours=1))
        start = datetime.now(timezone.utc) - timedelta(days=1)
        r = evaluate_experiment(crit, [old, new], start, None)
        assert r.verdict == "succeeded"
        assert r.rationale["criteria"][0]["observed_value"] == 20.0

    def test_naive_datetime_handled(self):
        crit = [{"metric_name": "m", "comparator": "gte", "threshold": 1}]
        naive_start = datetime.utcnow() - timedelta(days=1)
        outs = [self._out("m", 5.0)]
        r = evaluate_experiment(crit, outs, naive_start, None)
        assert r.verdict == "succeeded"


# ── API tests ────────────────────────────────────────────────────────────


@pytest.fixture
def test_app():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON;")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app = create_app(Settings(_env_file=None, environment="test", database_url=None, redis_url=None))
    app.dependency_overrides[get_db_session] = override_get_db_session
    yield app
    Base.metadata.drop_all(bind=engine)


def test_experiment_api_full_flow(test_app):
    async def run():
        async with test_app.router.lifespan_context(test_app):
            async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
                p = await client.post("/api/v1/projects", json={"name": "API Exp"})
                pid = p.json()["id"]
                s = await client.post(
                    f"/api/v1/projects/{pid}/strategies",
                    json={
                        "name": "S", "strategic_vision": "v", "target_audience": "u",
                        "time_horizon": "Q1",
                    },
                )
                assert s.status_code == 201, s.text
                sid = s.json()["id"]

                # Create experiment
                r = await client.post(
                    f"/api/v1/projects/{pid}/strategies/{sid}/experiments",
                    json={
                        "name": "Landing test",
                        "hypothesis": "New CTA lifts signups",
                        "success_criteria": {
                            "criteria": [
                                {
                                    "metric_name": "signups",
                                    "comparator": "gte",
                                    "threshold": 100,
                                    "min_sample_size": 10,
                                }
                            ]
                        },
                    },
                )
                assert r.status_code == 201, r.text
                eid = r.json()["id"]
                assert r.json()["status"] == "draft"

                # List
                lst = await client.get(f"/api/v1/projects/{pid}/strategies/{sid}/experiments")
                assert lst.status_code == 200 and lst.json()["total"] == 1

                # Invalid transition draft->running
                bad = await client.post(
                    f"/api/v1/projects/{pid}/strategies/{sid}/experiments/{eid}/transition",
                    json={"status": "running"},
                )
                assert bad.status_code == 409

                # Valid path to running
                for st in ("in_review", "running"):
                    tr = await client.post(
                        f"/api/v1/projects/{pid}/strategies/{sid}/experiments/{eid}/transition",
                        json={"status": st},
                    )
                    assert tr.status_code == 200, tr.text

                # History
                hist = await client.get(
                    f"/api/v1/projects/{pid}/strategies/{sid}/experiments/{eid}/history"
                )
                assert hist.status_code == 200
                assert [h["new_status"] for h in hist.json()] == ["draft", "in_review", "running"]

                # Outcome
                oc = await client.post(
                    f"/api/v1/projects/{pid}/strategies/{sid}/experiments/{eid}/outcomes",
                    json={
                        "metric_name": "signups",
                        "value": 120,
                        "sample_size": 50,
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "source": "manual",
                    },
                )
                assert oc.status_code == 201, oc.text

                # Evaluate → succeeded
                ev = await client.post(
                    f"/api/v1/projects/{pid}/strategies/{sid}/experiments/{eid}/evaluate"
                )
                assert ev.status_code == 201, ev.text
                assert ev.json()["verdict"] == "succeeded"

                # Evaluations list has 1
                evs = await client.get(
                    f"/api/v1/projects/{pid}/strategies/{sid}/experiments/{eid}/evaluations"
                )
                assert len(evs.json()) == 1

                # Cross-project 404
                p2 = await client.post("/api/v1/projects", json={"name": "Other"})
                pid2 = p2.json()["id"]
                nf = await client.get(
                    f"/api/v1/projects/{pid2}/strategies/{sid}/experiments/{eid}"
                )
                assert nf.status_code == 404

    import asyncio
    asyncio.run(run())
