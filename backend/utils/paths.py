"""
Utilidades para manejar paths en entornos de producción y desarrollo.
Maneja correctamente _MEIPASS de PyInstaller vs desarrollo local.
"""
import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """Returns True si estamos运行ando desde un ejecutable PyInstaller."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_base_dir() -> Path:
    """
    Returns la base del directorio de la aplicación.
    - En desarrollo: directorio del proyecto
    - En producción (PyInstaller): directorio del ejecutable
    """
    if is_frozen():
        # Estamos en ejecutable - usar directorio del exe
        return Path(sys.executable).parent
    else:
        # Estamos en desarrollo - usar directorio del script
        return Path(__file__).parent


def resource_path(relative: str) -> Path:
    """
    Returns path para assets de SOLO LECTURA (recursos embebidos).
    - En desarrollo: look in project root
    - En producción: look in _MEIPASS (recursos embebidos)
    
    NO usar para archivos mutables como SQLite DB.
    """
    if is_frozen():
        # PyInstaller: los recursos están en _MEIPASS
        base = Path(sys._MEIPASS)
    else:
        # Desarrollo: usar directorio del proyecto
        base = Path(__file__).parent.parent
    
    return base / relative


def data_path(relative: str) -> Path:
    """
    Returns path para archivos MUTABLES (como SQLite DB).
    - SIEMPRE usar directorio del ejecutable, NO _MEIPASS
    - Crea el directorio si no existe
    
    Importante: La DB SQLite NUNCA debe estar en _MEIPASS
    porque es mutable y _MEIPASS es solo lectura.
    """
    base = get_base_dir()
    full_path = base / relative
    
    # Crear directorios padres si no existen
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    return full_path


def get_db_path(db_name: str = "carpinteria.db") -> Path:
    """
    Returns el path correcto para la base de datos SQLite.
    Siempre usa data_path, nunca resource_path.
    """
    return data_path(db_name)


def ensure_data_dir() -> Path:
    """Crea y retorna el directorio de datos si no existe."""
    data_dir = data_path("")
    return data_dir