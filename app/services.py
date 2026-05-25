from fastapi import HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models


DEFAULT_ROLES = (
    ("admin", "Can manage users, roles, projects, and tasks."),
    ("task creator", "Can create and maintain projects and tasks."),
    ("individual read only user", "Can view assigned tasks and mark them complete."),
)


def get_or_404(db: Session, model, entity_id: int, label: str):
    entity = db.get(model, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} not found")
    return entity


def commit_or_409(db: Session, message: str):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=message) from exc


def ensure_user_exists(db: Session, user_id: int | None):
    if user_id is None:
        return None
    return get_or_404(db, models.User, user_id, "User")


def ensure_project_exists(db: Session, project_id: int):
    return get_or_404(db, models.Project, project_id, "Project")


def ensure_role_ids_exist(db: Session, role_ids: list[int]):
    roles = db.query(models.Role).filter(models.Role.id.in_(role_ids)).all() if role_ids else []
    found_ids = {role.id for role in roles}
    missing_ids = sorted(set(role_ids) - found_ids)
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Roles not found: {missing_ids}",
        )
    return roles


def get_role_by_name(db: Session, name: str):
    return db.query(models.Role).filter(models.Role.name == name).first()


def seed_default_roles(db: Session):
    existing_names = {role.name for role in db.query(models.Role).all()}
    for name, description in DEFAULT_ROLES:
        if name not in existing_names:
            db.add(models.Role(name=name, description=description))
    commit_or_409(db, "Unable to seed default roles")


def ensure_user_auth_columns(engine: Engine):
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    indexes = {index["name"] for index in inspector.get_indexes("users")}

    with engine.begin() as connection:
        if "google_sub" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255) NULL"))
            connection.execute(text("CREATE UNIQUE INDEX ix_users_google_sub ON users (google_sub)"))
        elif "ix_users_google_sub" not in indexes:
            connection.execute(text("CREATE UNIQUE INDEX ix_users_google_sub ON users (google_sub)"))

        if "avatar_url" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512) NULL"))
