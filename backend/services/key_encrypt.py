"""Encriptación de claves privadas en reposo.

Usa Fernet (AES-128-CBC + HMAC-SHA256) con una clave derivada
de un secreto del servidor. El secreto se almacena en:

  1. Variable de entorno `GA_ERP_KEY_ENCRYPT_SECRET`
  2. Si no existe, se genera y guarda en `backend/.key_encrypt_secret`

En producción, SETEAR la variable de entorno con un valor seguro.
"""

import os
import base64
import hashlib
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_SALT = b"ga-erp-key-encrypt-v1"

_fernet_instance = None


def _get_fernet() -> Fernet:
    """Obtiene o crea una instancia Fernet con la clave derivada."""
    global _fernet_instance
    if _fernet_instance is not None:
        return _fernet_instance

    secret = os.environ.get("GA_ERP_KEY_ENCRYPT_SECRET")
    if not secret:
        # Fallback: leer desde archivo (solo desarrollo)
        secret_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), ".key_encrypt_secret"
        )
        if os.path.exists(secret_file):
            with open(secret_file, "r") as f:
                secret = f.read().strip()
        else:
            # Generar nuevo secreto
            secret = base64.b64encode(os.urandom(32)).decode("utf-8")
            with open(secret_file, "w") as f:
                f.write(secret)
            logger.info(f"Clave de encriptación generada en {secret_file}")

    # Derivar clave Fernet de 32 bytes usando PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=600000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(secret.encode("utf-8")))
    _fernet_instance = Fernet(key)
    return _fernet_instance


def encrypt_key(key_data: bytes) -> bytes:
    """Encripta datos de clave privada.

    Args:
        key_data: Contenido binario de la clave privada.

    Returns:
        Datos encriptados (token Fernet).
    """
    f = _get_fernet()
    return f.encrypt(key_data)


def decrypt_key(encrypted_data: bytes) -> bytes:
    """Desencripta datos de clave privada.

    Args:
        encrypted_data: Token Fernet previamente encriptado.

    Returns:
        Datos originales de la clave privada.
    """
    f = _get_fernet()
    return f.decrypt(encrypted_data)
