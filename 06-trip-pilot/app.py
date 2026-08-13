"""
TripPilot — Automation Lab Project #8
----------------------------------------
Planificá un viaje: presupuesto inteligente calculado con datos reales,
validación de factibilidad, itinerario generado con IA, y export a PDF.

Requiere: streamlit, groq, requests, plotly, fpdf2
"""

import json

from pdf import PDFBuilder
import plotly.graph_objects as go
import streamlit as st
from groq import Groq

from calculations import (
    list_countries, calculate_budget_breakdown, calculate_daily_budget,
    validate_budget_feasibility, what_can_i_do_with_budget,
)

st.set_page_config(page_title="TripPilot", page_icon="🌍", layout="wide")

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
        temperature=0.6,
        **kwargs,
    )
    return response.choices[0].message.content


# ── Generador de itinerario (recibe SOLO números ya calculados) ─────────

def generate_itinerary(pais: str, ciudad: str, dias: int, preferencias: list[str],
                        tipo_viaje: str, presupuesto_diario: dict) -> dict:
    ciudad_texto = ciudad if ciudad else pais
    prefs_texto = ", ".join(preferencias) if preferencias else "sin preferencias particulares"

    prompt = f"""
    Armá un itinerario de viaje de {dias} días para {ciudad_texto}, {pais}.
    Tipo de viaje: {tipo_viaje}.
    Intereses del viajero: {prefs_texto}.

    Presupuesto DIARIO ya calculado (respetalo, no lo cambies):
    {json.dumps(presupuesto_diario, ensure_ascii=False)}

    Para cada día, armá una lista de actividades con horario aproximado
    (mañana, mediodía, tarde, noche), acorde a los intereses indicados
    y realista para el presupuesto diario dado.

    Respondé ÚNICAMENTE con este JSON:
    {{"itinerario": {{
        "dia_1": [
            {{"hora": "09:00", "actividad": "..."}},
            {{"hora": "13:00", "actividad": "..."}}
        ],
        "dia_2": [...]
    }}}}
    Generá exactamente {dias} días (dia_1 a dia_{dias}).
    """
    return json.loads(ask_llm(prompt))["itinerario"]


# ── Gráfico de torta del presupuesto ──────────────────────────────────

def render_budget_pie_chart(breakdown: dict, moneda: str):
    labels = [cat.capitalize() for cat in breakdown.keys()]
    values = list(breakdown.values())

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,
        textinfo="label+percent",
        hovertemplate="%{label}: %{value} " + moneda + "<extra></extra>",
    )])
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=380)
    st.plotly_chart(fig, use_container_width=True)


# ── Exportar a PDF ─────────────────────────────────────────────────────

def export_to_pdf(destino, dias, breakdown, moneda, itinerario):

    pdf = PDFBuilder("TripPilot")

    pdf.heading("Resumen del viaje")

    pdf.paragraph(f"Destino: {destino}")
    pdf.paragraph(f"Duración: {dias} días")

    pdf.heading("Presupuesto")

    for categoria, monto in breakdown.items():
        pdf.paragraph(f"{categoria.capitalize()}: {monto} {moneda}")

    pdf.heading("Itinerario")

    for dia, actividades in itinerario.items():

        pdf.heading(dia.replace("_", " ").capitalize())

        for act in actividades:
            pdf.paragraph(
                f"{act['hora']} - {act['actividad']}"
            )

    return pdf.build()

# ── Interfaz ─────────────────────────────────────────────────────────────

st.title("🌍 TripPilot")
st.caption("Planificá un viaje completo: presupuesto validado con datos reales + itinerario con IA.")
st.caption("Datos de costo de vida: [WhereNext](https://getwherenext.com/data/cost-of-living-2026) (CC BY 4.0)")

