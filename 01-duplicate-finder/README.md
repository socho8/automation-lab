# 🗂️ 01 - Duplicate Finder

Encuentra archivos duplicados en cualquier carpeta (y subcarpetas) comparando
el **contenido real** de los archivos, no el nombre. Así detecta duplicados
aunque se llamen distinto (`foto.jpg` y `foto_copia.jpg` con el mismo contenido
son detectados igual).

## 🧠 Cómo funciona

1. Recorre la carpeta de forma recursiva con `pathlib`.
2. Agrupa primero los archivos por **tamaño** (comparar tamaños es instantáneo).
3. Solo calcula el **hash SHA-256** (`hashlib`) de los archivos que comparten
   tamaño con al menos otro archivo — esto evita leer byte a byte archivos
   que ya sabemos que son únicos.
4. Si dos o más archivos tienen el mismo hash, son duplicados.
5. Calcula cuánto espacio se podría liberar.

## ⚙️ Requisitos

Solo librería estándar de Python (3.9+). No hace falta instalar nada:

```bash
python3 --version  # 3.9 o superior
```

## 🚀 Uso

**1. Reporte (modo seguro, no borra ni mueve nada):**
```bash
python app.py /ruta/a/tu/carpeta
```

**2. Mover duplicados a una carpeta de cuarentena** (`_duplicates_quarantine/`),
para revisarlos antes de decidir si los borrás:
```bash
python app.py /ruta/a/tu/carpeta --move-duplicates
```

**3. Borrado permanente** (pide confirmación explícita, usar con cuidado):
```bash
python app.py /ruta/a/tu/carpeta --delete
```

## 📋 Ejemplo de salida

```
🔍 Escaneando: /Users/tomas/Descargas

📁 Grupo 1 — 2.30 MB cada uno
   Original (más antiguo): /Users/tomas/Descargas/reporte.pdf
   Duplicado:              /Users/tomas/Descargas/reporte (1).pdf
   Duplicado:              /Users/tomas/Descargas/reporte_final.pdf

💾 Espacio recuperable si se eliminan los duplicados: 4.60 MB
```

## ⚠️ Nota de seguridad

Por defecto el script **nunca borra ni mueve nada** — solo informa. El modo
de borrado permanente (`--delete`) pide confirmación escribiendo "si" antes
de actuar, y siempre conserva el archivo más antiguo del grupo como "original".

## 💡 Posibles mejoras futuras

- Interfaz gráfica simple (drag & drop de carpeta).
- Excluir extensiones o carpetas específicas (`.git`, `node_modules`, etc.).
- Exportar el reporte a CSV/JSON.

---
📎 Parte de [Automation Lab](../README.md) — 30 días de automatizaciones con Python.