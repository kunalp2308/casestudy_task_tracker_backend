import os
from pathlib import Path

from dotenv import load_dotenv


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(ENV_FILE)

DEFAULT_DATABASE_URL = "mysql+pymysql://root:Root%40123@localhost:3306/task_tracker"


class Settings:
    database_url: str = os.getenv("MY_SQL_DATABASE_URL", DEFAULT_DATABASE_URL)
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv(
        "GOOGLE_REDIRECT_URI",
        "http://localhost:8000/api/auth/google/callback",
    )
    google_authorization_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"
    google_userinfo_url: str = "https://openidconnect.googleapis.com/v1/userinfo"
    google_admin_emails: str = os.getenv("GOOGLE_ADMIN_EMAILS", "")
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "480"))
    oauth_state_expire_minutes: int = int(os.getenv("OAUTH_STATE_EXPIRE_MINUTES", "10"))

    @property
    def google_admin_email_set(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.google_admin_emails.split(",")
            if email.strip()
        }


settings = Settings()
