from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_any_role
from ..database import get_db
from ..services import commit_or_409, get_or_404


router = APIRouter(prefix="/roles", tags=["roles"])


@router.get("", response_model=list[schemas.RoleRead])
def list_roles(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Role).order_by(models.Role.name).all()


@router.post("", response_model=schemas.RoleRead, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: schemas.RoleCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin")),
):
    role = models.Role(**payload.model_dump())
    db.add(role)
    commit_or_409(db, "Role name already exists")
    db.refresh(role)
    return role


@router.get("/{role_id}", response_model=schemas.RoleRead)
def get_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_or_404(db, models.Role, role_id, "Role")


@router.put("/{role_id}", response_model=schemas.RoleRead)
def update_role(
    role_id: int,
    payload: schemas.RoleUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin")),
):
    role = get_or_404(db, models.Role, role_id, "Role")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(role, field, value)
    commit_or_409(db, "Role name already exists")
    db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin")),
):
    role = get_or_404(db, models.Role, role_id, "Role")
    db.delete(role)
    commit_or_409(db, "Unable to delete role")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
