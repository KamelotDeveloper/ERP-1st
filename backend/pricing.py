"""Pure pricing catalog for subscription plans (ordo | canyp).

Single canonical fallback for plan prices and durations on the backend.
The web codebase mirrors this table (suscipcion-api/lib/mp-contract.mjs)
so both flows charge identical prices. No external dependencies.

Each entry: id, nombre, precio, dias, descuento (0 = no plan-level discount).
`descripcion` is kept for the desktop frontend which consumes it.
"""

KNOWN_APPS = ("ordo", "canyp")

# Fallback table - values MUST match suscripcion-api/lib/mp-contract.mjs
PLANES_FALLBACK = {
    "ordo": [
        {"id": "1_mes", "nombre": "Mensual", "descripcion": "Acceso completo por 1 mes", "precio": 70000, "dias": 30, "descuento": 0},
        {"id": "6_meses", "nombre": "Semestral", "descripcion": "Acceso completo por 6 meses", "precio": 360000, "dias": 180, "descuento": 0},
        {"id": "1_anio", "nombre": "Anual", "descripcion": "Acceso completo por 1 año", "precio": 720000, "dias": 365, "descuento": 0},
    ],
    "canyp": [
        {"id": "canyp_1_mes", "nombre": "Mensual", "descripcion": "Acceso completo por 1 mes", "precio": 120000, "dias": 30, "descuento": 0},
        {"id": "canyp_6_meses", "nombre": "Semestral", "descripcion": "Acceso completo por 6 meses", "precio": 617000, "dias": 180, "descuento": 0},
        {"id": "canyp_1_anio", "nombre": "Anual", "descripcion": "Acceso completo por 1 año", "precio": 1234000, "dias": 365, "descuento": 0},
    ],
}


def get_planes_for_app(app_id: str):
    """Return the fallback plan catalog for app_id, or None if unknown.

    Callers must 400 on unknown app_id (fail-loud, never default to 'ordo').
    """
    return PLANES_FALLBACK.get(app_id)