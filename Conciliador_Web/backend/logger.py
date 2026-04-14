"""
Módulo centralizado de logging para Conciliador Bancario.

Uso:
    from logger import get_logger
    logger = get_logger(__name__)
    logger.info("Mensaje")
    logger.warning("Advertencia")
    logger.error("Error", exc_info=True)

Variables de entorno:
    LOG_LEVEL       - Nivel de log: DEBUG, INFO, WARNING, ERROR (default: INFO)
    LOG_DIR         - Directorio donde se guardan los archivos de log (default: ./logs)
    LOG_MAX_MB      - Tamaño máximo por archivo de log en MB (default: 10)
    LOG_BACKUPS     - Cantidad de archivos de backup a conservar (default: 5)
    ENVIRONMENT     - "development" o "production" (default: production)
"""

import os
import logging
import logging.handlers
from pathlib import Path

# --- Configuración desde entorno ---
LOG_LEVEL_NAME = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)
LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
LOG_MAX_BYTES = int(os.getenv("LOG_MAX_MB", "10")) * 1024 * 1024
LOG_BACKUPS = int(os.getenv("LOG_BACKUPS", "5"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").lower()
IS_DEV = ENVIRONMENT == "development"

# --- Formatos ---
FMT_DETALLADO = "%(asctime)s [%(levelname)-8s] %(name)s (%(filename)s:%(lineno)d): %(message)s"
FMT_SIMPLE = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"


class ColorFormatter(logging.Formatter):
    """Formatter con colores ANSI para consola en desarrollo."""
    COLORES = {
        logging.DEBUG:    "\033[37m",    # blanco
        logging.INFO:     "\033[36m",    # cyan
        logging.WARNING:  "\033[33m",    # amarillo
        logging.ERROR:    "\033[31m",    # rojo
        logging.CRITICAL: "\033[1;31m",  # rojo negrita
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORES.get(record.levelno, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


def _configurar_logging() -> None:
    """Configura los handlers de logging globales. Se llama una sola vez."""
    root = logging.getLogger()
    if root.handlers:
        return  # Ya configurado

    root.setLevel(LOG_LEVEL)

    # --- Handler de consola ---
    consola = logging.StreamHandler()
    consola.setLevel(LOG_LEVEL)
    if IS_DEV:
        consola.setFormatter(ColorFormatter(FMT_DETALLADO, datefmt=DATE_FMT))
    else:
        consola.setFormatter(logging.Formatter(FMT_SIMPLE, datefmt=DATE_FMT))
    root.addHandler(consola)

    # --- Handler de archivo con rotación ---
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / "conciliador.log"
        archivo = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUPS,
            encoding="utf-8"
        )
        archivo.setLevel(LOG_LEVEL)
        archivo.setFormatter(logging.Formatter(FMT_DETALLADO, datefmt=DATE_FMT))
        root.addHandler(archivo)

        # Archivo separado solo para errores
        error_file = LOG_DIR / "errores.log"
        errores = logging.handlers.RotatingFileHandler(
            filename=error_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUPS,
            encoding="utf-8"
        )
        errores.setLevel(logging.ERROR)
        errores.setFormatter(logging.Formatter(FMT_DETALLADO, datefmt=DATE_FMT))
        root.addHandler(errores)

    except PermissionError:
        root.warning("No se pudo crear el directorio de logs. Solo se loguea en consola.")

    # Silenciar loggers ruidosos de librerías externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    root.info(
        f"Logging inicializado | nivel={LOG_LEVEL_NAME} | "
        f"entorno={ENVIRONMENT} | dir_logs={LOG_DIR.resolve()}"
    )


def get_logger(nombre: str) -> logging.Logger:
    """
    Devuelve un logger configurado para el módulo indicado.

    Uso típico:
        logger = get_logger(__name__)
    """
    _configurar_logging()
    return logging.getLogger(nombre)
