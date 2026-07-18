"""
FitPilot — Automation Lab Project #5
----------------------------------------
Genera rutina, menú semanal, lista de compras y proyección de evolución,
a partir de datos personales. Python calcula y VALIDA todos los números;
la IA (Groq) solo redacta el contenido usando esos números ya calculados.

Requiere: streamlit, groq, fpdf2
"""

import json
from io import BytesIO
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import streamlit as st
from groq import Groq

from calculations import (
    calculate_bmi, calculate_bmr, calculate_tdee, calculate_lean_mass,
    calculate_calorie_target, calculate_macros, estimate_timeline, validate_goal, validate_goal_consistency,validate_body_fat
)

st.set_page_config(page_title="FitPilot", page_icon="🏋️", layout="wide")

MODEL = "llama-3.3-70b-versatile"


# ── Cliente Groq ─────────────────────────────────────────────────────

def get_client() -> Groq:
    return Groq(api_key=st.secrets["GROQ_API_KEY"])


def ask_llm(prompt: str, json_mode: bool = True) -> str:
    client = get_client()
    kwargs = {"response_format": {"type": "json_object"}} if json_mode else {}
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        **kwargs,
    )
    return response.choices[0].message.content


# ── Generadores (reciben SOLO números ya calculados) ─────────────────────

def generate_routine(dias_fuerza: int, dias_cardio: int, minutos_sesion: int, objetivo: str) -> dict:
    prompt = f"""
    Armá una rutina de entrenamiento semanal en español para una persona
    con este perfil:
    - Objetivo: {objetivo}
    - Días de fuerza disponibles: {dias_fuerza}
    - Días de cardio disponibles: {dias_cardio}
    - Tiempo por sesión: {minutos_sesion} minutos

    Distribuí los días de la semana (lunes a domingo) combinando fuerza,
    cardio y descanso de forma realista. Para los días de fuerza, indicá
    grupo muscular y 4-6 ejercicios con series x repeticiones sugeridas.

    Respondé ÚNICAMENTE con este JSON:
    {{"rutina": {{
        "lunes": {{"tipo": "fuerza|cardio|descanso", "grupo_muscular": "...",
                    "ejercicios": ["...", "..."], "cardio_min": 0}},
        "martes": {{...}}, "miercoles": {{...}}, "jueves": {{...}},
        "viernes": {{...}}, "sabado": {{...}}, "domingo": {{...}}
    }}}}
    """
    return json.loads(ask_llm(prompt))["rutina"]


def generate_menu(calorias: int, macros: dict, comidas_por_dia: int, preferencias: list[str]) -> dict:
    prefs_texto = ", ".join(preferencias) if preferencias else "sin preferencias especiales"
    prompt = f"""
    Armá un menú semanal en español (lunes a domingo) que cumpla EXACTAMENTE
    estos valores diarios (ya calculados, no los cambies):
    - Calorías: {calorias} kcal/día
    - Proteína: {macros['proteina_g']} g/día
    - Carbohidratos: {macros['carbohidratos_g']} g/día
    - Grasas: {macros['grasas_g']} g/día

    Distribuí en {comidas_por_dia} comidas por día.
    Preferencias del usuario: {prefs_texto}.

    Respondé ÚNICAMENTE con este JSON:
    {{"menu": {{
        "lunes": {{"🍳 Desayuno": "...", "🥗 Almuerzo": "...", "🥜 Merienda": "...", "🍲 Cena": "..."}},
        "martes": {{...}}, "miercoles": {{...}}, "jueves": {{...}},
        "viernes": {{...}}, "sabado": {{...}}, "domingo": {{...}}
    }}}}
    Si {comidas_por_dia} es distinto de 4, ajustá las claves de cada día
    (por ejemplo "🥜 Colación de la mañana", "🍎 Colación de la tarde") según corresponda.
    """
    return json.loads(ask_llm(prompt))["menu"]


def generate_shopping_list(menu: dict) -> dict:
    prompt = f"""
    Basándote en este menú semanal, generá una lista de compras agrupada
    por categoría, en español, sin cantidades repetidas.

    MENÚ:
    {json.dumps(menu, ensure_ascii=False)}

    Respondé ÚNICAMENTE con este JSON:
    {{"lista_compras": {{
        "proteinas": ["...", "..."],
        "carbohidratos": ["...", "..."],
        "verduras": ["...", "..."],
        "frutas": ["...", "..."],
        "lacteos": ["...", "..."],
        "otros": ["...", "..."]
    }}}}
    """
    return json.loads(ask_llm(prompt))["lista_compras"]


# ── Exportar a PDF ─────────────────────────────────────────────────────

