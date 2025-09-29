---
applyTo: '**'
---
 Project Context & Guidelines for AI Assistance (Inventory Project)

 Project Context
- Framework: Django + Django REST Framework (DRF).  
- Architecture: Shared-tenant approach using PostgreSQL schemas.  
- Database: PostgreSQL 15+.  
- Services: Docker and Docker Compose used for local development and deployment.  
- Purpose: Build an Inventory Management API with multi-tenant support (shared-tenant schema-based).  

 Coding Guidelines
1. Structure
   - Use Django apps to separate concerns (e.g., `users`, `products`, `orders`, `tenants`).
   - Place serializers, views, and urls inside their respective app folders.
   - Use DRF viewsets where possible, with `routers` for clean API endpoints.

2. Tenancy
   - Every tenant should be separated by schema.
   - Ensure middleware handles schema switching based on the request domain or headers.
   - Database queries must always be schema-aware.

3. Database
   - Use Django migrations for schema changes.
   - Write models with clear `__str__` methods and verbose names.
   - Keep database configuration in `settings.py`, but secrets should be stored in environment variables.

4. API Standards
   - Follow REST best practices (use nouns for endpoints, plural form, lowercase).
   - Support CRUD operations (Create, Read, Update, Delete).
   - Use proper HTTP status codes.
   - Always return JSON responses.
   - Validate data in serializers, not in views.

5. Authentication & Authorization
   - Use JWT (SimpleJWT) for authentication.
   - Apply DRF permissions and custom permissions for tenant-based access.
   - Never expose sensitive data in API responses.

6. Code Style
   - Follow PEP8 for Python code formatting.
   - Keep functions small and focused.
   - Add docstrings to models, views, and serializers.
   - Write descriptive commit messages.

7. Other Rules
   - Use `.env` files for local configs (never hardcode secrets).
   - Document new APIs in `README.md` or OpenAPI schema.
   - Ensure CI/CD compatibility (tests should run in Docker).

 Output Rules for AI
- Generate complete, runnable code (no pseudo-code unless requested).
- Provide file names and paths when creating new files.
- Explain reasoning when making design choices.
- When asked for fixes, show the minimal code changes required.
