# CareBridge – Backend (Django REST API)
Sirf API hai (JSON). Koi HTML template nahi. Frontend alag folder `CareBridge_Frontend` me hai.
Stack: Django + Django REST Framework (Token auth) + SQL Server (mssql-django) + django-cors-headers.

## Setup (Windows, VS Code)
1. Python 3.11+, **ODBC Driver 17 for SQL Server**, SQL Server + SSMS install karo.
2. SSMS me khali database `CareBridge` banao.
3. `python -m venv venv` → `venv\Scripts\activate` → `pip install -r requirements.txt`
4. Environment variables (PowerShell example, `.env.example` dekho):
   `$env:DB_ENGINE="mssql"; $env:DB_NAME="CareBridge"; $env:DB_HOST="localhost\SQLEXPRESS"; $env:DB_USER="sa"; $env:DB_PASSWORD="..."`
   (Windows auth: DB_USER/DB_PASSWORD khali rakho aur `$env:DB_EXTRA="Trusted_Connection=yes;TrustServerCertificate=yes"`.)
   DB_ENGINE na do to SQLite use hoga (sirf quick test ke liye).
5. `python manage.py migrate` → `python manage.py seed` → `python manage.py runserver`
6. API: http://127.0.0.1:8000/api/  |  Django admin: http://127.0.0.1:8000/django-admin/

**Update karte waqt `python manage.py migrate` zaroor chalao** (naya `authtoken_token` table banega).

## Demo logins (fake data)
admin / Admin@12345 · senior_demo / Demo@12345 · volunteer_demo / Demo@12345

## Authentication
Login/Register par `token` milta hai. Baaki har request me header bhejo: `Authorization: Token <token>`.
Frontend ka URL CORS me allow hona chahiye (DEBUG=1 me sab allowed; production me `CORS_ALLOWED_ORIGINS` set karo).

## API endpoints (prefix `/api/`)
| Method | URL | Kaun | Kaam |
|---|---|---|---|
| POST | auth/register/<senior\|volunteer>/ | public | Register (multipart, `document` file) → token |
| POST | auth/login/ | public | `{username,password}` → token + user |
| POST | auth/logout/ | login | Token delete |
| GET | auth/me/ | login | Current user + rejection_reason |
| POST | auth/resubmit/ | rejected user | Document dobara (multipart) |
| GET/PUT | profile/ | login | Profile dekho / badlo |
| GET | categories/ | login | Active categories |
| GET | dashboard/ | senior/volunteer | Dashboard data |
| GET/POST | requests/ | senior | Meri requests / nayi request |
| POST | requests/<id>/cancel/ | senior | Cancel |
| GET | requests/available/ | volunteer | Pending requests |
| GET | assignments/ | volunteer | Meri assignments |
| GET | requests/<id>/ | owner / assigned volunteer / admin | Detail (+ contact sirf owner & assigned volunteer ko) |
| POST | requests/<id>/accept/ | volunteer | Accept |
| POST | requests/<id>/progress/<start\|complete\|withdraw>/ | volunteer | Status |
| GET/POST | report/ | senior/volunteer | Complaint options / complaint bhejo |
| GET | manage/dashboard/ | admin | Counts |
| GET | manage/verifications/?s=pending\|approved\|rejected | admin | Users list |
| POST | manage/verify/<user_id>/<approve\|reject>/ | admin | `{reason}` |
| GET | manage/doc/<record_id>/ | admin | Verification document file |
| GET | manage/requests/?s=status | admin | Sab requests |
| GET/POST | manage/categories/ | admin | List / add |
| PUT/DELETE | manage/categories/<id>/ | admin | Edit / delete |
| POST | manage/categories/<id>/toggle/ | admin | Active on/off |
| GET | manage/users/ , POST manage/users/<id>/toggle/ | admin | Users, suspend/activate |
| GET/POST | manage/complaints/ | admin | List / resolve `{id,action}` |
| GET | manage/activity/ | admin | Activity log |

Errors: `{"detail": "...", "code": "..."}`; form errors: `{"detail": "...", "errors": {"field": ["msg"]}}`.
`code: "not_approved"` = user verified nahi hai (frontend status page par bhejta hai).

## Tests
`python manage.py test core` – 14 tests (full workflow, role checks, double-accept, contact privacy, admin actions, etc.)

## Security notes
Django password hashing, backend role checks, contact info sirf owner senior + assigned volunteer ko,
verification documents sirf admin endpoint se, DB unique filtered index = ek request par ek hi active assignment.
Production me DEBUG=0 + HTTPS.