def export_to_pdf(calculos: dict, rutina: dict, menu: dict, lista_compras: dict) -> bytes:

    # Registrar una fuente con soporte para acentos
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", "DejaVuSans.ttf"))
        font = "DejaVu"
    except:
        font = "Helvetica"

    buffer = BytesIO()

    doc = SimpleDocTemplate(buffer)

    styles = getSampleStyleSheet()

    estilo = styles["BodyText"]
    estilo.fontName = font
    estilo.leading = 18

    titulo = styles["Heading1"]
    titulo.fontName = font

    story = []

    story.append(Paragraph("FitPilot - Tu Plan Personalizado", titulo))

    story.append(Paragraph(f"<b>Calorías objetivo:</b> {calculos['calorias_objetivo']} kcal", estilo))
    story.append(Paragraph(f"<b>Proteínas:</b> {calculos['macros']['proteina_g']} g", estilo))
    story.append(Paragraph(f"<b>Carbohidratos:</b> {calculos['macros']['carbohidratos_g']} g", estilo))
    story.append(Paragraph(f"<b>Grasas:</b> {calculos['macros']['grasas_g']} g", estilo))

    story.append(Paragraph("<br/><b>Rutina semanal</b>", titulo))

    for dia, info in rutina.items():
        story.append(
            Paragraph(
                f"<b>{dia.capitalize()}</b>: {info.get('tipo','')} - {info.get('grupo_muscular','')}",
                estilo
            )
        )

    story.append(Paragraph("<br/><b>Menú semanal</b>", titulo))

    for dia, comidas in menu.items():

        story.append(Paragraph(f"<b>{dia.capitalize()}</b>", estilo))

        for momento, detalle in comidas.items():

            story.append(
                Paragraph(
                    f"• <b>{momento.capitalize()}</b>: {detalle}",
                    estilo
                )
            )

    story.append(Paragraph("<br/><b>Lista de compras</b>", titulo))

    for categoria, items in lista_compras.items():

        texto = ", ".join(items)

        story.append(
            Paragraph(
                f"<b>{categoria.capitalize()}</b>: {texto}",
                estilo
            )
        )

    doc.build(story)

    pdf = buffer.getvalue()
    buffer.close()

    return pdf


# ── Interfaz ─────────────────────────────────────────────────────────────

st.title("🏋️ FitPilot")
st.caption("Tu plan de entrenamiento y nutrición, calculado con matemática real e Inteligencia Artificial.")
st.info("ℹ️ ESTA APP USA FÓRMULAS ESTÁNDAR DE NUTRICIÓN DEPORTIVA. NO REEMPLAZA EL CONSEJO DE UN PROFESIONAL DE LA SALUD.")

with st.form("datos_form"):
    st.subheader("1️⃣ Datos personales")
    c1, c2, c3 = st.columns(3)
    with c1:
        edad = st.number_input("Edad", 14, 90, 30)
        sexo = st.selectbox("Sexo", ["Hombre", "Mujer"])
    with c2:
        altura = st.number_input("Altura (cm)", 130, 220, 175)
        peso = st.number_input("Peso actual (kg)", 35.0, 200.0, 75.0)
    with c3:
        nivel_actividad = st.selectbox(
            "Nivel de actividad",
            ["Sedentario", "Ligero", "Moderado", "Activo", "Muy Activo"],
        )
        grasa_corporal = st.number_input(
            "% de grasa corporal (opcional, dejar en 0 si no lo sabés)",
            0.0, 100.0, 0.0,
        )

    st.subheader("2️⃣ Objetivo")
    objetivo_label = st.selectbox(
        "¿Cuál es tu objetivo?",
        ["Perder grasa", "Ganar masa muscular", "Recomposición corporal", "Mantener peso"],
    )
    objetivo_map = {
        "Perder grasa": "perder_grasa",
        "Ganar masa muscular": "ganar_masa",
        "Recomposición corporal": "recomposicion",
        "Mantener peso": "mantener",
    }
    objetivo = objetivo_map[objetivo_label]

    peso_objetivo = None
    semanas_deseadas = None
    if objetivo in ("perder_grasa", "ganar_masa"):
        cpeso, csemanas = st.columns(2)
        with cpeso:
            peso_objetivo = st.number_input(
                "Peso objetivo (kg)", 35.0, 200.0,
                peso - 5 if objetivo == "perder_grasa" else peso + 3,
            )
        with csemanas:
            semanas_deseadas = st.number_input("¿En cuántas semanas te gustaría lograrlo?", 1, 104, 12)

    st.subheader("3️⃣ Entrenamiento")
    c4, c5, c6 = st.columns(3)
    with c4:
        dias_fuerza = st.slider("Días de fuerza por semana", 0, 6, 3)
    with c5:
        dias_cardio = st.slider("Días de cardio por semana", 0, 6, 2)
    with c6:
        minutos_sesion = st.selectbox("Tiempo disponible por sesión", [30, 45, 60, 90])

    st.subheader("4️⃣ Alimentación")
    comidas_por_dia = st.selectbox("¿Cuántas comidas por día?", [3, 4, 5, 6], index=1)
    preferencias = st.multiselect(
        "Preferencias",
        ["Económico", "Alto en proteína", "Vegetariano", "Sin lactosa", "Sin gluten"],
    )

    submitted = st.form_submit_button("🚀 Generar plan")