with st.form("trip_form"):
    st.subheader("1️⃣ Datos del viaje")
    c1, c2 = st.columns(2)
    with c1:
        pais = st.selectbox("País de destino", list_countries())
        ciudad = st.text_input("Ciudad (opcional, no afecta el cálculo)", "")
        ciudad_salida = st.text_input("Ciudad de salida", "")
    with c2:
        fecha_salida = st.date_input("Fecha de salida")
        fecha_regreso = st.date_input("Fecha de regreso")
        personas = st.number_input("Personas", 1, 20, 1)

    c3, c4 = st.columns(2)
    with c3:
        presupuesto_total = st.number_input("Presupuesto total", min_value=0.0, value=1000.0)
    with c4:
        moneda = st.selectbox("Moneda", ["EUR", "USD", "GBP", "ARS", "MXN"])

    tipo_viaje = st.selectbox("Tipo de viaje", ["mochilero", "economico", "estandar", "premium"])

    st.subheader("2️⃣ Preferencias")
    preferencias = st.multiselect(
        "¿Qué te interesa?",
        ["Museos", "Naturaleza", "Vida nocturna", "Gastronomía", "Deportes", "Compras", "Lugares históricos", "Playa"],
    )

    submitted = st.form_submit_button("🚀 Generar plan de viaje")

if submitted:
    dias = (fecha_regreso - fecha_salida).days

    if dias <= 0:
        st.error("❌ La fecha de regreso debe ser posterior a la fecha de salida.")
        st.stop()

    # ── Paso 3: presupuesto inteligente (Python puro) ──
    breakdown = calculate_budget_breakdown(presupuesto_total, tipo_viaje)
    diario = calculate_daily_budget(presupuesto_total, dias, tipo_viaje)

    # ── Validación de factibilidad (Python + dataset real) ──
    factibilidad = validate_budget_feasibility(presupuesto_total, moneda, dias, personas, pais, tipo_viaje)

    # ── "¿Qué puedo hacer con X?" ──
    sugerencia = what_can_i_do_with_budget(presupuesto_total, moneda, dias, personas, pais)

    st.session_state["dias"] = dias
    st.session_state["breakdown"] = breakdown
    st.session_state["diario"] = diario
    st.session_state["factibilidad"] = factibilidad
    st.session_state["sugerencia"] = sugerencia
    st.session_state["pais"] = pais
    st.session_state["ciudad"] = ciudad
    st.session_state["moneda"] = moneda

    # ── Itinerario con IA, usando el presupuesto diario ya calculado ──
    with st.spinner("Generando tu itinerario..."):
        st.session_state["itinerario"] = generate_itinerary(
            pais, ciudad, dias, preferencias, tipo_viaje, diario["desglose_por_dia"]
        )

    st.session_state["plan_generado"] = True


if st.session_state.get("plan_generado"):
    dias = st.session_state["dias"]
    breakdown = st.session_state["breakdown"]
    diario = st.session_state["diario"]
    factibilidad = st.session_state["factibilidad"]
    sugerencia = st.session_state["sugerencia"]
    pais = st.session_state["pais"]
    ciudad = st.session_state["ciudad"]
    moneda = st.session_state["moneda"]

    st.divider()

    if factibilidad["nivel"]:
        if factibilidad["nivel"] == "🔴":
            st.error(factibilidad["mensaje"])
        elif factibilidad["nivel"] == "🟡":
            st.warning(factibilidad["mensaje"])
        else:
            st.success(factibilidad["mensaje"])
    else:
        st.info(factibilidad["mensaje"])

    if sugerencia.get("mensaje"):
        st.info(f"💡 {sugerencia['mensaje']}")

    tab_presupuesto, tab_itinerario = st.tabs(["💰 Presupuesto", "🗺️ Itinerario"])

    with tab_presupuesto:
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader(f"Reparto total ({moneda})")
            for cat, monto in breakdown.items():
                st.write(f"**{cat.capitalize()}:** {monto} {moneda}")
            st.metric("Por día", f"{diario['presupuesto_por_dia_total']} {moneda}")
        with col2:
            render_budget_pie_chart(breakdown, moneda)

        st.subheader("Desglose diario")
        st.json(diario["desglose_por_dia"])

    with tab_itinerario:
        for dia, actividades in st.session_state["itinerario"].items():
            with st.expander(dia.replace("_", " ").capitalize()):
                for act in actividades:
                    st.write(f"**{act['hora']}** — {act['actividad']}")

    pdf_bytes = export_to_pdf(f"{ciudad}, {pais}" if ciudad else pais,
    dias,
    breakdown,
    moneda,
    st.session_state["itinerario"],
                )

    st.download_button(
    "📄 Descargar PDF",
    pdf_bytes,
    "trip_pilot_plan.pdf",
    mime="application/pdf",
                )

st.divider()
st.caption("🚀 Automation Lab — Project #6: TripPilot")
