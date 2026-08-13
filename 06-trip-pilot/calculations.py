"""
Módulo de cálculos de TripPilot.
Todo lo que se puede calcular con datos reales/matemática vive acá.
La IA (Groq) solo entra después, para redactar itinerario/checklist/tips
usando estos números ya calculados.
"""

import json
from pathlib import Path

import requests

DATA_PATH = Path(__file__).parent / "data" / "costo_vida.json"

# Tasas de respaldo (aproximadas, enero 2026) por si la API de cambio
# no responde. Se usan SOLO como fallback; en producción siempre se
# intenta la tasa en vivo primero.
FALLBACK_RATES_TO_USD = {
    "USD": 1.0,
    "EUR": 1.165,
    "GBP": 1.33,
    "ARS": 0.00085,
    "MXN": 0.055,
}


def convert_to_usd(monto: float, moneda: str) -> dict:
    """
    Convierte un monto a USD (la moneda del dataset de costos) usando
    Frankfurter (API gratuita del BCE, sin key). Si falla la conexión,
    usa una tasa de respaldo aproximada y lo marca explícitamente.
    """
    moneda = moneda.upper()
    if moneda == "USD":
        return {"monto_usd": monto, "en_vivo": True, "tasa": 1.0}

    try:
        resp = requests.get(
            "https://api.frankfurter.app/latest",
            params={"amount": monto, "from": moneda, "to": "USD"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        monto_usd = data["rates"]["USD"]
        return {"monto_usd": round(monto_usd, 2), "en_vivo": True, "tasa": None}
    except Exception:
        tasa_fallback = FALLBACK_RATES_TO_USD.get(moneda)
        if tasa_fallback is None:
            return {"monto_usd": None, "en_vivo": False, "tasa": None}
        return {
            "monto_usd": round(monto * tasa_fallback, 2),
            "en_vivo": False,
            "tasa": tasa_fallback,
        }


def load_cost_index() -> dict:
    """Carga el dataset de costo de vida por país (WhereNext, CC BY 4.0)."""
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_countries() -> list[str]:
    """Lista de países disponibles, ordenada alfabéticamente (para el selectbox)."""
    data = load_cost_index()
    return sorted(data["paises"].keys())


# ── Multiplicador turístico ──────────────────────────────────────────────
#
# El dataset da el costo de vida RESIDENCIAL (lo que gasta alguien que vive
# ahí). Un viajero gasta distinto según el tipo de viaje:
# - Mochilero: MENOS que un residente promedio (hostels compartidos,
#   comida callejera, transporte público) -> multiplicador < 1
# - Económico: similar a vivir ahí de forma ajustada -> ~1
# - Estándar: hoteles 3 estrellas, restaurantes turísticos -> notablemente más
# - Premium: hoteles 4-5 estrellas, actividades pagas, taxis -> mucho más
#
# Estos valores son una aproximación razonable, no una medición exacta
# (no existe un dataset público gratuito con este nivel de detalle).

TOURIST_MULTIPLIERS = {
    "mochilero": 0.7,
    "economico": 1.1,
    "estandar": 1.8,
    "premium": 3.2,
}


def get_daily_cost_estimate(pais: str, tipo_viaje: str) -> dict | None:
    """
    Estima el gasto diario de VIAJE (no residencial) para un país y tipo
    de viaje. Devuelve None si el país no está en el dataset.
    """
    data = load_cost_index()
    info = data["paises"].get(pais)
    if info is None:
        return None

    costo_diario_residencial = info["monthly_estimate_usd"] / 30
    multiplicador = TOURIST_MULTIPLIERS.get(tipo_viaje, 1.1)
    costo_diario_turistico = round(costo_diario_residencial * multiplicador)

    return {
        "costo_diario_estimado_usd": costo_diario_turistico,
        "costo_diario_residencial_usd": round(costo_diario_residencial),
        "multiplicador_aplicado": multiplicador,
        "region": info["region"],
    }


def estimate_trip_cost(pais: str, dias: int, personas: int, tipo_viaje: str) -> dict | None:
    """Estima el costo total del viaje completo. None si el país no está en el dataset."""
    estimado = get_daily_cost_estimate(pais, tipo_viaje)
    if estimado is None:
        return None

    costo_total = estimado["costo_diario_estimado_usd"] * dias * personas

    return {
        "costo_total_estimado_usd": costo_total,
        "costo_diario_por_persona_usd": estimado["costo_diario_estimado_usd"],
        "region": estimado["region"],
    }


def validate_budget_feasibility(presupuesto_total: float, moneda: str, dias: int,
                                  personas: int, pais: str, tipo_viaje: str) -> dict:
    """
    Compara el presupuesto del usuario (en SU moneda) contra el costo
    estimado del destino (en USD). Convierte primero -> compara después.
    Si el país no está en el dataset, no bloquea -> simplemente no valida.
    """
    estimacion = estimate_trip_cost(pais, dias, personas, tipo_viaje)

    if estimacion is None:
        return {
            "nivel": None,
            "mensaje": f"No tenemos datos de costo de referencia para '{pais}', "
                       f"así que no podemos validar tu presupuesto contra ese destino.",
            "costo_estimado_usd": None,
        }

    conversion = convert_to_usd(presupuesto_total, moneda)
    if conversion["monto_usd"] is None:
        return {
            "nivel": None,
            "mensaje": f"No pudimos convertir {moneda} a USD para comparar con el costo estimado.",
            "costo_estimado_usd": estimacion["costo_total_estimado_usd"],
        }

    presupuesto_usd = conversion["monto_usd"]
    nota_conversion = "" if conversion["en_vivo"] else " (tasa de cambio aproximada, no en vivo)"

    costo_estimado = estimacion["costo_total_estimado_usd"]
    ratio = presupuesto_usd / costo_estimado if costo_estimado > 0 else 0

    if ratio < 0.7:
        nivel = "🔴"
        mensaje = (f"⚠️ Presupuesto muy ajustado para {pais}. "
                   f"El costo estimado para este viaje es ~{costo_estimado} USD, "
                   f"y tu presupuesto equivale a ~{round(presupuesto_usd)} USD{nota_conversion} — "
                   f"considerá aumentarlo o bajar el nivel de viaje.")
    elif ratio < 0.9:
        nivel = "🟡"
        mensaje = (f"Presupuesto justo para {pais} (estimado ~{costo_estimado} USD "
                   f"vs. tu presupuesto de ~{round(presupuesto_usd)} USD{nota_conversion}). "
                   f"Vas a tener que cuidar los gastos extra.")
    else:
        nivel = "🟢"
        mensaje = (f"Presupuesto cómodo para {pais} (estimado ~{costo_estimado} USD "
                   f"contra tu presupuesto de ~{round(presupuesto_usd)} USD{nota_conversion}).")

    return {"nivel": nivel, "mensaje": mensaje, "costo_estimado_usd": costo_estimado,
            "presupuesto_convertido_usd": round(presupuesto_usd), "conversion_en_vivo": conversion["en_vivo"]}


# ── Presupuesto inteligente (paso 3, no depende del país) ────────────────

# Reparto base por categoría. Se ajusta levemente según tipo_viaje:
# un mochilero gasta proporcionalmente menos en hotel y más en "extras"
# de experiencias; un premium gasta más proporción en hotel.
BUDGET_SPLITS = {
    "mochilero":  {"hotel": 0.30, "comida": 0.25, "transporte": 0.15, "actividades": 0.15, "extras": 0.10, "emergencia": 0.05},
    "economico":  {"hotel": 0.38, "comida": 0.21, "transporte": 0.10, "actividades": 0.21, "extras": 0.07, "emergencia": 0.03},
    "estandar":   {"hotel": 0.42, "comida": 0.20, "transporte": 0.10, "actividades": 0.20, "extras": 0.05, "emergencia": 0.03},
    "premium":    {"hotel": 0.48, "comida": 0.18, "transporte": 0.08, "actividades": 0.18, "extras": 0.06, "emergencia": 0.02},
}


def calculate_budget_breakdown(presupuesto_total: float, tipo_viaje: str) -> dict:
    """Reparte el presupuesto total entre categorías, según el tipo de viaje."""
    splits = BUDGET_SPLITS.get(tipo_viaje, BUDGET_SPLITS["economico"])
    return {categoria: round(presupuesto_total * pct) for categoria, pct in splits.items()}


def calculate_daily_budget(presupuesto_total: float, dias: int, tipo_viaje: str) -> dict:
    """Desglose del presupuesto diario, día por categoría."""
    breakdown_total = calculate_budget_breakdown(presupuesto_total, tipo_viaje)
    por_dia = {categoria: round(monto / dias) for categoria, monto in breakdown_total.items()}
    return {
        "presupuesto_por_dia_total": round(presupuesto_total / dias),
        "desglose_por_dia": por_dia,
    }


def what_can_i_do_with_budget(presupuesto_total: float, moneda: str, dias: int,
                                personas: int, pais: str) -> dict:
    """
    Para un presupuesto dado (en su moneda), indica qué tipo de viaje es
    razonable, y cuánto haría falta para subir de nivel. 100% basado en
    reglas, sin IA (comparación directa contra el dataset de costos).
    """
    resultados = {}
    for tipo in ("mochilero", "economico", "estandar", "premium"):
        estimacion = estimate_trip_cost(pais, dias, personas, tipo)
        if estimacion:
            resultados[tipo] = estimacion["costo_total_estimado_usd"]

    if not resultados:
        return {"recomendacion": None, "mensaje": f"Sin datos de costo para '{pais}'."}

    conversion = convert_to_usd(presupuesto_total, moneda)
    if conversion["monto_usd"] is None:
        return {"recomendacion": None, "mensaje": f"No pudimos convertir {moneda} a USD."}
    presupuesto_total = conversion["monto_usd"]  # de acá en más, todo en USD

    alcanzable = [tipo for tipo, costo in resultados.items() if costo <= presupuesto_total]
    nivel_actual = alcanzable[-1] if alcanzable else None

    niveles_ordenados = ["mochilero", "economico", "estandar", "premium"]
    siguiente_nivel = None
    if nivel_actual:
        idx = niveles_ordenados.index(nivel_actual)
        if idx + 1 < len(niveles_ordenados):
            siguiente_nivel = niveles_ordenados[idx + 1]
    elif resultados:
        siguiente_nivel = "mochilero"  # ni el nivel más económico alcanza

    mensajes_nivel = {
        "mochilero": "un hostel, transporte público, y comidas económicas",
        "economico": "alojamiento económico (hostel privado/Airbnb compartido) y algunas actividades pagas",
        "estandar": "un hotel de 3 estrellas y varias actividades pagas",
        "premium": "hoteles de 4-5 estrellas y experiencias premium",
    }

    if nivel_actual:
        mensaje = f"Con este presupuesto es recomendable {mensajes_nivel[nivel_actual]}."
        if siguiente_nivel:
            faltante = resultados[siguiente_nivel] - presupuesto_total
            mensaje += (f" Si aumentás el presupuesto en ~{round(faltante)} USD, "
                        f"podrías viajar en modo '{siguiente_nivel}'.")
    else:
        faltante = resultados["mochilero"] - presupuesto_total
        mensaje = (f"Este presupuesto no alcanza ni para el modo más económico en {pais}. "
                   f"Necesitarías ~{round(faltante)} USD más, o menos días de viaje.")

    return {
        "nivel_actual": nivel_actual,
        "siguiente_nivel": siguiente_nivel,
        "costos_por_nivel": resultados,
        "mensaje": mensaje,
    }
