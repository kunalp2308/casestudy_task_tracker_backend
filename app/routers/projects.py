from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user, require_any_role
from ..database import get_db
from ..services import commit_or_409, ensure_user_exists, get_or_404


router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[schemas.ProjectRead])
def list_projects(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Project)
        .options(joinedload(models.Project.owner))
        .order_by(models.Project.name)
        .all()
    )


@router.post("", response_model=schemas.ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: schemas.ProjectCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin", "task creator")),
):
    ensure_user_exists(db, payload.owner_id)
    project = models.Project(**payload.model_dump())
    db.add(project)
    commit_or_409(db, "Project name already exists")
    db.refresh(project)
    return project


@router.get("/{project_id}", response_model=schemas.ProjectRead)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_or_404(db, models.Project, project_id, "Project")


@router.put("/{project_id}", response_model=schemas.ProjectRead)
def update_project(
    project_id: int,
    payload: schemas.ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin", "task creator")),
):
    project = get_or_404(db, models.Project, project_id, "Project")
    updates = payload.model_dump(exclude_unset=True)
    if "owner_id" in updates:
        ensure_user_exists(db, updates["owner_id"])
    for field, value in updates.items():
        setattr(project, field, value)
    commit_or_409(db, "Project name already exists")
    db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin", "task creator")),
):
    project = get_or_404(db, models.Project, project_id, "Project")
    db.delete(project)
    commit_or_409(db, "Unable to delete project")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
