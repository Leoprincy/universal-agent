# Configuration

Local and deployment configuration is environment-based. `.env.example` documents the current variables; copy it to an ignored `.env` for local development. Backend settings use the `UGA_` prefix, while Compose infrastructure variables use the standard PostgreSQL names. Do not commit populated environment files.
