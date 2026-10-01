import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .database import Base, engine, get_db
from .email_service import send_reset_code
from .models import PasswordResetCode, Role, User
from .schemas import LoginRequest, RecoveryRequest, ResetPasswordRequest, TokenResponse, UserCreate, UserResponse, VerifyCodeRequest
from .security import allow_roles, create_access_token, current_user, hash_password, verify_password


app = FastAPI(title="Taller Mecánico - Seguridad")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    if settings.bootstrap_admin_email and settings.bootstrap_admin_password:
        with Session(engine) as db:
            if not db.scalar(select(User).where(User.email == settings.bootstrap_admin_email.lower())):
                db.add(User(full_name="Administrador inicial", email=settings.bootstrap_admin_email.lower(), password_hash=hash_password(settings.bootstrap_admin_password), role=Role.ADMINISTRADOR, branch=None))
                db.commit()


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    return TokenResponse(access_token=create_access_token(user), user=user)


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user


@app.post("/api/auth/recovery", status_code=status.HTTP_202_ACCEPTED)
def request_recovery(payload: RecoveryRequest, db: Session = Depends(get_db)):
    # SQL Server no soporta "IS 1": se usa "== True" para que genere "= 1"
    user = db.scalar(select(User).where(User.email == payload.email.lower(), User.is_active == True))  # noqa: E712
    if user:
        code = f"{secrets.randbelow(1_000_000):06d}"
        db.add(PasswordResetCode(user_id=user.id, code_hash=hash_password(code), expires_at=datetime.utcnow() + timedelta(minutes=settings.reset_code_minutes)))
        db.commit()
        send_reset_code(user.email, code)
    return {"message": "Si el correo está registrado, enviamos un código de recuperación."}


def valid_reset(payload: VerifyCodeRequest, db: Session) -> tuple[User, PasswordResetCode]:
    user = db.scalar(select(User).where(User.email == payload.email.lower(), User.is_active == True))  # noqa: E712
    if not user:
        raise HTTPException(status_code=400, detail="Código inválido o vencido")
    reset = db.scalar(select(PasswordResetCode).where(PasswordResetCode.user_id == user.id, PasswordResetCode.used_at.is_(None)).order_by(PasswordResetCode.id.desc()))
    if not reset or reset.expires_at < datetime.utcnow() or not verify_password(payload.code, reset.code_hash):
        raise HTTPException(status_code=400, detail="Código inválido o vencido")
    return user, reset


@app.post("/api/auth/recovery/verify")
def verify_recovery_code(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    valid_reset(payload, db)
    return {"message": "Código verificado"}


@app.post("/api/auth/recovery/reset")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user, reset = valid_reset(payload, db)
    user.password_hash = hash_password(payload.new_password)
    reset.used_at = datetime.utcnow()
    db.commit()
    return {"message": "Contraseña actualizada"}


@app.post("/api/users/employees", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_employee(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(allow_roles(Role.ADMINISTRADOR))):
    employee = User(full_name=payload.full_name.strip(), email=payload.email.lower(), password_hash=hash_password(payload.password), role=payload.role, branch=payload.branch.strip() if payload.branch else None)
    db.add(employee)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo")
    db.refresh(employee)
    return employee


@app.get("/api/work-orders", dependencies=[Depends(allow_roles(Role.ADMINISTRADOR, Role.RECEPCIONISTA, Role.ASESOR_SERVICIO, Role.TECNICO))])
def list_work_orders():
    return {"message": "Acceso autorizado a órdenes de trabajo"}


@app.post("/api/receptions", dependencies=[Depends(allow_roles(Role.ADMINISTRADOR, Role.RECEPCIONISTA))])
def register_reception():
    return {"message": "Recepción registrada"}


@app.patch("/api/work-orders/{order_id}/corrections", dependencies=[Depends(allow_roles(Role.ADMINISTRADOR, Role.ASESOR_SERVICIO))])
def correct_work_order(order_id: int):
    return {"message": f"Orden {order_id} corregida"}


@app.post("/api/work-orders/{order_id}/diagnostics", dependencies=[Depends(allow_roles(Role.ADMINISTRADOR, Role.TECNICO))])
def register_diagnostic(order_id: int):
    return {"message": f"Diagnóstico de la orden {order_id} registrado"}


@app.get("/api/notifications", dependencies=[Depends(allow_roles(Role.ADMINISTRADOR, Role.CLIENTE))])
def client_notifications():
    return {"message": "Notificaciones disponibles"}