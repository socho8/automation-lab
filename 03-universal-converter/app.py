"""
Universal File Converter
--------------------------
Interfaz web (Streamlit) para convertir archivos entre formatos comunes:
- PNG <-> JPG
- CSV <-> Excel
- DOCX -> PDF

Uso local:
    streamlit run app.py

Requiere: streamlit, pillow, pandas, openpyxl (ver requirements.txt)
Requiere además LibreOffice instalado en el sistema (para DOCX -> PDF).
"""

import io
import subprocess
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

st.set_page_config(page_title="Universal File Converter", page_icon="🔄")


# ── Lógica de conversión ──────────────────────────────────────────────

def convert_image(file_bytes: bytes, target_format: str) -> bytes:
    """Convierte una imagen entre formatos (PNG, JPG, etc.)."""
    image = Image.open(io.BytesIO(file_bytes))
    if target_format.upper() == "JPEG" and image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    output = io.BytesIO()
    image.save(output, format=target_format.upper())
    return output.getvalue()


def csv_to_excel(file_bytes: bytes) -> bytes:
    """Convierte CSV a Excel (.xlsx)."""
    df = pd.read_csv(io.BytesIO(file_bytes))
    output = io.BytesIO()
    df.to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def excel_to_csv(file_bytes: bytes) -> bytes:
    """Convierte Excel (.xlsx) a CSV."""
    df = pd.read_excel(io.BytesIO(file_bytes))
    output = io.BytesIO()
    df.to_csv(output, index=False)
    return output.getvalue()


def docx_to_pdf(file_bytes: bytes) -> bytes:
    """
    Convierte DOCX a PDF usando LibreOffice en modo headless.
    Requiere que LibreOffice esté instalado en el sistema (comando `soffice`).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_docx = Path(tmpdir) / "input.docx"
        tmp_docx.write_bytes(file_bytes)

        result = subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf",
             "--outdir", tmpdir, str(tmp_docx)],
            capture_output=True,
            timeout=60,
        )

        tmp_pdf = Path(tmpdir) / "input.pdf"
        if not tmp_pdf.exists():
            error_msg = result.stderr.decode(errors="ignore")
            raise RuntimeError(
                "No se pudo convertir el archivo. "
                "Verificá que LibreOffice esté instalado. "
                f"Detalle: {error_msg}"
            )
        return tmp_pdf.read_bytes()


# ── Configuración de conversiones disponibles ─────────────────────────

CONVERSIONS = {
    "png": ["JPG"],
    "jpg": ["PNG"],
    "jpeg": ["PNG"],
    "csv": ["Excel (.xlsx)"],
    "xlsx": ["CSV"],
    "docx": ["PDF"],
}


def get_file_extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower()


def run_conversion(file_bytes: bytes, source_ext: str, target_label: str) -> tuple[bytes, str, str]:
    """
    Ejecuta la conversión correspondiente.
    Devuelve (bytes_resultado, nombre_archivo_salida, mime_type).
    """
    if source_ext in ("png", "jpg", "jpeg") and target_label in ("PNG", "JPG"):
        target_format = "PNG" if target_label == "PNG" else "JPEG"
        result = convert_image(file_bytes, target_format)
        ext_out = "png" if target_format == "PNG" else "jpg"
        return result, f"convertido.{ext_out}", f"image/{ext_out}"

    if source_ext == "csv" and target_label == "Excel (.xlsx)":
        result = csv_to_excel(file_bytes)
        return result, "convertido.xlsx", (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    if source_ext == "xlsx" and target_label == "CSV":
        result = excel_to_csv(file_bytes)
        return result, "convertido.csv", "text/csv"

    if source_ext == "docx" and target_label == "PDF":
        result = docx_to_pdf(file_bytes)
        return result, "convertido.pdf", "application/pdf"

    raise ValueError("Conversión no soportada.")


# ── Interfaz ───────────────────────────────────────────────────────────

st.title("🔄 Universal File Converter")
st.caption("Parte de Automation Lab — convertí archivos sin instalar nada.")

uploaded_file = st.file_uploader(
    "Arrastrá un archivo o hacé clic para elegirlo",
    type=list(CONVERSIONS.keys()),
)

if uploaded_file is not None:
    source_ext = get_file_extension(uploaded_file.name)
    file_bytes = uploaded_file.read()

    st.write(f"**Archivo:** {uploaded_file.name} ({source_ext.upper()})")

    available_targets = CONVERSIONS.get(source_ext, [])

    if not available_targets:
        st.error(f"No hay conversiones disponibles para archivos .{source_ext}")
    else:
        target = st.selectbox("Convertir a:", available_targets)

        if st.button("Convertir"):
            try:
                with st.spinner("Convirtiendo..."):
                    result_bytes, output_name, mime = run_conversion(
                        file_bytes, source_ext, target
                    )
                st.success("✅ Conversión completada.")
                st.download_button(
                    label=f"⬇️ Descargar {output_name}",
                    data=result_bytes,
                    file_name=output_name,
                    mime=mime,
                )

                if source_ext in ("png", "jpg", "jpeg") and target in ("PNG", "JPG"):
                    st.image(result_bytes, caption="Vista previa del resultado")
                elif target == "Excel (.xlsx)":
                    st.dataframe(pd.read_excel(io.BytesIO(result_bytes)))
                elif target == "CSV":
                    st.dataframe(pd.read_csv(io.BytesIO(result_bytes)))

            except Exception as e:
                st.error(f"Ocurrió un error al convertir: {e}")
else:
    st.info("Subí un archivo PNG, JPG, CSV, XLSX o DOCX para empezar.")

st.divider()
st.caption("🚀 Automation Lab — Project #4")