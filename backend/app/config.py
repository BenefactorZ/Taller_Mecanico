from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str
    access_token_minutes: int = 60
    reset_code_minutes: int = 15
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "no-reply@taller.local"
    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    # Carpeta de archivos subidos (fotos de talleres). Por defecto backend/uploads, fuera del control de versiones.
    uploads_dir: str | None = None


settings = Settings()
