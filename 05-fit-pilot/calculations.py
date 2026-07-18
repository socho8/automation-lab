"""
Módulo de cálculos de FitPilot.
Toda la matemática vive acá, separada de la IA, para que ningún número
salga "inventado" por el modelo.
"""

from datetime import date, timedelta

MESES_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def calculate_bmi(peso_kg: float, altura_cm: float) -> float:
    altura_m = altura_cm / 100
    return round(peso_kg / (altura_m ** 2), 1)


def calculate_bmr(peso_kg: float, altura_cm: float, edad: int, sexo: str) -> float:
    """Fórmula de Mifflin-St Jeor."""
    base = (10 * peso_kg) + (6.25 * altura_cm) - (5 * edad)
    if sexo.lower() in ("hombre", "masculino", "m"):
        return round(base + 5, 1)
    else:
        return round(base - 161, 1)


ACTIVITY_MULTIPLIERS = {
    "sedentario": 1.2,
    "ligero": 1.375,
    "moderado": 1.55,
    "activo": 1.725,
    "muy_activo": 1.9,
}


def calculate_tdee(bmr: float, nivel_actividad: str) -> float:
    multiplicador = ACTIVITY_MULTIPLIERS.get(nivel_actividad, 1.375)
    return round(bmr * multiplicador, 1)


def calculate_lean_mass(peso_kg: float, porcentaje_grasa: float | None) -> float | None:
    """Calcula la masa magra si se proporcionó % de grasa corporal (opcional)."""
    if porcentaje_grasa is None:
        return None
    return round(peso_kg * (1 - porcentaje_grasa / 100), 1)


MAX_TASA_SEMANAL_PERDIDA = 0.01
MAX_TASA_SEMANAL_GANANCIA = 0.0025
KCAL_POR_KG_GRASA = 7700

MIN_CALORIAS_HOMBRE = 1500
MIN_CALORIAS_MUJER = 1200


def calculate_calorie_target(tdee: float, objetivo: str, peso_kg: float, sexo: str) -> dict:
    """
    Calcula las calorías objetivo respetando:
    1. Un déficit/superávit máximo seguro.
    2. Un piso mínimo absoluto de calorías, que nunca se cruza.
    """
    ajustado_por_piso = False

    if objetivo == "perder_grasa":
        max_deficit_diario = (peso_kg * MAX_TASA_SEMANAL_PERDIDA * KCAL_POR_KG_GRASA) / 7
        deficit = min(max_deficit_diario, tdee * 0.25)
        calorias = round(tdee - deficit)
    elif objetivo == "ganar_masa":
        max_superavit_diario = (peso_kg * MAX_TASA_SEMANAL_GANANCIA * KCAL_POR_KG_GRASA) / 7
        calorias = round(tdee + max_superavit_diario)
    elif objetivo == "recomposicion":
        calorias = round(tdee - (tdee * 0.05))
    else:
        calorias = round(tdee)

    piso = MIN_CALORIAS_HOMBRE if sexo.lower() in ("hombre", "masculino", "m") else MIN_CALORIAS_MUJER
    if calorias < piso:
        calorias = piso
        ajustado_por_piso = True

    return {
        "calorias_objetivo": calorias,
        "diferencia_vs_tdee": round(calorias - tdee),
        "ajustado_por_piso": ajustado_por_piso,
    }


def calculate_macros(peso_kg: float, calorias_objetivo: float, objetivo: str,
                      masa_magra_kg: float | None = None) -> dict:
    """
    Orden de prioridad:
    1. Proteína -> por kg de masa magra si está disponible, si no por peso total.
    2. Grasas -> mínimo fijo por kg de peso corporal (no un % de las calorías).
    3. Carbohidratos -> lo que queda de las calorías totales.
    """
    base_para_proteina = masa_magra_kg if masa_magra_kg is not None else peso_kg

    if objetivo in ("perder_grasa", "recomposicion"):
        proteina_por_kg = 2.4 if masa_magra_kg else 2.2
    elif objetivo == "ganar_masa":
        proteina_por_kg = 2.0 if masa_magra_kg else 1.8
    else:
        proteina_por_kg = 1.8 if masa_magra_kg else 1.6

    proteina_g = round(base_para_proteina * proteina_por_kg)
    proteina_kcal = proteina_g * 4

    grasas_g = round(peso_kg * 0.8)
    grasas_kcal = grasas_g * 9

    carbos_kcal = calorias_objetivo - proteina_kcal - grasas_kcal
    carbos_g = max(round(carbos_kcal / 4), 0)

    return {
        "proteina_g": proteina_g,
        "carbohidratos_g": carbos_g,
        "grasas_g": grasas_g,
        "calculado_con_masa_magra": masa_magra_kg is not None,
    }


