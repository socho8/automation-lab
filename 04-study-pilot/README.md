# 📚 Study Pilot

Transformá cualquier PDF en material de estudio utilizando Inteligencia Artificial.

Study Pilot permite subir uno o varios documentos PDF y generar automáticamente resúmenes, flashcards, preguntas tipo examen, rutas de estudio y cronogramas personalizados.

---

## ✨ Características

- 📄 Resumen estructurado por capítulos o secciones.
- 🧠 Flashcards listas para estudiar.
- ❓ Quiz interactivo con distintos niveles de dificultad.
- 🗺️ Ruta de estudio personalizada.
- 📅 Cronograma de estudio según los días disponibles.
- 📂 Soporte para uno o varios archivos PDF.
- 📥 Exportación de flashcards compatibles con Anki.

---

## 🛠 Tecnologías utilizadas

- Python
- Streamlit
- Groq API
- Llama 3.3 70B
- PyMuPDF
- JSON
- Regex

---

## 📖 ¿Cómo funciona?

1. Subí uno o varios archivos PDF.
2. El texto se extrae automáticamente utilizando PyMuPDF.
3. El contenido se divide en partes para optimizar el contexto del modelo.
4. Study Pilot genera:

- Resumen
- Flashcards
- Quiz
- Ruta de estudio
- Cronograma

5. Todo el contenido queda disponible desde una única interfaz.

---

## 📂 Estructura del proyecto

```
04-study-pilot/

├── app.py
├── requirements.txt
├── README.md
├── demo/
│   ├── AUTOMATION LAB 4.mp4
│ 
└── .streamlit/
```

---

## 💡 Próximas mejoras

- 🌳 Cuadros sinópticos.
- 🧩 Mapas conceptuales.
- 📄 Exportación a PDF.
- 🎤 Lectura por voz.
- 📊 Seguimiento del progreso.
- 🌐 Soporte para DOCX y PPTX.

---


📎 Parte de **Automation Lab** — 30 proyectos para aprender Python creando herramientas reales.