if submitted:
    # ── Paso 0: VALIDAR antes de calcular nada ──
    # "0" en el input de grasa corporal significa "no lo cargué",
    # así que lo tratamos como None, no como un valor real a validar.
    grasa_input = grasa_corporal if grasa_corporal > 0 else None

    errores = []

    body_fat_check = validate_body_fat(grasa_input)
    if not body_fat_check["valido"]:
        errores.append(body_fat_check["mensaje"])

    if peso_objetivo is not None:
        coherence_check = validate_goal_consistency(
                    peso,
                    peso_objetivo,
                    objetivo)
        if not coherence_check["coherente"]:
            errores.append(coherence_check["mensaje"])

    if errores:
        for error in errores:
            st.error(f"❌ {error}")
        st.stop()  # No se calcula NADA si algo es incoherente

    # ── Paso 1: TODO lo numérico se calcula en Python, sin IA ──
    bmi = calculate_bmi(peso, altura)
    bmr = calculate_bmr(peso, altura, edad, sexo)
    tdee = calculate_tdee(bmr, nivel_actividad)
    cal = calculate_calorie_target(tdee, objetivo, peso, sexo)

    masa_magra = calculate_lean_mass(peso, grasa_input)
    macros = calculate_macros(peso, cal["calorias_objetivo"], objetivo, masa_magra_kg=masa_magra)

    timeline = None
    goal_check = None
    if peso_objetivo:
        timeline = estimate_timeline(peso, peso_objetivo, objetivo)
        goal_check = validate_goal(peso, peso_objetivo, semanas_deseadas, objetivo)

    calculos = {**cal, "bmi": bmi, "bmr": bmr, "tdee": tdee, "macros": macros, "masa_magra": masa_magra}
    st.session_state["calculos"] = calculos
    st.session_state["timeline"] = timeline
    st.session_state["goal_check"] = goal_check

    # ── Paso 2: la IA redacta contenido usando esos números fijos ──
    with st.spinner("Generando tu rutina..."):
        st.session_state["rutina"] = generate_routine(dias_fuerza, dias_cardio, minutos_sesion, objetivo)

    with st.spinner("Generando tu menú..."):
        st.session_state["menu"] = generate_menu(cal["calorias_objetivo"], macros, comidas_por_dia, preferencias)

    with st.spinner("Generando lista de compras..."):
        st.session_state["lista_compras"] = generate_shopping_list(st.session_state["menu"])

    st.session_state["plan_generado"] = True


if st.session_state.get("plan_generado"):
    calculos = st.session_state["calculos"]
    timeline = st.session_state["timeline"]
    goal_check = st.session_state["goal_check"]

    st.divider()

    if calculos["ajustado_por_piso"]:
        st.warning(
            "⚠️ Para mantener un enfoque más seguro, se ajustó automáticamente "
            "el objetivo calórico a un mínimo saludable."
        )

    st.subheader("📊 Tus números")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Calorías objetivo", f"{calculos['calorias_objetivo']} kcal")
    m2.metric("Proteínas", f"{calculos['macros']['proteina_g']} g")
    m3.metric("Carbohidratos", f"{calculos['macros']['carbohidratos_g']} g")
    m4.metric("Grasas", f"{calculos['macros']['grasas_g']} g")

    if calculos["masa_magra"]:
        st.caption(f"💪 Masa magra estimada: {calculos['masa_magra']} kg "
                   f"(la proteína se calculó en base a esto, no al peso total)")

    if goal_check:
        if goal_check["realista"]:
            st.success(goal_check["mensaje"])
        else:
            st.error(goal_check["mensaje"])
    elif timeline and timeline["semanas_estimadas"]:
        st.info(f"📈 {timeline['mensaje']}")

    tab_rutina, tab_menu, tab_compras = st.tabs(["🏋️ Rutina", "🍽️ Menú", "🛒 Lista de compras"])

    with tab_rutina:
        for dia, info in st.session_state["rutina"].items():
            with st.expander(dia.capitalize()):
                st.write(f"**Tipo:** {info.get('tipo', '')}")
                if info.get("grupo_muscular"):
                    st.write(f"**Grupo muscular:** {info['grupo_muscular']}")
                for ej in info.get("ejercicios", []):
                    st.write(f"- {ej}")
                if info.get("cardio_min"):
                    st.write(f"🏃 Cardio: {info['cardio_min']} min")

    with tab_menu:
        for dia, comidas in st.session_state["menu"].items():
            with st.expander(dia.capitalize()):
                for momento, detalle in comidas.items():
                    st.write(f"**{momento.capitalize()}:** {detalle}")

    with tab_compras:
        for categoria, items in st.session_state["lista_compras"].items():

            st.subheader(categoria.replace("_", " ").title())

            for item in items:
                st.markdown(f"• {item}")

    st.divider()
    pdf_bytes = export_to_pdf(
        calculos, st.session_state["rutina"], st.session_state["menu"], st.session_state["lista_compras"]
    )
    st.download_button("📄 Descargar plan en PDF", data=pdf_bytes, file_name="fitpilot_plan.pdf", mime="application/pdf")

st.divider()
st.caption("🚀 Automation Lab — Project #5: FitPilot")