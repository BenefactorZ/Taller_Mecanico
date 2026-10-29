"""Registro público de cuentas: creación de cuenta → registro → rol INVITADO."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .models import Role, User
from .schemas import RegisterRequest, UserResponse
from .security import hash_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def registrar_cuenta(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Cualquier persona puede registrarse, pero siempre como INVITADO. Los roles los asigna un administrador."""
    correo = payload.email.lower()
    if db.scalar(select(User.id).where(User.email == correo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")
    cuenta = User(full_name=payload.full_name.strip(), email=correo, password_hash=hash_password(payload.password), role=Role.INVITADO, branch=None)
    db.add(cuenta)
    try:
        db.commit()
    except IntegrityError:  # dos registros simultáneos con el mismo correo
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")
    db.refresh(cuenta)
    return cuenta
