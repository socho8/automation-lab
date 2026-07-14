"""
Study Pilot — Automation Lab Project #6
------------------------------------------
Sube uno o varios PDF y genera: resumen por capítulo, flashcards,
quiz interactivo, ruta de estudio y cronograma — usando Groq (Llama 3.3 70B).

Requiere: streamlit, pymupdf, groq
"""

import json
import re

import fitz  # PyMuPDF
import streamlit as st
from groq import Groq

st.set_page_config(page_title="Study Pilot", page_icon="📚", layout="wide")

MODEL = "llama-3.3-70b-versatile"


# ── Extracción y chunking ──────────────────────────────────────────────

def extract_text(pdf_bytes: bytes) -> str:
    """Extrae todo el texto de un PDF usando PyMuPDF."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    doc.close()
    return text


def split_into_chapters(text: str) -> dict[str, str]:
    """
    Intenta dividir el texto por capítulos (busca patrones tipo
    'Capítulo 1', 'Chapter 1', 'CAPÍTULO I', etc.).
    Si no encuentra ninguno, devuelve todo como un solo bloque
    dividido en partes de tamaño manejable para el LLM.
    """
    pattern = re.compile(r"(cap[ií]tulo|chapter)\s+\w+", re.IGNORECASE)
    matches = list(pattern.finditer(text))

    if len(matches) < 2:
        # No hay estructura clara de capítulos -> partimos por tamaño
        chunk_size = 8000  # caracteres aprox., para no exceder el contexto
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        return {f"Parte {i+1}": chunk for i, chunk in enumerate(chunks)}

    chapters = {}
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        title = match.group().strip().title()
        chapters[f"{title} ({i+1})"] = text[start:end]

    return chapters


# ── Cliente de Groq ─────────────────────────────────────────────────────

def get_client() -> Groq:
    return Groq(api_key=st.secrets["GROQ_API_KEY"])


def ask_llm(prompt: str, json_mode: bool = False) -> str:
    """Llama al modelo de Groq con el prompt dado."""
    client = get_client()
    kwargs = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        **kwargs,
    )
    return response.choices[0].message.content


# ── Generadores de contenido ────────────────────────────────────────────

def generate_summary(chapters: dict[str, str]) -> dict[str, str]:
    """Genera un resumen estructurado por cada capítulo/parte."""
    summaries = {}
    for title, content in chapters.items():
        prompt = f"""
        Resumí el siguiente texto de forma estructurada, en español.
        Incluí: qué explica el capítulo, conceptos importantes,
        definiciones clave y ejemplos si los hay. Usá subtítulos claros.

        TEXTO:
        {content[:6000]}
        """
        summaries[title] = ask_llm(prompt)
    return summaries


def generate_flashcards(full_text: str, cantidad: int = 15) -> list[dict]:
    """Genera flashcards en formato JSON: [{'frente': ..., 'dorso': ...}]."""
    prompt = f"""
    Basándote en el siguiente texto, generá {cantidad} flashcards de estudio
    en español. Cada una con un "frente" (pregunta o concepto) y un "dorso"
    (respuesta o explicación breve).

    Respondé ÚNICAMENTE con un JSON con este formato exacto:
    {{"flashcards": [{{"frente": "...", "dorso": "..."}}]}}

    TEXTO:
    {full_text[:8000]}
    """
    raw = ask_llm(prompt, json_mode=True)
    return json.loads(raw)["flashcards"]


def generate_quiz(full_text: str, cantidad: int = 9) -> list[dict]:
    """
    Genera preguntas de quiz en 3 niveles de dificultad, con opciones
    y la respuesta correcta marcada.
    """
    prompt = f"""
    Basándote en el siguiente texto, generá {cantidad} preguntas de opción
    múltiple en español, distribuidas en partes iguales entre dificultad
    "facil", "intermedio" y "dificil". Cada pregunta con 4 opciones y
    una explicación breve de por qué la respuesta es correcta.

    Respondé ÚNICAMENTE con un JSON con este formato exacto:
    {{"preguntas": [
        {{"dificultad": "facil", "pregunta": "...",
          "opciones": ["...", "...", "...", "..."],
          "respuesta_correcta": 0,
          "explicacion": "..."}}
    ]}}
    El campo "respuesta_correcta" es el índice (0-3) de la opción correcta.

    TEXTO:
    {full_text[:8000]}
    """
    raw = ask_llm(prompt, json_mode=True)
    return json.loads(raw)["preguntas"]


def generate_study_path(full_text: str, tiempo_disponible: str) -> str:
    """Genera una ruta de estudio adaptada al tiempo disponible."""
    prompt = f"""
    Basándote en el siguiente texto, generá una ruta de estudio en español.
    Incluí: conocimientos previos recomendados, orden sugerido de estudio,
    y cuándo conviene hacer ejercicios o repasos.

    El estudiante tiene disponible: {tiempo_disponible}.
    Adaptá la profundidad y el ritmo sugerido a ese tiempo real
    (no es lo mismo preparar algo para mañana que para dentro de 2 semanas).

    TEXTO:
    {full_text[:8000]}
    """
    return ask_llm(prompt)


def generate_schedule(full_text: str, dias_disponibles: int) -> str:
    """Genera un cronograma día por día."""
    prompt = f"""
    Basándote en el siguiente texto, generá un cronograma de estudio
    distribuido en {dias_disponibles} días, día por día, en español.
    El último día debe ser de repaso general.

    TEXTO:
    {full_text[:8000]}
    """
    return ask_llm(prompt)


# ── Interfaz ─────────────────────────────────────────────────────────────

st.title("📚 Study Pilot")
st.caption("Subí tus apuntes, libros o diapositivas y generá tu material de estudio.")

uploaded_files = st.file_uploader(
    "Subí uno o varios PDF", type=["pdf"], accept_multiple_files=True
)

if uploaded_files:
    if "full_text" not in st.session_state or st.session_state.get("archivo_actual") != [f.name for f in uploaded_files]:
        with st.spinner("Extrayendo texto de los PDF..."):
            full_text = ""
            for f in uploaded_files:
                full_text += extract_text(f.read()) + "\n"
            st.session_state["full_text"] = full_text
            st.session_state["chapters"] = split_into_chapters(full_text)
            st.session_state["archivo_actual"] = [f.name for f in uploaded_files]
            # Reset de contenido generado al cambiar de archivo
            for key in ["summary", "flashcards", "quiz", "study_path", "schedule"]:
                st.session_state.pop(key, None)

    st.success(f"Texto extraído: {len(st.session_state['full_text'])} caracteres, "
               f"{len(st.session_state['chapters'])} secciones detectadas.")

    tab_resumen, tab_flashcards, tab_quiz, tab_ruta, tab_cronograma = st.tabs(
        ["📄 Resumen", "🧠 Flashcards", "❓ Quiz", "🗺️ Ruta de estudio", "📅 Cronograma"]
    )

    # ── Tab Resumen ──
    with tab_resumen:
        if st.button("Generar resumen"):
            with st.spinner("Generando resumen por capítulo..."):
                st.session_state["summary"] = generate_summary(st.session_state["chapters"])

        if "summary" in st.session_state:
            for titulo, resumen in st.session_state["summary"].items():
                with st.expander(titulo, expanded=False):
                    st.markdown(resumen)

    # ── Tab Flashcards ──
    with tab_flashcards:
        if st.button("Generar flashcards"):
            with st.spinner("Generando flashcards..."):
                st.session_state["flashcards"] = generate_flashcards(st.session_state["full_text"])

        if "flashcards" in st.session_state:
            for i, card in enumerate(st.session_state["flashcards"]):
                with st.expander(f"🎴 {card['frente']}"):
                    st.write(card["dorso"])

            # Exportar a CSV compatible con Anki
            import io
            import csv
            output = io.StringIO()
            writer = csv.writer(output, delimiter="\t")
            for card in st.session_state["flashcards"]:
                writer.writerow([card["frente"], card["dorso"]])
            st.download_button(
                "⬇️ Exportar para Anki (.txt, separado por tabs)",
                data=output.getvalue(),
                file_name="flashcards_anki.txt",
                mime="text/plain",
            )

    # ── Tab Quiz ──
    with tab_quiz:
        if st.button("Generar quiz"):
            with st.spinner("Generando preguntas..."):
                st.session_state["quiz"] = generate_quiz(st.session_state["full_text"])
                st.session_state["quiz_respuestas"] = {}

        if "quiz" in st.session_state:
            for i, q in enumerate(st.session_state["quiz"]):
                st.write(f"**[{q['dificultad'].upper()}] {q['pregunta']}**")
                respuesta = st.radio(
                    "Elegí una opción:", q["opciones"], key=f"quiz_{i}", index=None
                )
                if respuesta is not None:
                    elegida = q["opciones"].index(respuesta)
                    if elegida == q["respuesta_correcta"]:
                        st.success("✔ Correcto")
                    else:
                        st.error("✘ Incorrecto")
                    st.caption(q["explicacion"])
                st.divider()

    # ── Tab Ruta de estudio ──
    with tab_ruta:
        tiempo = st.selectbox("Tiempo disponible:", ["30 minutos", "1 hora", "2 horas", "1 día", "1 semana", "2 semanas"])
        if st.button("Generar ruta de estudio"):
            with st.spinner("Generando ruta de estudio..."):
                st.session_state["study_path"] = generate_study_path(st.session_state["full_text"], tiempo)

        if "study_path" in st.session_state:
            st.markdown(st.session_state["study_path"])

    # ── Tab Cronograma ──
    with tab_cronograma:
        dias = st.slider("¿Cuántos días tenés?", 1, 30, 7)
        if st.button("Generar cronograma"):
            with st.spinner("Generando cronograma..."):
                st.session_state["schedule"] = generate_schedule(st.session_state["full_text"], dias)

        if "schedule" in st.session_state:
            st.markdown(st.session_state["schedule"])

else:
    st.info("Subí al menos un PDF para empezar.")

st.divider()
st.caption("🚀 Automation Lab — Project #6: Study Pilot")