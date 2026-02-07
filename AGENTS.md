# Multi-Agent Workflow

**Project**: orb-tool
**Last updated**: 2026-02-07
**Source of truth**: WORKFLOW_STATE.json

## Summary

Flask-based maritime fuel tracking and engine room status app. Combines Oil Record Book compliance tracking with CAT engine manuals search (consolidated from engine_tool). Wave 1 and Wave 2 complete. LLM-powered manuals chat assistant merged (PR #6).

**Current state:**
- Authentication (Flask-Login, RBAC)
- Structured logging, request middleware, audit trail
- Database migrations (Flask-Migrate)
- Docker deployment, health check, backup scripts
- Offline support (localStorage, retry queue)
- Integration tests (23 E2E)
- API route tests, service tests, model tests
- Manuals search (FTS5), troubleshooting cards, LLM chat assistant

## Tasks

### add-api-route-tests
- **Status**: done
- **Completed**: Wave 1
- **Branch**: agent/add-api-route-tests

### add-service-and-model-tests
- **Status**: done
- **Completed**: 2025-12-27
- **Files**: tests/test_orb_service.py, tests/test_ocr_service.py, tests/test_models.py

### implement-authentication-authorization
- **Status**: done
- **Completed**: Wave 1
- **Files**: src/routes/auth.py, User model with roles, Flask-Login

### fix-datetime-deprecations
- **Status**: done
- **Completed**: 2025-12-28

### add-input-validation-security
- **Status**: done
- **Completed**: 2025-12-28
- **Files**: src/security.py, src/routes/secure_api.py

### add-logging-monitoring
- **Status**: done
- **Completed**: Wave 2
- **Files**: src/logging_config.py, src/middleware/request_logger.py

### create-database-migrations
- **Status**: done
- **Completed**: Wave 1
- **Files**: migrations/, simple_migration.py, docs/DATABASE_MIGRATIONS.md

### create-deployment-config
- **Status**: done
- **Completed**: Wave 2
- **Files**: Dockerfile, docker-compose.yml, docs/DEPLOYMENT.md

### add-error-recovery
- **Status**: done
- **Completed**: Wave 2
- **Files**: static/js/offline.js, static/js/storage.js

### add-integration-tests
- **Status**: done
- **Completed**: Wave 2
- **Files**: tests/test_integration.py, 23 E2E tests

### add-frontend-tests
- **Status**: ready
- **Priority**: low
- **Description**: Add JS tests for form validation, API handling, offline behavior.

### add-api-documentation
- **Status**: ready
- **Priority**: low
- **Description**: OpenAPI/Swagger spec for endpoints.

### improve-ocr-accuracy
- **Status**: ready
- **Priority**: low
- **Description**: Confidence scoring, manual correction UI, validation.

### add-performance-monitoring
- **Status**: ready
- **Priority**: low
- **Description**: Query profiling, caching, pagination.
- **Dependencies**: add-logging-monitoring (done)

## Parallelization Plan

**Wave 1 (Complete):** Security, auth, migrations, tests
**Wave 2 (Complete):** Logging, deployment, offline, integration tests
**Wave 3 (Ready):** Frontend tests, API docs, OCR improvements, performance

## Notes

- Duplicate API routes: `/api/*` and `/api/v1/*` both exist (secure_api is validated). Consolidation is a follow-up.
- ENGINE_TOOL references updated to orb-tool in templates and config.
- Project/logger names standardized to `orb_tool`.
