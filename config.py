"""Configuracion centralizada del pipeline, cargada desde variables de entorno (.env)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


@dataclass
class Settings:
    # --- Proveedor de LLM: "gemini" (por defecto) o "groq". Ambos tienen tier gratuito y no
    # requieren tarjeta de credito ni pasarela de pago. ---
    llm_provider: str = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    # Google Gemini (Google AI Studio) - clave gratuita en https://aistudio.google.com/apikey
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    # Groq - clave gratuita en https://console.groq.com/keys
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    # --- Persistencia (Track Record Engine) ---
    database_url: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'data' / 'macro_intel.db').as_posix()}"
    )

    # --- Ingesta / Raw Data Lake ---
    data_lake_dir: Path = Path(os.getenv("DATA_LAKE_DIR", str(BASE_DIR / "data" / "raw_lake")))
    fetch_timeout: int = int(os.getenv("FETCH_TIMEOUT", "15"))
    # Email de contacto opcional para el User-Agent HTTP (buena practica con feeds RSS).
    # No se usa ningun dato personal salvo que el usuario lo configure explicitamente.
    contact_email: str = os.getenv("CONTACT_EMAIL", "no-reply@example.com")

    # --- Motor de consenso / cross-check ---
    min_institutional_diversity: int = int(os.getenv("MIN_INSTITUTIONAL_DIVERSITY", "2"))
    cluster_time_window_hours: int = int(os.getenv("CLUSTER_TIME_WINDOW_HOURS", "48"))
    # Similitud SEMANTICA (embeddings, coseno 0-1), no de texto literal -- reemplaza al
    # antiguo CLUSTER_TITLE_SIMILARITY (rapidfuzz sobre texto), que en la practica casi nunca
    # agrupaba coberturas reales del mismo evento porque cada medio redacta su titular distinto
    # (ver crosscheck/clustering.py). 0.60 elegido empiricamente contra articulos reales de este
    # pipeline: separa bien duplicados tematicos genuinos de temas meramente relacionados.
    cluster_semantic_similarity_threshold: float = float(os.getenv("CLUSTER_SEMANTIC_SIMILARITY", "0.60"))

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # "development" (por defecto) o "production" -- controla si un secreto JWT auto-generado
    # es tolerable (desarrollo) o un error fatal que impide arrancar (produccion). Ver
    # api/server.py:lifespan, donde se aplica de verdad.
    environment: str = os.getenv("ENVIRONMENT", "development").strip().lower()

    # --- Identidad y control de acceso (Institutional Prompt, seccion 6) ---
    # Sin JWT_SECRET_KEY en .env, se genera uno aleatorio al arrancar: valido para desarrollo
    # local (los tokens siguen siendo validos mientras el proceso vive), pero en produccion
    # DEBE fijarse explicitamente -- si no, cada reinicio del servidor invalida todas las
    # sesiones activas, y un despliegue con varias replicas tendria un secreto distinto por
    # instancia (los tokens de una no servirian en otra).
    jwt_secret: str = field(default_factory=lambda: os.getenv("JWT_SECRET_KEY") or secrets.token_hex(32))
    jwt_expiry_hours: int = int(os.getenv("JWT_EXPIRY_HOURS", "8"))
    jwt_secret_was_generated: bool = field(default=False)

    @property
    def user_agent(self) -> str:
        return f"MacroIntelPipeline/1.0 (+research; contact: {self.contact_email})"

    def require_api_key(self) -> None:
        if self.llm_provider not in ("gemini", "groq"):
            raise SystemExit(
                f"LLM_PROVIDER='{self.llm_provider}' no reconocido. Usa 'gemini' o 'groq' en .env."
            )
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise SystemExit(
                "Falta GEMINI_API_KEY. Consigue una clave GRATUITA (sin tarjeta) en "
                "https://aistudio.google.com/apikey y configurala en el archivo .env "
                "(ver .env.example)."
            )
        if self.llm_provider == "groq" and not self.groq_api_key:
            raise SystemExit(
                "Falta GROQ_API_KEY. Consigue una clave GRATUITA (sin tarjeta) en "
                "https://console.groq.com/keys y configurala en el archivo .env "
                "(ver .env.example)."
            )


settings = Settings()
settings.jwt_secret_was_generated = "JWT_SECRET_KEY" not in os.environ
settings.data_lake_dir.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)
