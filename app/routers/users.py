from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session, selectinload

from .. import models, schemas
from ..auth import get_current_user, require_any_role
from ..database import get_db
from ..services import commit_or_409, ensure_role_ids_exist, get_or_404


router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[schemas.UserRead])
def list_users(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.User)
        .options(selectinload(models.User.roles))
        .order_by(models.User.full_name)
        .all()
    )


@router.post("", response_model=schemas.UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: schemas.UserCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin")),
):
    data = payload.model_dump(exclude={"role_ids"})
    user = models.User(**data)
    user.roles = ensure_role_ids_exist(db, payload.role_ids)
    db.add(user)
    commit_or_409(db, "User email already exists")
    db.refresh(user)
    return user


@router.get("/{user_id}", response_model=schemas.UserRead)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return get_or_404(db, models.User, user_id, "User")


@router.put("/{user_id}", response_model=schemas.UserRead)
def update_user(
    user_id: int,
    payload: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin")),
):
    user = get_or_404(db, models.User, user_id, "User")
    updates = payload.model_dump(exclude_unset=True, exclude={"role_ids"})
    for field, value in updates.items():
        setattr(user, field, value)
    if payload.role_ids is not None:
        user.roles = ensure_role_ids_exist(db, payload.role_ids)
    commit_or_409(db, "User email already exists")
    db.refresh(user)
    return user


@router.put("/{user_id}/roles", response_model=schemas.UserRead)
def assign_roles(
    user_id: int,
    payload: schemas.UserRoleAssignment,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin")),
):
    user = get_or_404(db, models.User, user_id, "User")
    user.roles = ensure_role_ids_exist(db, payload.role_ids)
    commit_or_409(db, "Unable to assign roles")
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin")),
):
    user = get_or_404(db, models.User, user_id, "User")
    db.delete(user)
    commit_or_409(db, "Unable to delete user")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
