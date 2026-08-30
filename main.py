"""Orquestador del pipeline. Uso:

    python main.py run             # ingesta + consenso cruzado + analisis macro
    python main.py evaluate        # evalua predicciones vencidas contra datos de mercado reales
    python main.py sync-conflicts  # sincroniza el registro de conflictos activos (Wikipedia)
    python main.py create-admin --email tu@email.com  # crea el primer usuario admin (CLI, no API)
"""
from __future__ import annotations

import argparse
import getpass
import json

from config import settings
from crosscheck.clustering import cluster_articles
from crosscheck.consensus import evaluate_cluster
from analysis.macro_engine import analyze_event
from ingestion.fetchers import fetch_all
from ingestion.raw_data_lake import persist_batch
from ingestion.sources import SOURCES
from persistence.conflicts import sync_active_conflicts
from persistence.db import init_db
from persistence.product_track_record import (
    evaluate_due_product_predictions,
    product_track_record_summary,
)
from persistence.system_runs import track_system_run
from persistence.track_record import (
    evaluate_due_predictions,
    save_analysis,
    save_consensus,
    track_record_summary,
)
from utils.logging_conf import get_logger

logger = get_logger(__name__)


def run_pipeline() -> None:
    settings.require_api_key()
    init_db()

    with track_system_run("pipeline_run") as run:
        logger.info("=== 1. INGESTA MULTI-FUENTE ===")
        articles = fetch_all(SOURCES)
        if not articles:
            run.add_warning("No se obtuvo ningun articulo en esta ejecucion.")
            logger.warning("No se obtuvo ningun articulo. Revisa conectividad o disponibilidad de los feeds.")
            return
        persist_batch(articles)

        logger.info("=== 2. CONSENSO CRUZADO / MITIGACION DE SESGO ===")
        clusters = cluster_articles(articles)

        logger.info("=== 3. ANALISIS MACROECONOMICO ===")
        generated = 0
        for cluster_id, cluster in clusters.items():
            verdict = evaluate_cluster(cluster_id, cluster)
            if verdict is None:
                continue

            save_consensus(verdict)

            if not verdict.get("apto_para_analisis"):
                logger.info(
                    "Cluster %s NO apto para analisis: %s",
                    cluster_id, verdict.get("motivo_rechazo", "sin motivo especificado"),
                )
                continue

            analysis, causal_links = analyze_event(verdict)
            if analysis is None:
                run.add_warning(f"Cluster {cluster_id}: cadena de agentes abortada o vetada (ver logs/agent_traces).")
                continue

            save_analysis(analysis, cluster_id, causal_links)
            generated += 1

        run.set_records_processed(generated)
        logger.info(
            "Pipeline completo: %d analisis generados sobre %d clusters candidatos.",
            generated, len(clusters),
        )


def run_evaluation() -> None:
    """Evalua las predicciones vencidas de AMBOS track records (pipeline automatico y
    predictor de producto), pero los reporta siempre por separado -nunca mezclados-."""
    with track_system_run("evaluate") as run:
        results = evaluate_due_predictions()
        summary = track_record_summary()
        product_results = evaluate_due_product_predictions()
        product_summary = product_track_record_summary()
        run.set_records_processed(len(results) + len(product_results))

    print(json.dumps(
        {
            "pipeline_automatico": {"evaluadas_ahora": results, "resumen_track_record": summary},
            "predictor_producto": {"evaluadas_ahora": product_results, "resumen_track_record": product_summary},
        },
        indent=2, ensure_ascii=False,
    ))


def run_sync_conflicts() -> None:
    with track_system_run("sync_conflicts") as run:
        n = sync_active_conflicts()
        run.set_records_processed(n)
    logger.info("Registro de conflictos activos actualizado: %d conflictos.", n)


def run_create_admin(email: str, password: str | None) -> None:
    """Bootstrap del primer usuario admin. Deliberadamente un comando de CLI local y NO un
    endpoint HTTP: crear cuentas con privilegio maximo no debe ser alcanzable por red, ni
    siquiera detras de auth (Institutional Prompt, seccion 6). Solo funciona si `users` esta
    vacia -- para dar de alta admins adicionales usa `persistence.users.create_user` desde una
    shell de confianza, con el mismo usuario admin ya autenticando esa sesion."""
    init_db()
    from persistence.users import bootstrap_admin_if_empty

    if password is None:
        password = getpass.getpass(f"Contrasena para {email}: ")
        confirm = getpass.getpass("Repite la contrasena: ")
        if password != confirm:
            print("Las contrasenas no coinciden. Cancelado.")
            return

    created = bootstrap_admin_if_empty(email, password)
    if created:
        print(f"Usuario admin '{email}' creado. Ya puedes autenticarte en POST /api/auth/login.")
    else:
        print(
            "No se creo ningun usuario: la tabla 'users' ya tiene al menos un registro. "
            "Este comando solo arranca el PRIMER admin; usa persistence.users.create_user "
            "para dar de alta cuentas adicionales una vez autenticado como admin."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Macro Intelligence Pipeline")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="Ejecuta ingesta + consenso cruzado + analisis macro")
    sub.add_parser("evaluate", help="Evalua predicciones vencidas contra datos de mercado reales")
    sub.add_parser("sync-conflicts", help="Sincroniza el registro de conflictos activos (Wikipedia)")
    admin_parser = sub.add_parser(
        "create-admin",
        help="Crea el primer usuario admin (solo si la tabla 'users' esta vacia). Comando de CLI, no expuesto por API.",
    )
    admin_parser.add_argument("--email", required=True, help="Email del admin a crear")
    admin_parser.add_argument(
        "--password", default=None,
        help="Opcional: si se omite, se pide de forma interactiva (recomendado, no queda en el historial de la shell)",
    )
    args = parser.parse_args()

    if args.command == "run":
        run_pipeline()
    elif args.command == "evaluate":
        run_evaluation()
    elif args.command == "sync-conflicts":
        run_sync_conflicts()
    elif args.command == "create-admin":
        run_create_admin(args.email, args.password)


if __name__ == "__main__":
    main()