def _formatear_fecha_es(fecha: date) -> str:
    return f"{fecha.day} de {MESES_ES[fecha.month - 1]} de {fecha.year}"


def estimate_timeline(peso_actual: float, peso_objetivo: float, objetivo: str) -> dict:
    """Estima semanas realistas Y la fecha aproximada de logro."""
    diferencia_kg = abs(peso_objetivo - peso_actual)

    if objetivo == "perder_grasa":
        tasa_semanal_kg = peso_actual * MAX_TASA_SEMANAL_PERDIDA
    elif objetivo == "ganar_masa":
        tasa_semanal_kg = peso_actual * MAX_TASA_SEMANAL_GANANCIA
    else:
        return {"semanas_estimadas": None, "fecha_estimada": None,
                "mensaje": "No aplica cronograma de peso para este objetivo."}

    semanas = round(diferencia_kg / tasa_semanal_kg) if tasa_semanal_kg > 0 else None
    fecha_estimada = date.today() + timedelta(weeks=semanas) if semanas else None
    fecha_texto = _formatear_fecha_es(fecha_estimada) if fecha_estimada else None

    mensaje = (
        f"Si mantenés una buena adherencia, podrías alcanzar tu objetivo "
        f"aproximadamente durante la semana del {fecha_texto}."
        if fecha_texto else "No se pudo estimar una fecha."
    )

    return {
        "semanas_estimadas": semanas,
        "tasa_semanal_kg": round(tasa_semanal_kg, 2),
        "fecha_estimada": fecha_estimada.isoformat() if fecha_estimada else None,
        "mensaje": mensaje,
    }


def validate_body_fat(porcentaje_grasa: float | None) -> dict:
    if porcentaje_grasa is None:
        return {"valido": True, "mensaje": ""}

    if porcentaje_grasa < 3:
        return {
            "valido": False,
            "mensaje": "El porcentaje de grasa corporal es demasiado bajo."
        }

    if porcentaje_grasa > 70:
        return {
            "valido": False,
            "mensaje": "El porcentaje de grasa corporal parece incorrecto."
        }

    return {"valido": True, "mensaje": ""}


def validate_goal_consistency(
    peso_actual: float,
    peso_objetivo: float,
    objetivo: str
) -> dict:

    if objetivo == "perder_grasa" and peso_objetivo >= peso_actual:
        return {
            "coherente": False,
            "mensaje": "Si el objetivo es perder grasa, el peso objetivo debe ser menor que el actual."
        }

    if objetivo == "ganar_masa" and peso_objetivo <= peso_actual:
        return {
            "coherente": False,
            "mensaje": "Si el objetivo es ganar masa, el peso objetivo debe ser mayor que el actual."
        }

    return {
        "coherente": True,
        "mensaje": ""
    }


def validate_goal(peso_actual: float, peso_objetivo: float, semanas_deseadas: int, objetivo: str) -> dict:
    """
    Compara lo que el usuario pidió contra lo que es realista según
    el ritmo seguro. No fuerza el deseo del usuario; informa la realidad.
    """
    recomendado = estimate_timeline(peso_actual, peso_objetivo, objetivo)
    semanas_recomendadas = recomendado["semanas_estimadas"]

    if semanas_recomendadas is None:
        return {
            "realista": True,
            "semanas_recomendadas": None,
            "semanas_usuario": semanas_deseadas,
            "mensaje": "Este objetivo no requiere validación de ritmo de peso.",
        }

    realista = semanas_deseadas >= semanas_recomendadas

    if realista:
        mensaje = (
            f"🟢 Objetivo realista. Con tu plazo de {semanas_deseadas} semanas "
            f"tenés margen suficiente (se necesitan al menos {semanas_recomendadas})."
        )
    else:
        mensaje = (
            f"🔴 Objetivo demasiado agresivo. Pediste {semanas_deseadas} semanas, "
            f"pero a un ritmo seguro (~{recomendado['tasa_semanal_kg']} kg/semana) "
            f"se necesitan aproximadamente {semanas_recomendadas} semanas. "
            f"Se recomienda ajustar el plazo o el objetivo de peso."
        )

    return {
        "realista": realista,
        "semanas_recomendadas": semanas_recomendadas,
        "semanas_usuario": semanas_deseadas,
        "fecha_estimada_real": recomendado["fecha_estimada"],
        "mensaje": mensaje,
    }