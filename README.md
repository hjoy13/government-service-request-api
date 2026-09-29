# Government Service Request Management System

A production-style REST API for managing citizen service requests, built with Django REST Framework, PostgreSQL, JWT authentication, role-based authorization, automated tests, Swagger/OpenAPI documentation, and Docker Compose.

The system supports three application roles:

- **CITIZEN** — registers, creates and manages their own service requests, uploads attachments, and participates in request conversations.
- **OFFICER** — works on requests assigned to them, updates processing fields, and participates in request conversations.
- **ADMIN** — manages categories, views all requests, assigns officers, updates processing fields, and views system statistics.

---

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Architecture](#architecture)
- [Business Roles](#business-roles)
- [Role and Permission Matrix](#role-and-permission-matrix)
- [Key Business Rules](#key-business-rules)
- [API Endpoints](#api-endpoints)
- [Filtering, Search, Ordering, and Pagination](#filtering-search-ordering-and-pagination)
- [File Attachments](#file-attachments)
- [Admin Statistics](#admin-statistics)
- [Swagger and OpenAPI](#swagger-and-openapi)
- [Environment Variables](#environment-variables)
- [Docker Quick Start](#docker-quick-start)
- [Local Development Setup](#local-development-setup)
- [Database Migrations](#database-migrations)
- [Running Tests](#running-tests)
- [Repository Structure](#repository-structure)
- [Design Decisions](#design-decisions)
- [Known Limitations](#known-limitations)
- [Verification Status](#verification-status)

---

## Features

### Authentication and Accounts

- JWT-based authentication.
- Public citizen registration.
- JWT access and refresh tokens.
- Custom Django user model with:
  - `CITIZEN`
  - `OFFICER`
  - `ADMIN`
- Public registration always creates a `CITIZEN`.
- Registration rejects attempts to set privileged or server-controlled fields such as:
  - `role`
  - `is_staff`
  - `is_superuser`
  - `is_active`
- Email addresses are normalized and enforced as unique case-insensitively.
- Django password validators are applied.

### Categories

- Authenticated users can read categories available to their role.
- Citizens and officers see active categories only.
- Admins can view all categories.
- Admin-only category creation, update, and deletion.
- Category names are unique case-insensitively.
- Categories already referenced by service requests cannot be deleted.
- Attempting to delete a category that is in use returns **409 Conflict**.
- A category can instead be made inactive.

### Service Requests

Each service request supports:

- category
- title
- description
- priority
- status
- creator
- assigned officer
- optional attachment
- creation timestamp
- update timestamp

Priority values:

```text
LOW
MEDIUM
HIGH
URGENT
```

Status values:

```text
OPEN
IN_PROGRESS
RESOLVED
CLOSED
```

Default values:

```text
status      = OPEN
priority    = MEDIUM
assigned_to = null
```

### Role-Aware Visibility

Request visibility is enforced at queryset level:

```text
CITIZEN
    → own requests only

OFFICER
    → requests assigned to that officer only

ADMIN
    → all requests
```

Requests outside a user's accessible scope normally return **404 Not Found** rather than revealing that the resource exists.

### Request Updates

Citizens may update:

- title
- description
- category
- attachment

only while their own request is still `OPEN`.

Officers may update, on requests assigned to themselves:

- priority
- status

Admins may update, on any request:

- priority
- status

The following fields are not directly writable through request `PATCH`:

- `assigned_to`
- `created_by`

Officer assignment is handled through a dedicated admin-only endpoint.

### Officer Assignment

Admins can assign or reassign requests using:

```http
POST /api/v1/requests/{id}/assign/
```

Example request body:

```json
{
  "officer_id": 7
}
```

Rules:

- Only `ADMIN` may assign.
- The target must be an active user with role `OFFICER`.
- Citizens, admins, inactive users, nonexistent users, and other invalid targets are rejected.
- Assignment does not automatically change request status.

### Comments

Nested request conversations are available through:

```http
GET  /api/v1/requests/{id}/comments/
POST /api/v1/requests/{id}/comments/
```

Access follows the parent request:

- Citizen: own requests.
- Officer: assigned requests.
- Admin: any request.

Comment rules:

- `text` is the only writable field.
- `author` is always taken from the authenticated user.
- `service_request` is always taken from the URL.
- Comments are returned oldest first.
- Comments cannot be edited or deleted through the API.

### File Attachments

A service request may contain one optional attachment.

Allowed extensions:

```text
.pdf
.jpg
.jpeg
.png
```

Maximum size:

```text
5 MB
```

Files are stored using generated UUID-based filenames rather than client-provided filenames.

The API does not expose direct media URLs. Authorized users download attachments through:

```http
GET /api/v1/requests/{id}/attachment/
```

Access is role-scoped through the parent request.

---

## Technology Stack

| Component | Technology |
|---|---|
| Language | Python 3.13 |
| Web framework | Django 5.2 LTS |
| API framework | Django REST Framework |
| Authentication | SimpleJWT |
| Database | PostgreSQL 18 |
| Filtering | django-filter |
| API documentation | drf-spectacular |
| Containerization | Docker |
| Multi-container orchestration | Docker Compose |
| Testing | Django / DRF test framework |
| Environment configuration | python-dotenv |

Main verified package versions:

```text
Django==5.2.17
djangorestframework==3.18.1
djangorestframework_simplejwt==5.5.1
django-filter==26.1
drf-spectacular==0.30.0
psycopg==3.3.6
psycopg-binary==3.3.6
python-dotenv==1.2.3
tzdata==2026.4
```

---

## Architecture

The application is implemented as a modular Django monolith.

```text
Client / Swagger / API Consumer
              │
              ▼
          /api/v1/
              │
              ▼
        Django REST Framework
              │
              ▼
      Views / ViewSets / Actions
              │
              ├── Authentication
              ├── Permissions
              ├── Role-aware querysets
              ├── Validation
              └── Business rules
              │
              ▼
           Serializers
              │
              ▼
          Django ORM
              │
              ▼
          PostgreSQL
```

Primary Django applications:

```text
apps.accounts
apps.categories
apps.service_requests
```

---

## Business Roles

### CITIZEN

Can:

- register
- log in
- create service requests
- view own requests
- view own request details
- edit citizen-controlled fields while status is `OPEN`
- upload or replace an attachment while status is `OPEN`
- view attachments on own requests
- read comments on own requests
- add comments to own requests
- read active categories

Cannot:

- view another citizen's requests
- create officer or admin accounts through registration
- assign officers
- change request status
- change priority after creation
- manage categories
- access admin statistics

### OFFICER

Can:

- log in
- view requests assigned to themselves
- change priority on assigned requests
- change status on assigned requests
- view attachments on assigned requests
- read comments on assigned requests
- add comments to assigned requests
- read active categories

Cannot:

- create citizen service requests
- access another officer's assigned request
- assign or reassign officers
- manage categories
- access admin statistics

### ADMIN

Can:

- log in
- view all service requests
- manage categories
- assign and reassign officers
- update request priority
- update request status
- view request attachments
- read and post comments
- access system statistics
- view active and inactive categories

---

## Role and Permission Matrix

| Action | Citizen | Officer | Admin |
|---|---:|---:|---:|
| Register own account | Yes | No | No |
| Login | Yes | Yes | Yes |
| Create service request | Yes | No | No |
| View own request | Yes | — | All |
| View assigned request | — | Yes | All |
| View all requests | No | No | Yes |
| Edit citizen content | Own request, `OPEN` only | No | No |
| Change status | No | Assigned only | Yes |
| Change priority | Creation only | Assigned only | Yes |
| Assign officer | No | No | Yes |
| Reassign officer | No | No | Yes |
| Comment | Own request | Assigned request | Yes |
| Download attachment | Own request | Assigned request | Yes |
| Manage categories | No | No | Yes |
| View statistics | No | No | Yes |

---

## Key Business Rules

### Registration

Public registration creates `CITIZEN` accounts only.

Privileged role escalation through registration is rejected.

### Category Selection

Inactive categories cannot be selected for new requests.

### Category Deletion

Categories referenced by service requests are protected from deletion.

The API returns:

```text
409 Conflict
```

when an admin tries to delete a category currently in use.

### Request Creation

Only citizens may create service requests through the public request endpoint.

The server controls:

```text
created_by
status
assigned_to
```

The client may provide:

```text
category
title
description
priority
attachment
```

### Request Editing

Citizen content fields can be modified only while a request is still `OPEN`.

Once processing has begun, citizens cannot rewrite request content.

### Status Changes

Citizens cannot directly change request status.

Assigned officers and admins may change status to any valid status value.

No custom state-machine transition restriction is enforced.

### Assignment

`assigned_to` is not directly writable through normal request updates.

All assignment and reassignment uses the dedicated admin action.

### Deletion

Service requests are not deletable through the API.

`PUT` is also disabled.

This keeps the API focused on partial updates and preserves service-request history.

---

## API Endpoints

Base API path:

```text
/api/v1/
```

### Authentication

| Method | Endpoint | Access |
|---|---|---|
| POST | `/api/v1/auth/register/` | Public |
| POST | `/api/v1/auth/login/` | Public |
| POST | `/api/v1/auth/token/refresh/` | Public |

### Categories

| Method | Endpoint | Access |
|---|---|---|
| GET | `/api/v1/categories/` | Authenticated |
| GET | `/api/v1/categories/{id}/` | Authenticated |
| POST | `/api/v1/categories/` | Admin |
| PATCH | `/api/v1/categories/{id}/` | Admin |
| DELETE | `/api/v1/categories/{id}/` | Admin |

Notes:

- Citizens and officers see active categories only.
- Admins can see active and inactive categories.
- `PUT` is disabled.

### Service Requests

| Method | Endpoint | Access |
|---|---|---|
| GET | `/api/v1/requests/` | Authenticated, role-scoped |
| POST | `/api/v1/requests/` | Citizen |
| GET | `/api/v1/requests/{id}/` | Authenticated, role-scoped |
| PATCH | `/api/v1/requests/{id}/` | Authenticated, role-dependent |
| POST | `/api/v1/requests/{id}/assign/` | Admin |
| GET | `/api/v1/requests/{id}/comments/` | Authenticated, role-scoped |
| POST | `/api/v1/requests/{id}/comments/` | Authenticated, role-scoped |
| GET | `/api/v1/requests/{id}/attachment/` | Authenticated, role-scoped |

`PUT` and `DELETE` are disabled for service requests.

### Statistics

| Method | Endpoint | Access |
|---|---|---|
| GET | `/api/v1/statistics/` | Admin |

### API Documentation

| Method | Endpoint | Access |
|---|---|---|
| GET | `/api/schema/` | Public |
| GET | `/api/docs/` | Public |

---

## Filtering, Search, Ordering, and Pagination

The request list supports filtering, search, ordering, and pagination.

### Filtering

Supported parameters:

```text
status
priority
category
assigned_to
unassigned
```

Examples:

```text
/api/v1/requests/?status=OPEN
/api/v1/requests/?priority=HIGH
/api/v1/requests/?category=1
/api/v1/requests/?assigned_to=4
/api/v1/requests/?unassigned=true
```

Filters operate only inside the caller's already role-scoped queryset.

They cannot widen a user's access.

### Search

Searches request title and description:

```text
/api/v1/requests/?search=streetlight
```

### Ordering

Supported ordering fields:

```text
created_at
updated_at
priority
```

Examples:

```text
/api/v1/requests/?ordering=created_at
/api/v1/requests/?ordering=-created_at
/api/v1/requests/?ordering=priority
/api/v1/requests/?ordering=-priority
```

Priority uses business ordering rather than alphabetical ordering:

```text
LOW → MEDIUM → HIGH → URGENT
```

Descending order reverses that sequence.

### Pagination

The request list uses page-number pagination.

Default page size:

```text
20
```

Custom page size:

```text
?page_size=<number>
```

Maximum page size:

```text
100
```

Paginated response shape:

```json
{
  "count": 42,
  "next": "http://127.0.0.1:8000/api/v1/requests/?page=2",
  "previous": null,
  "results": []
}
```

Categories and request comments remain unpaginated.

---

## File Attachments

### Accepted Files

Allowed extensions:

```text
pdf
jpg
jpeg
png
```

Maximum file size:

```text
5 MB
```

The validator accepts a file exactly 5 MB in size and rejects anything larger.

### Upload

Attachments can be submitted with multipart form data when creating a request.

Example:

```bash
curl -i \
  -X POST http://127.0.0.1:8000/api/v1/requests/ \
  -H "Authorization: Bearer <access-token>" \
  -F "category=1" \
  -F "title=Road damage near school" \
  -F "description=Large pothole requires repair" \
  -F "priority=HIGH" \
  -F "attachment=@/path/to/sample.pdf"
```

Do not commit or publish reusable JWT values.

### Download

Authorized download endpoint:

```http
GET /api/v1/requests/{id}/attachment/
```

The API:

- checks access through the role-scoped request queryset,
- streams the file,
- returns it as an attachment,
- does not expose a public `/media/` route,
- does not return the storage path in normal API responses.

Normal request responses expose:

```json
{
  "has_attachment": true
}
```

rather than an attachment URL.

### Attachment Storage

Uploaded files use UUID-based filenames:

```text
service_requests/<uuid>.<extension>
```

The original client filename is not used as the stored filename.

---

## Admin Statistics

Admin-only endpoint:

```http
GET /api/v1/statistics/
```

Response includes:

```json
{
  "total_requests": 0,
  "by_status": {
    "open": 0,
    "in_progress": 0,
    "resolved": 0,
    "closed": 0
  },
  "by_priority": {
    "low": 0,
    "medium": 0,
    "high": 0,
    "urgent": 0
  },
  "unassigned": 0,
  "by_category": []
}
```

`by_category` also includes categories with zero requests, including inactive categories, because the endpoint is intended for administrators.

---

## Swagger and OpenAPI

The project uses `drf-spectacular`.

Swagger UI:

```text
http://127.0.0.1:8000/api/docs/
```

OpenAPI schema:

```text
http://127.0.0.1:8000/api/schema/
```

### Using JWT in Swagger

1. Register or log in through the authentication endpoint.
2. Copy the returned access token value.
3. Open Swagger UI.
4. Click **Authorize**.
5. Paste the access token only.

Do **not** add:

```text
Bearer
```

manually.

Swagger adds the authentication scheme automatically.

Do not include quotes around the token.

---

## Environment Variables

The application is configured through environment variables.

Create your local environment file from the provided example:

```bash
cp .env.example .env
```

Then replace all placeholder values before starting the application.

The configuration uses variables for values such as:

```text
SECRET_KEY
DEBUG
DB_NAME
DB_USER
DB_PASSWORD
DB_HOST
DB_PORT
```

Do not commit the real `.env`.

### Important Docker Note

Inside Docker Compose, PostgreSQL is reached through the Compose service name:

```text
DB_HOST=db
```

The PostgreSQL service is intentionally not published to the host.

Only the Django web service publishes a host port.

---

## Docker Quick Start

### Prerequisites

Install:

- Git
- Docker Desktop
- Docker Compose

Docker Desktop should be running before starting the project.

### 1. Clone the repository

```bash
git clone https://github.com/hjoy13/government-service-request-api.git
cd government-service-request-api
```

### 2. Create the environment file

```bash
cp .env.example .env
```

Open `.env` and replace the placeholder values.

Do not commit this file.

### 3. Validate the Compose configuration

Use:

```bash
docker compose config --quiet
```

Using `--quiet` is recommended because plain `docker compose config` expands environment variables and may display secret values.

### 4. Build and start the containers

```bash
docker compose up -d --build
```

### 5. Verify service status

```bash
docker compose ps
```

Expected:

- `web` is running.
- `db` is running and healthy.

### 6. Run migrations

```bash
docker compose exec web python manage.py migrate
```

### 7. Run Django system checks

```bash
docker compose exec web python manage.py check --database default
```

### 8. Run the test suite

```bash
docker compose exec -T web python manage.py test --noinput
```

### 9. Open the API documentation

Swagger:

```text
http://127.0.0.1:8000/api/docs/
```

OpenAPI schema:

```text
http://127.0.0.1:8000/api/schema/
```

### 10. Stop the containers

```bash
docker compose down
```

The PostgreSQL named volume remains available, so database data survives normal container shutdown and restart.

To intentionally delete the Docker database volume as well:

```bash
docker compose down -v
```

Use `down -v` only when you intentionally want a fresh Docker database.

---

## Local Development Setup

The normal local development environment used for this project is:

```text
Windows
VS Code
Git Bash
Python virtual environment: .venv
PostgreSQL running locally
```

### 1. Clone

```bash
git clone https://github.com/hjoy13/government-service-request-api.git
cd government-service-request-api
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create `.env`

```bash
cp .env.example .env
```

For native development, configure the environment to point to the PostgreSQL instance running on the host.

The verified native development setup uses:

```text
DB_HOST=localhost
DB_PORT=5432
```

Use your own database name, username, password, and Django secret key.

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Run system checks

```bash
python manage.py check --database default
```

### 7. Run tests

```bash
python manage.py test
```

### 8. Start the development server

```bash
python manage.py runserver
```

Application:

```text
http://127.0.0.1:8000/
```

Swagger:

```text
http://127.0.0.1:8000/api/docs/
```

### Native and Docker Servers

Both native Django development and the Docker web container use host port `8000`.

Do not run both at the same time.

Stop one before starting the other.

---

## Database Migrations

### Native

```bash
python manage.py migrate
```

Check migration state:

```bash
python manage.py showmigrations
```

Preview pending migrations:

```bash
python manage.py migrate --plan
```

### Docker

```bash
docker compose exec web python manage.py migrate
```

Preview pending migrations:

```bash
docker compose exec web python manage.py migrate --plan
```

Migrations are intentionally run manually rather than automatically during container startup.

---

## Running Tests

### Native

Run the full suite:

```bash
python manage.py test
```

### Docker

Run the full suite inside the application container:

```bash
docker compose exec -T web python manage.py test --noinput
```

The current verified suite contains:

```text
137 passing tests
```

Coverage includes:

- authentication
- citizen registration
- role escalation prevention
- permission classes
- category management
- case-insensitive category uniqueness
- category deletion protection
- service request creation
- request visibility
- citizen update restrictions
- officer update restrictions
- admin update behavior
- officer assignment
- nested comments
- attachment validation
- attachment download authorization
- admin statistics
- filtering
- search
- priority ordering
- pagination
- Swagger/OpenAPI schema behavior

---

## Repository Structure

```text
government-service-request-api/
│
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── manage.py
├── requirements.txt
├── README.md
│
├── config/
│   ├── __init__.py
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   ├── __init__.py
│   │
│   ├── accounts/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── permissions.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   ├── views.py
│   │   └── migrations/
│   │
│   ├── categories/
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── urls.py
│   │   ├── views.py
│   │   └── migrations/
│   │
│   └── service_requests/
│       ├── admin.py
│       ├── apps.py
│       ├── filters.py
│       ├── models.py
│       ├── pagination.py
│       ├── permissions.py
│       ├── serializers.py
│       ├── urls.py
│       ├── validators.py
│       ├── views.py
│       └── migrations/
│
└── tests/
    ├── __init__.py
    ├── test_api_docs.py
    ├── test_attachments.py
    ├── test_auth.py
    ├── test_categories.py
    ├── test_list_queries.py
    ├── test_pagination.py
    ├── test_permissions.py
    ├── test_service_requests.py
    └── test_statistics.py
```

---

## Design Decisions

### Custom User Model

The project uses a custom user model from the start.

Application authorization uses:

```text
role
```

Django administration privileges continue to use:

```text
is_staff
is_superuser
```

These concepts are intentionally kept separate.

### Deny-by-Default API

The global REST framework configuration requires:

- JWT authentication
- authenticated access

Public endpoints explicitly opt out where needed.

### Queryset-Level Security

Request visibility is implemented through role-scoped querysets.

This prevents users from discovering resources outside their authorized scope.

### Dedicated Assignment Action

Officer assignment is implemented as a dedicated business operation instead of making `assigned_to` writable through ordinary request updates.

### Server-Controlled Fields

Fields such as:

```text
created_by
assigned_to
status during creation
comment author
comment parent request
```

are controlled by the server rather than trusted from client input.

### No Request Deletion

Service requests represent government-service history, so the API does not provide request deletion.

### No Full PUT Replacement

The API uses `PATCH` for supported updates and disables `PUT`.

### Time Zone

The application uses:

```text
Asia/Dhaka
```

with Django time-zone support enabled.

### Priority Ordering

Priority ordering follows business meaning instead of alphabetical text ordering:

```text
LOW < MEDIUM < HIGH < URGENT
```

### Pagination Scope

Only the service-request list is paginated.

Comments and categories intentionally remain normal lists.

---

## Known Limitations

### Development Server

The Docker image currently runs:

```text
python manage.py runserver 0.0.0.0:8000
```

This is appropriate for development and assessment use, but it is not a production WSGI/ASGI deployment.

A production deployment should use an appropriate production server and additional hardening.

### Container User

The current Docker image does not add a dedicated non-root application user.

### Migrations

Migrations are run manually after container startup.

They are not automatically executed by an entrypoint.

### File Validation

Attachment validation checks:

- file extension
- file size

The current implementation does not inspect file contents or perform MIME/content sniffing.

### Attachment Replacement

Replacing an attachment does not automatically delete the previously stored file.

### Attachment Clearing

The current API supports attachment creation and replacement but does not expose a dedicated operation to clear an existing attachment.

### Media Storage

The development Docker Compose configuration bind-mounts the project directory into `/app`.

Uploaded media therefore persists on the host during this development setup.

There is no separate named Docker volume specifically for media files.

### Swagger PATCH Schema

The generated generic PATCH schema may display fields that are valid only for particular roles.

Runtime authorization and serializer validation still enforce the actual role-specific rules.

### Swagger File Extension Schema

The generated OpenAPI extension pattern may appear stricter than the server behavior for uppercase file extensions.

Server-side validation remains authoritative.

### Status Workflow

The project validates status values but intentionally does not implement a strict state-transition machine such as:

```text
OPEN → IN_PROGRESS → RESOLVED → CLOSED
```

Assigned officers and admins may move a request to any valid status.

---

## Verification Status

The required implementation has been verified through both native development and Docker.

Verified items include:

- Django system checks.
- PostgreSQL connectivity.
- JWT authentication.
- Citizen registration.
- Role escalation prevention.
- Category management and permissions.
- Service request creation.
- Role-scoped request visibility.
- Citizen request-editing rules.
- Officer request-processing rules.
- Admin assignment.
- Comments.
- File upload validation.
- Secure attachment download.
- Filtering.
- Search.
- Business-priority ordering.
- Pagination.
- Admin statistics.
- Swagger/OpenAPI.
- Docker image build.
- Docker Compose startup.
- PostgreSQL healthcheck.
- PostgreSQL named-volume persistence.
- Fresh GitHub clone startup.
- Full automated test suite inside Docker.
- End-to-end role workflow through the containerized API.

Latest verified automated test result:

```text
Ran 137 tests
OK
```

The Docker setup has also been tested from a fresh GitHub clone using:

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose exec web python manage.py migrate
```

with PostgreSQL becoming healthy and the Django application starting successfully.

---

## Repository

Public repository:

```text
https://github.com/hjoy13/government-service-request-api
```

---

## Final Notes

This project prioritizes:

- correctness
- role-based authorization
- predictable API behavior
- server-controlled security-sensitive fields
- automated verification
- Docker reproducibility
- clear documentation
- maintainable Django/DRF structure

The system is intentionally implemented as a modular monolith without unnecessary architectural layers or microservices.
