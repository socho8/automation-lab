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
import shutil
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

def format_size(num_bytes: int) -> str:
    """Convierte bytes a un formato legible."""
    for unit in ("B", "KB", "MB", "GB"):
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.2f} TB"

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
    Convierte un archivo DOCX a PDF utilizando LibreOffice.

    Si LibreOffice no está instalado, informa al usuario de forma clara.
    """

    soffice = shutil.which("soffice")

    if soffice is None:
        possible_paths = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]

        for path in possible_paths:
            if Path(path).exists():
                soffice = path
                break

    if soffice is None:
        raise RuntimeError(
            "LibreOffice no está instalado.\n\n"
            "Instálalo desde https://www.libreoffice.org para habilitar la conversión DOCX → PDF."
        )

    with tempfile.TemporaryDirectory() as tmpdir:

        input_docx = Path(tmpdir) / "input.docx"
        input_docx.write_bytes(file_bytes)

        result = subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                tmpdir,
                str(input_docx),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        output_pdf = Path(tmpdir) / "input.pdf"

        if not output_pdf.exists():
            raise RuntimeError(
                result.stderr if result.stderr else "No se pudo convertir el archivo."
            )

        return output_pdf.read_bytes()


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


def run_conversion(file_bytes: bytes, source_ext: str, target_label: str):
    if source_ext in ("png", "jpg", "jpeg") and target_label in ("PNG", "JPG"):
        target_format = "PNG" if target_label == "PNG" else "JPEG"
        result = convert_image(file_bytes, target_format)
        ext_out = "png" if target_format == "PNG" else "jpg"

        return result, f"convertido.{ext_out}", f"image/{ext_out}"

    if source_ext == "csv" and target_label == "Excel (.xlsx)":
        result = csv_to_excel(file_bytes)
        return (
            result,
            "convertido.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    if source_ext == "xlsx" and target_label == "CSV":
        result = excel_to_csv(file_bytes)
        return result, "convertido.csv", "text/csv"

    if source_ext == "docx" and target_label == "PDF":
        result = docx_to_pdf(file_bytes)
        return result, "convertido.pdf", "application/pdf"

    raise ValueError("Conversión no soportada.")

# ── Interfaz ───────────────────────────────────────────────────────────

st.title("📂 Universal File Converter")
st.caption("Automation Lab #3 — Convertí imágenes y documentos desde tu navegador.")
with st.sidebar:
    st.header("📦 Conversiones")

    st.write("🖼 PNG → JPG")
    st.write("🖼 JPG → PNG")
    st.write("📄 CSV → Excel")
    st.write("📄 Excel → CSV")
    st.write("📄 DOCX → PDF")

uploaded_file = st.file_uploader(
    "Arrastrá un archivo o hacé clic para elegirlo",
    type=list(CONVERSIONS.keys()),
)

if uploaded_file is not None:
    source_ext = get_file_extension(uploaded_file.name)
    file_bytes = uploaded_file.read()

    st.write(f"**Archivo:** {uploaded_file.name} ({source_ext.upper()})")

    available_targets = CONVERSIONS.get(source_ext, [])
    
    if source_ext == "docx":
        st.info(
            "ℹ️ La conversión DOCX → PDF requiere LibreOffice instalado."
        )

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

                    original_size = len(file_bytes)
                    converted_size = len(result_bytes)

                    difference = original_size - converted_size

                    percentage = (difference / original_size) * 100 if original_size else 0

                    col1, col2 = st.columns(2)

                    with col1:
                        st.metric("📁 Archivo original", format_size(original_size))

                    with col2:
                        st.metric("📁 Archivo convertido", format_size(converted_size))

                    if difference > 0:
                        st.success(
                            f"📉 Se redujo el tamaño en {percentage:.1f}% "
                            f"({format_size(difference)} menos)"
                        )
                    elif difference < 0:
                        st.info(
                            f"📈 El archivo aumentó un {abs(percentage):.1f}% "
                            f"({format_size(abs(difference))} más)"
                        )
                    else:
                        st.info("El tamaño del archivo no cambió.")

                    st.subheader("🖼 Vista previa")

                    st.image(result_bytes, use_container_width=True)
                elif target == "Excel (.xlsx)":
                    st.dataframe(pd.read_excel(io.BytesIO(result_bytes)))
                elif target == "CSV":
                    st.dataframe(pd.read_csv(io.BytesIO(result_bytes)))

            except RuntimeError as e:
                st.warning(str(e))

            except Exception as e:
                st.error(f"Error inesperado: {e}")
else:
    st.info("Subí un archivo PNG, JPG, CSV, XLSX o DOCX para empezar.")

st.divider()
st.caption("🚀 Automation Lab — Project #3")
st.caption("🔗 github.com/socho8/automation-lab")