# Database infrastructure

PostgreSQL is provisioned locally through Docker Compose. SQLAlchemy connection handling is in `apps/backend/app/database/connection.py`; Alembic migration configuration lives with the backend. No domain tables or migration revisions are defined until the product data model is specified.
