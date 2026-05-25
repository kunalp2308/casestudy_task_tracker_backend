from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import can_manage_work, get_current_user, require_any_role
from ..database import get_db
from ..services import commit_or_409, ensure_project_exists, ensure_user_exists, get_or_404


router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/statuses", response_model=list[str])
def list_statuses(current_user: models.User = Depends(get_current_user)):
    return list(models.TASK_STATUSES)


@router.get("", response_model=list[schemas.TaskRead])
def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    project_id: int | None = None,
    owner_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Task).options(
        joinedload(models.Task.owner).joinedload(models.User.roles),
        joinedload(models.Task.project).joinedload(models.Project.owner).joinedload(models.User.roles),
    )
    
    if status_filter:
        query = query.filter(models.Task.status == status_filter)
    if project_id:
        query = query.filter(models.Task.project_id == project_id)
    if owner_id:
        query = query.filter(models.Task.owner_id == owner_id)
    
    tasks = query.order_by(models.Task.due_date.is_(None), models.Task.due_date).all()
    return tasks


@router.post("", response_model=schemas.TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin", "task creator")),
):
    ensure_project_exists(db, payload.project_id)
    ensure_user_exists(db, payload.owner_id)
    task = models.Task(**payload.model_dump())
    db.add(task)
    commit_or_409(db, "Unable to create task")
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=schemas.TaskRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = db.query(models.Task).options(
        joinedload(models.Task.owner).joinedload(models.User.roles),
        joinedload(models.Task.project).joinedload(models.Project.owner).joinedload(models.User.roles),
    ).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.put("/{task_id}", response_model=schemas.TaskRead)
def update_task(
    task_id: int,
    payload: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin", "task creator")),
):
    task = get_or_404(db, models.Task, task_id, "Task")
    updates = payload.model_dump(exclude_unset=True)
    if "project_id" in updates and updates["project_id"] is not None:
        ensure_project_exists(db, updates["project_id"])
    if "owner_id" in updates:
        ensure_user_exists(db, updates["owner_id"])
    for field, value in updates.items():
        setattr(task, field, value)
    commit_or_409(db, "Unable to update task")
    db.refresh(task)
    return task


@router.patch("/{task_id}/assign", response_model=schemas.TaskRead)
def assign_task(
    task_id: int,
    payload: schemas.TaskAssign,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin", "task creator")),
):
    task = get_or_404(db, models.Task, task_id, "Task")
    ensure_user_exists(db, payload.owner_id)
    task.owner_id = payload.owner_id
    commit_or_409(db, "Unable to assign task")
    db.refresh(task)
    return task


@router.patch("/{task_id}/complete", response_model=schemas.TaskRead)
def mark_task_complete(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_or_404(db, models.Task, task_id, "Task")
    if not can_manage_work(current_user) and task.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the assigned user can complete this task",
        )
    task.status = "completed"
    commit_or_409(db, "Unable to mark task complete")
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_any_role("admin", "task creator")),
):
    task = get_or_404(db, models.Task, task_id, "Task")
    db.delete(task)
    commit_or_409(db, "Unable to delete task")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
