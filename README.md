# Backend

FastAPI API for the Task Tracker application.

## Capabilities

- CRUD projects
- CRUD tasks
- Assign tasks to users
- Mark tasks complete
- CRUD users
- CRUD roles
- Assign roles to users
- Google SSO authentication
- Role-based API access for admin, task creator, and individual read only users

## Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Copy `.env.example` to `.env` and set your Google OAuth client ID before running.

For the React Google login button, Google Cloud Console needs this authorized JavaScript origin:

```text
http://localhost:5173
```

Set `GOOGLE_ADMIN_EMAILS` for known admins. The first Google user is also promoted when `BOOTSTRAP_FIRST_GOOGLE_USER_AS_ADMIN=true`.

## API Docs

Open `http://localhost:8000/docs`.
