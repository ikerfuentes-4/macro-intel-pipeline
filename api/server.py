"""Backend del dashboard, con capa de identidad y gobierno (Institutional Prompt, secciones 6,
7 y 8: RBAC obligatorio en todo endpoint, revision humana antes de publicar, kill switch).

Sirve el frontend estatico (frontend/index.html) desde el MISMO origen, para no depender de
configuracion de CORS ni de un segundo servidor -- los datos que ese frontend consume SI estan
protegidos por rol; el shell HTML/JS estatico no (ver README, seccion de limitaciones: gatear
el propio StaticFiles requeriria un proxy de autenticacion que no se ha construido en esta
iteracion -- lo que importa de verdad, los endpoints de datos, si lo esta).

Ejecucion:
    uvicorn api.server:app --reload --port 8000

Luego abre http://localhost:8000 en el navegador, o consume la API desde web/ (Next.js).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

from analysis.product_engine import forecast_product
from analysis.product_report import REPORTS_DIR
from analysis.risk_score import compute_conflict_risk_by_country, compute_energy_risk_by_country
from config import settings
from core.auth import CurrentUser, authenticate_user, create_access_token, require_role
from llm.circuit_breaker import all_breaker_statuses
from persistence.audit import list_audit_log, record_audit_event, verify_audit_chain
from persistence.conflicts import list_active_conflicts
from persistence.db import init_db
from persistence.model_inventory import list_model_inventory, sync_model_inventory, update_model_card_governance
from persistence.product_track_record import product_track_record_summary, save_product_prediction
from persistence.review import list_pending_review, review_prediction
from persistence.system_control import get_kill_switch_status, set_kill_switch
from persistence.system_runs import list_recent_system_runs, track_system_run
from persistence.track_record import list_events_for_dashboard, track_record_summary
from utils.logging_conf import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)  # StaticFiles exige que exista al montar
    sync_model_inventory()
    if settings.jwt_secret_was_generated:
        if settings.environment == "production":
            # En produccion esto no es una advertencia, es un fallo de arranque: un secreto
            # JWT distinto en cada reinicio invalida TODAS las sesiones activas sin aviso, y en
            # un despliegue con varias replicas cada una firmaria con un secreto distinto (un
            # token emitido por una no lo validaria otra). Institutional Prompt, seccion 6.
            raise RuntimeError(
                "ENVIRONMENT=production pero JWT_SECRET_KEY no esta fijado en .env. "
                "Arranque abortado a proposito -- fija un secreto real y fijo antes de "
                "desplegar (ver .env.example). En desarrollo (ENVIRONMENT=development, "
                "por defecto) esto solo genera un aviso, no bloquea el arranque."
            )
        logger.warning(
            "JWT_SECRET_KEY no esta fijado en .env: se genero uno aleatorio para esta "
            "ejecucion. Todas las sesiones se invalidaran al reiniciar el proceso. Fija "
            "JWT_SECRET_KEY y ENVIRONMENT=production antes de desplegar de verdad (ver "
            ".env.example)."
        )
    logger.info("API lista. Sirviendo frontend desde %s", FRONTEND_DIR)
    yield


app = FastAPI(title="Macro Intelligence Engine API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ============================== AUTENTICACION ==============================

class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/auth/login")
@limiter.limit("5/minute")  # objetivo: dificultar fuerza bruta, no imponer friccion normal
def login(request: Request, body: LoginRequest) -> dict:
    user = authenticate_user(body.email, body.password)
    if user is None:
        # Mensaje identico exista o no el usuario -- evita enumeracion de cuentas validas.
        raise HTTPException(status_code=401, detail="Email o contrasena incorrectos.")
    token = create_access_token(user)
    record_audit_event(actor_email=user.email, actor_role=user.role, action="login", entity_type="user", entity_id=str(user.id))
    return {"access_token": token, "token_type": "bearer", "role": user.role, "email": user.email}


@app.get("/api/auth/me")
def get_me(user: CurrentUser = Depends(require_role("viewer"))) -> dict:
    return {"email": user.email, "role": user.role}


# ============================== DATOS (lectura: rol viewer) ==============================

@app.get("/api/events")
def get_events(user: CurrentUser = Depends(require_role("viewer"))) -> list[dict]:
    """Analisis aprobados por un reviewer humano, con su consenso, geolocalizacion y estado de
    prediccion (ver persistence/track_record.py:list_events_for_dashboard). Solo
    `review_status == 'APPROVED'` -- Institutional Prompt, Principio 8."""
    return list_events_for_dashboard()


@app.get("/api/summary")
def get_summary(user: CurrentUser = Depends(require_role("viewer"))) -> dict:
    return track_record_summary()


@app.get("/api/conflicts")
def get_conflicts(user: CurrentUser = Depends(require_role("viewer"))) -> list[dict]:
    """Registro de conflictos armados activos (capa de referencia factual). NO pasa por el
    motor de analisis LLM y no requiere revision humana -- son datos factuales, no analisis."""
    return list_active_conflicts()


@app.get("/api/risk-score")
def get_risk_score(user: CurrentUser = Depends(require_role("viewer"))) -> list[dict]:
    return compute_conflict_risk_by_country()


@app.get("/api/energy-risk")
def get_energy_risk(user: CurrentUser = Depends(require_role("viewer"))) -> list[dict]:
    return compute_energy_risk_by_country()


@app.get("/api/product-summary")
def get_product_summary(user: CurrentUser = Depends(require_role("viewer"))) -> dict:
    return product_track_record_summary()


# ============================== PREDICTOR DE PRODUCTO (rol analyst) ==============================

class ProductQuery(BaseModel):
    producto: str


@app.post("/api/predict")
@limiter.limit("10/hour")  # cada llamada cuesta una cadena de LLM real -- limite de coste, no solo de abuso
def predict_product(request: Request, query: ProductQuery, user: CurrentUser = Depends(require_role("analyst"))) -> dict:
    """Cruza 4 bloques de datos reales para generar una tesis de inversion con hipotesis
    falsable. Nace en PENDING_REVIEW (Principio 8): no aparece en /api/product-summary ni se
    evalua contra mercado hasta que un `reviewer` la aprueba via /api/review/product/{id}."""
    settings.require_api_key()
    producto = query.producto.strip()
    if not producto:
        raise HTTPException(status_code=400, detail="El campo 'producto' no puede estar vacio.")

    with track_system_run("product_predict") as run:
        forecast, report_path = forecast_product(producto)
        if forecast is None:
            run.add_error(f"'{producto}': fallo del LLM o de validacion Pydantic.")
            raise HTTPException(
                status_code=502,
                detail="No se pudo generar la prediccion (fallo del LLM o de validacion). Intenta de nuevo.",
            )
        run.set_records_processed(1)

    report_path_str = str(report_path) if report_path else None
    prediction_id = save_product_prediction(forecast, report_path_str)
    record_audit_event(
        actor_email=user.email, actor_role=user.role, action="product_prediction_created",
        entity_type="product", entity_id=str(prediction_id), details={"producto": producto},
    )

    result = forecast.model_dump()
    result["report_url"] = f"/reports/{report_path.name}" if report_path else None
    result["prediction_id"] = prediction_id
    result["review_status"] = "PENDING_REVIEW"
    return result


# ============================== REVISION HUMANA (rol reviewer) ==============================

@app.get("/api/review/{kind}/pending")
def get_pending_review(kind: str, user: CurrentUser = Depends(require_role("reviewer"))) -> list[dict]:
    if kind not in ("pipeline", "product"):
        raise HTTPException(status_code=400, detail="kind debe ser 'pipeline' o 'product'")
    return list_pending_review(kind)


class ReviewDecisionRequest(BaseModel):
    decision: str  # "APPROVED" | "REJECTED"
    note: str | None = None


@app.post("/api/review/{kind}/{prediction_id}")
@limiter.limit("30/minute")  # defensa en profundidad: RBAC ya exige rol reviewer+, esto limita
# el radio de dano si un token de reviewer quedara comprometido (ej. aprobar/rechazar en masa via script).
def post_review_decision(
    request: Request, kind: str, prediction_id: int, body: ReviewDecisionRequest,
    user: CurrentUser = Depends(require_role("reviewer")),
) -> dict:
    if kind not in ("pipeline", "product"):
        raise HTTPException(status_code=400, detail="kind debe ser 'pipeline' o 'product'")
    try:
        return review_prediction(kind, prediction_id, body.decision, user.email, body.note, actor_role=user.role)
    except PermissionError as exc:
        raise HTTPException(status_code=423, detail=str(exc))  # 423 Locked: kill switch activo
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ============================== SISTEMA (kill switch, breakers, runs) ==============================

@app.get("/api/system/kill-switch")
def get_kill_switch(user: CurrentUser = Depends(require_role("viewer"))) -> dict:
    return get_kill_switch_status()


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: str | None = None


@app.post("/api/system/kill-switch")
@limiter.limit("10/minute")  # un interruptor de este calibre no deberia poder martillearse
def post_kill_switch(request: Request, body: KillSwitchRequest, user: CurrentUser = Depends(require_role("admin"))) -> dict:
    result = set_kill_switch(body.enabled, user.email, body.reason)
    record_audit_event(
        actor_email=user.email, actor_role=user.role, action="kill_switch_toggled",
        entity_type="system_control", entity_id="1",
        details={"enabled": body.enabled, "reason": body.reason},
    )
    return result


@app.get("/api/system/circuit-breakers")
def get_circuit_breakers(user: CurrentUser = Depends(require_role("viewer"))) -> list[dict]:
    return all_breaker_statuses()


@app.get("/api/system-runs")
def get_system_runs(user: CurrentUser = Depends(require_role("viewer"))) -> list[dict]:
    return list_recent_system_runs()


# ============================== MODEL RISK / GOVERNANCE (rol admin para editar) ==============================

@app.get("/api/model-inventory")
def get_model_inventory(user: CurrentUser = Depends(require_role("viewer"))) -> list[dict]:
    return list_model_inventory()


class ModelCardUpdateRequest(BaseModel):
    owner_email: str | None = None
    mark_validated_now: bool = False


@app.patch("/api/model-inventory/{name}")
@limiter.limit("20/minute")
def patch_model_card(request: Request, name: str, body: ModelCardUpdateRequest, user: CurrentUser = Depends(require_role("admin"))) -> dict:
    ok = update_model_card_governance(name, body.owner_email, user.email, body.mark_validated_now)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Modelo '{name}' no existe en el inventario.")
    record_audit_event(
        actor_email=user.email, actor_role=user.role, action="model_card_updated",
        entity_type="model_card", entity_id=name,
        details={"owner_email": body.owner_email, "mark_validated_now": body.mark_validated_now},
    )
    return {"name": name, "updated": True}


# ============================== AUDITORIA (rol admin) ==============================

@app.get("/api/audit-log")
def get_audit_log(limit: int = 100, user: CurrentUser = Depends(require_role("admin"))) -> list[dict]:
    return list_audit_log(limit)


@app.get("/api/audit-log/verify")
def get_audit_log_verification(user: CurrentUser = Depends(require_role("admin"))) -> dict:
    """Recalcula la cadena de hashes completa y reporta si sigue intacta (ver
    persistence/audit.py:verify_audit_chain) -- es lo que hace el log 'auditable de verdad'."""
    return verify_audit_chain()


# Se registran DESPUES de las rutas /api/* para que estas tengan prioridad sobre los
# catch-all de archivos estaticos. StaticFiles exige que el directorio exista en el momento
# del mount (que ocurre al importar este modulo, ANTES de que corra el lifespan de arriba),
# asi que se crea aqui tambien, no solo en el lifespan.
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/reports", StaticFiles(directory=str(REPORTS_DIR)), name="reports")

# html=True sirve frontend/index.html en la raiz "/". Debe ser el ULTIMO mount (catch-all).
# NOTA DE SEGURIDAD: este mount NO esta gateado por autenticacion (StaticFiles no soporta
# Depends() sin un proxy dedicado) -- el shell HTML/JS estatico es publico, pero es inerte sin
# los endpoints /api/* de arriba, que si exigen token valido. Documentado como limitacion
# conocida, no como omision silenciosa.
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
