"""Phase 7 Milestone 3: learning records, evidence, deletion blockers."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.errors import ConflictError, NotFoundError, UnprocessableEntityError
from app.database.models import Base
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentOutcomeCreate,
    ExperimentTransition,
    SuccessCriteria,
    SuccessCriterion,
)
from app.schemas.learning import LearningCreate, LearningEvidence, LearningUpdate
from app.schemas.project import ProjectCreate
from app.schemas.strategy import GrowthStrategyCreate
from app.services.experiment import ExperimentService
from app.services.learning import LearningService
from app.services.project import ProjectService
from app.services.strategy import StrategyService


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
    return ProjectService(db_session).create_project(ProjectCreate(name="Learn Project"))


@pytest.fixture
def other_project(db_session):
    return ProjectService(db_session).create_project(ProjectCreate(name="Other"))


@pytest.fixture
def strategy(db_session, project):
    return StrategyService(db_session).create_strategy(
        GrowthStrategyCreate(
            name="S", strategic_vision="v", target_audience="u", time_horizon="q"
        ),
        project_id=project.id,
        actor="admin",
    )


@pytest.fixture
def other_strategy(db_session, other_project):
    return StrategyService(db_session).create_strategy(
        GrowthStrategyCreate(
            name="OS", strategic_vision="v", target_audience="u", time_horizon="q"
        ),
        project_id=other_project.id,
        actor="admin",
    )


@pytest.fixture
def learning_service(db_session):
    return LearningService(db_session)


@pytest.fixture
def experiment_service(db_session):
    return ExperimentService(db_session)


def _mk_learning(svc, project, **kw):
    return svc.create(
        LearningCreate(
            title=kw.pop("title", "Insight"),
            insight=kw.pop("insight", "Validated observation"),
            **kw,
        ),
        project_id=project.id,
        actor="admin",
    )


def _running_experiment_with_evidence(esvc, strategy, project):
    exp = esvc.create_experiment(
        strategy.id,
        ExperimentCreate(
            name="E",
            success_criteria=SuccessCriteria(
                criteria=[
                    SuccessCriterion(
                        metric_name="m", comparator="gte", threshold=1.0
                    )
                ]
            ),
        ),
        project_id=project.id,
        actor="admin",
    )
    esvc.transition_experiment(
        exp.id, strategy.id, ExperimentTransition(status="in_review"), project.id, "admin"
    )
    exp = esvc.transition_experiment(
        exp.id, strategy.id, ExperimentTransition(status="running"), project.id, "admin"
    )
    outcome = esvc.record_outcome(
        exp.id,
        strategy.id,
        ExperimentOutcomeCreate(
            metric_name="m",
            value=5.0,
            observed_at=datetime.now(timezone.utc),
        ),
        project_id=project.id,
        actor="admin",
    )
    evaluation = esvc.evaluate(exp.id, strategy.id, project_id=project.id, actor="admin")
    return exp, outcome, evaluation


class TestLearningCRUD:
    def test_create_candidate_and_get(self, learning_service, project):
        rec = _mk_learning(learning_service, project, category="messaging")
        assert rec.status == "candidate"
        fetched = learning_service.get(rec.id, project_id=project.id)
        assert fetched.title == "Insight"

    def test_list_and_filters(self, learning_service, project, strategy):
        _mk_learning(learning_service, project, category="a")
        _mk_learning(learning_service, project, category="b", strategy_id=strategy.id)
        items, total = learning_service.list(project_id=project.id)
        assert total == 2
        _, t = learning_service.list(project_id=project.id, category="a")
        assert t == 1
        _, t2 = learning_service.list(project_id=project.id, strategy_id=strategy.id)
        assert t2 == 1
        with pytest.raises(UnprocessableEntityError):
            learning_service.list(project_id=project.id, status="bogus")

    def test_update_candidate(self, learning_service, project):
        rec = _mk_learning(learning_service, project)
        updated = learning_service.update(
            rec.id,
            LearningUpdate(title="Better title", insight="New insight"),
            project_id=project.id,
            actor="admin",
        )
        assert updated.title == "Better title"

    def test_cross_project_isolation(self, learning_service, project, other_project):
        rec = _mk_learning(learning_service, project)
        with pytest.raises(NotFoundError):
            learning_service.get(rec.id, project_id=other_project.id)
        with pytest.raises(NotFoundError):
            learning_service.update(
                rec.id, LearningUpdate(title="x"), project_id=other_project.id, actor="a"
            )
        with pytest.raises(NotFoundError):
            learning_service.validate(rec.id, project_id=other_project.id, actor="a")


class TestLearningLifecycle:
    def test_validate(self, learning_service, project):
        rec = _mk_learning(learning_service, project)
        v = learning_service.validate(rec.id, project_id=project.id, actor="reviewer1")
        assert v.status == "validated"
        assert v.validated_by == "reviewer1"
        assert v.validated_at is not None

    def test_reject(self, learning_service, project):
        rec = _mk_learning(learning_service, project)
        r = learning_service.reject(
            rec.id, "Insufficient evidence for this claim", project_id=project.id, actor="rev2"
        )
        assert r.status == "rejected"
        assert r.rejected_by == "rev2"
        assert r.rejected_at is not None
        assert "Insufficient evidence" in r.rejection_reason

    def test_invalid_transitions(self, learning_service, project):
        rec = _mk_learning(learning_service, project)
        learning_service.validate(rec.id, project_id=project.id, actor="a")
        with pytest.raises(ConflictError):
            learning_service.validate(rec.id, project_id=project.id, actor="a")
        with pytest.raises(ConflictError):
            learning_service.reject(rec.id, "reason long enough", project_id=project.id, actor="a")
        with pytest.raises(ConflictError):
            learning_service.update(
                rec.id, LearningUpdate(title="tamper"), project_id=project.id, actor="a"
            )

    def test_rejected_is_terminal(self, learning_service, project):
        rec = _mk_learning(learning_service, project)
        learning_service.reject(rec.id, "Not supported by data", project_id=project.id, actor="a")
        with pytest.raises(ConflictError):
            learning_service.validate(rec.id, project_id=project.id, actor="a")
        with pytest.raises(ConflictError):
            learning_service.update(
                rec.id, LearningUpdate(insight="rewrite"), project_id=project.id, actor="a"
            )


class TestEvidence:
    def test_valid_evidence_references(
        self, learning_service, experiment_service, strategy, project
    ):
        exp, outcome, evaluation = _running_experiment_with_evidence(
            experiment_service, strategy, project
        )
        rec = learning_service.create(
            LearningCreate(
                title="CTA variant wins",
                insight="Variant B beat control on signups",
                strategy_id=strategy.id,
                experiment_id=exp.id,
                evidence=LearningEvidence(
                    outcome_ids=[outcome.id], evaluation_ids=[evaluation.id]
                ),
            ),
            project_id=project.id,
            actor="admin",
        )
        assert rec.evidence_json["outcome_ids"] == [outcome.id]
        assert rec.evidence_json["evaluation_ids"] == [evaluation.id]

    def test_missing_outcome_rejected(
        self, learning_service, experiment_service, strategy, project
    ):
        exp, _, _ = _running_experiment_with_evidence(
            experiment_service, strategy, project
        )
        with pytest.raises(NotFoundError):
            learning_service.create(
                LearningCreate(
                    title="x", insight="y", experiment_id=exp.id,
                    evidence=LearningEvidence(outcome_ids=["nonexistent"]),
                ),
                project_id=project.id, actor="a",
            )

    def test_evidence_requires_experiment(
        self, learning_service, project
    ):
        with pytest.raises(UnprocessableEntityError):
            learning_service.create(
                LearningCreate(
                    title="x", insight="y",
                    evidence=LearningEvidence(outcome_ids=["abc"]),
                ),
                project_id=project.id, actor="a",
            )

    def test_cross_project_experiment_rejected(
        self, learning_service, experiment_service, strategy, project,
        other_project, other_strategy,
    ):
        exp, _, _ = _running_experiment_with_evidence(
            experiment_service, other_strategy, other_project
        )
        with pytest.raises(NotFoundError):
            learning_service.create(
                LearningCreate(title="x", insight="y", experiment_id=exp.id),
                project_id=project.id, actor="a",
            )

    def test_outcome_from_other_experiment_rejected(
        self, learning_service, experiment_service, strategy, project
    ):
        exp1, outcome1, _ = _running_experiment_with_evidence(
            experiment_service, strategy, project
        )
        exp2 = experiment_service.create_experiment(
            strategy.id,
            ExperimentCreate(name="E2"),
            project_id=project.id, actor="a",
        )
        with pytest.raises(NotFoundError):
            learning_service.create(
                LearningCreate(
                    title="x", insight="y", experiment_id=exp2.id,
                    evidence=LearningEvidence(outcome_ids=[outcome1.id]),
                ),
                project_id=project.id, actor="a",
            )

    def test_inconsistent_strategy_experiment_links(
        self, learning_service, experiment_service, strategy, project, db_session
    ):
        s2 = StrategyService(db_session).create_strategy(
            GrowthStrategyCreate(
                name="S2", strategic_vision="v", target_audience="u", time_horizon="q"
            ),
            project_id=project.id,
            actor="admin",
        )
        exp, _, _ = _running_experiment_with_evidence(
            experiment_service, strategy, project
        )
        with pytest.raises(UnprocessableEntityError):
            learning_service.create(
                LearningCreate(
                    title="x", insight="y",
                    strategy_id=s2.id, experiment_id=exp.id,
                ),
                project_id=project.id, actor="a",
            )


class TestRecommendationIntegration:
    def test_only_validated_returned(
        self, learning_service, project
    ):
        cand = _mk_learning(learning_service, project, title="candidate")
        val = _mk_learning(learning_service, project, title="validated")
        rej = _mk_learning(learning_service, project, title="rejected")
        learning_service.validate(val.id, project_id=project.id, actor="a")
        learning_service.reject(
            rej.id, "Not supported", project_id=project.id, actor="a"
        )
        items, total = learning_service.get_validated(project_id=project.id)
        assert total == 1
        assert items[0].id == val.id
        assert items[0].status == "validated"
        # candidate and rejected never appear
        ids = {i.id for i in items}
        assert cand.id not in ids and rej.id not in ids

    def test_validated_filterable_by_strategy(
        self, learning_service, project, strategy
    ):
        a = _mk_learning(learning_service, project, strategy_id=strategy.id)
        b = _mk_learning(learning_service, project)
        for r in (a, b):
            learning_service.validate(r.id, project_id=project.id, actor="a")
        items, total = learning_service.get_validated(
            project_id=project.id, strategy_id=strategy.id
        )
        assert total == 1 and items[0].id == a.id


class TestProjectDeletionBlockers:
    def _delete(self, project_service, project):
        return project_service.delete_project(project.id, owner=None)

    def test_experiment_blocks(self, db_session, project, strategy, experiment_service):
        ps = ProjectService(db_session)
        experiment_service.create_experiment(
            strategy.id,
            ExperimentCreate(name="E"),
            project_id=project.id, actor="a",
        )
        with pytest.raises(ConflictError) as ei:
            self._delete(ps, project)
        assert ei.value.code == "cannot_delete_audited_project"
        assert "experiment" in str(ei.value).lower()

    def test_learning_blocks(self, db_session, project, learning_service):
        ps = ProjectService(db_session)
        _mk_learning(learning_service, project)
        with pytest.raises(ConflictError) as ei:
            self._delete(ps, project)
        assert "learning record" in str(ei.value)

    def test_full_experiment_trail_blocks_with_counts(
        self, db_session, project, strategy, experiment_service, learning_service
    ):
        ps = ProjectService(db_session)
        exp, outcome, evaluation = _running_experiment_with_evidence(
            experiment_service, strategy, project
        )
        learning_service.create(
            LearningCreate(
                title="t", insight="i", experiment_id=exp.id,
                evidence=LearningEvidence(outcome_ids=[outcome.id], evaluation_ids=[evaluation.id]),
            ),
            project_id=project.id, actor="a",
        )
        with pytest.raises(ConflictError) as ei:
            self._delete(ps, project)
        msg = str(ei.value)
        assert "experiment status transition" in msg
        assert "experiment outcome" in msg
        assert "experiment evaluation" in msg
        assert "learning record" in msg

    def test_clean_project_deletes(self, db_session, project):
        ps = ProjectService(db_session)
        ps.delete_project(project.id, owner=None)
        from app.database.models import Project
        from sqlalchemy import select
        assert db_session.scalar(select(Project).where(Project.id == project.id)) is None
