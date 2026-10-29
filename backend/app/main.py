import secrets
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .config import settings
from .customers.administracion import router as clientes_admin_router
from .customers.api import regla_incumplida_handler, router as customers_router
from .customers.dominio import ReglaIncumplida
from .database import Base, engine, get_db
from .email_service import send_reset_code
from .catalogos import sembrar_status
from .cuentas_api import router as cuentas_router
from .migraciones import migrar
from .models import PasswordResetCode, Role, User
from .empleados_api import router as empleados_router
from .permisos import requiere, router as permisos_router, sembrar_permisos, usuario_con_permisos
from .roles_api import resolver_rol_empleado, router as roles_router, sembrar_roles_sistema
from .talleres.administracion import router as talleres_admin_router
from .talleres.api import catalogo as catalogo_router, router as talleres_router
from .vehiculos.api import router as vehiculos_router
from .schemas import LoginRequest, RecoveryRequest, ResetPasswordRequest, TokenResponse, UserCreate, UserResponse, VerifyCodeRequest
from .security import create_access_token, current_user, hash_password, verify_password


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


app.include_router(clientes_admin_router)
app.include_router(customers_router)
app.include_router(vehiculos_router)
app.include_router(cuentas_router)
app.include_router(roles_router)
app.include_router(empleados_router)
app.include_router(permisos_router)
app.include_router(talleres_router)
app.include_router(talleres_admin_router)
app.include_router(catalogo_router)
app.add_exception_handler(ReglaIncumplida, regla_incumplida_handler)


@app.on_event("startup")
def startup() -> None:
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        sembrar_status(db)  # los estatus deben existir antes de agregar las claves foráneas de bin_status
    migrar(engine)
    with Session(engine) as db:
        sembrar_roles_sistema(db)  # requiere las columnas que agrega la migración
        sembrar_permisos(db)
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
    return TokenResponse(access_token=create_access_token(user), user=usuario_con_permisos(user, db))


@app.get("/api/auth/me", response_model=UserResponse)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return usuario_con_permisos(user, db)


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
def create_employee(payload: UserCreate, db: Session = Depends(get_db), _: User = Depends(requiere("empleados.alta"))):
    # El rol sale de la tabla de roles: uno de empleado de fábrica o uno personalizado activo (role = PERSONALIZADO + role_definition_id)
    rol, rol_id = resolver_rol_empleado(db, payload.role)
    employee = User(full_name=payload.full_name.strip(), email=payload.email.lower(), password_hash=hash_password(payload.password), role=rol, role_definition_id=rol_id, branch=payload.branch.strip() if payload.branch else None)
    db.add(employee)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ya existe un usuario con ese correo")
    db.refresh(employee)
    return employee


@app.get("/api/work-orders", dependencies=[Depends(requiere("ordenes.consultar"))])
def list_work_orders():
    return {"message": "Acceso autorizado a órdenes de trabajo"}


@app.post("/api/receptions", dependencies=[Depends(requiere("recepciones.registrar"))])
def register_reception():
    return {"message": "Recepción registrada"}


@app.patch("/api/work-orders/{order_id}/corrections", dependencies=[Depends(requiere("ordenes.corregir"))])
def correct_work_order(order_id: int):
    return {"message": f"Orden {order_id} corregida"}


@app.post("/api/work-orders/{order_id}/diagnostics", dependencies=[Depends(requiere("diagnosticos.registrar"))])
def register_diagnostic(order_id: int):
    return {"message": f"Diagnóstico de la orden {order_id} registrado"}


@app.get("/api/notifications", dependencies=[Depends(requiere("notificaciones.consultar"))])
def client_notifications():
    return {"message": "Notificaciones disponibles"}
