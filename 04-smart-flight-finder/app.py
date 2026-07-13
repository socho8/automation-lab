"""
Comparador de vuelos low-cost — Automation Lab Project #4
------------------------------------------------------------
Usa la API GraphQL de Travelpayouts (Aviasales) para comparar vuelos
por precio, duración y relación precio/tiempo.
"""

import requests
import streamlit as st
from datetime import date, datetime, timedelta

st.set_page_config(page_title="Comparador de Vuelos Low-Cost", page_icon="✈️")

BASE_URL = "https://api.travelpayouts.com/graphql/v1/query"


# ── Lógica de la API ───────────────────────────────────────────────────

def build_query(origin: str, destination: str, depart_month: str) -> str:
    """Arma la query GraphQL. No excluimos low-cost a propósito."""
    return f"""
    {{
      prices_one_way(
        params: {{
          origin: "{origin}"
          destination: "{destination}"
          depart_months: "{depart_month}"
        }}
        paging: {{ limit: 100, offset: 0 }}
        sorting: VALUE_ASC
      ) {{
        departure_at
        value
        trip_duration
        ticket_link
      }}
    }}
    """


def get_flights(origin: str, destination: str, depart_month: str, token: str) -> list[dict]:
    """Ejecuta la consulta y devuelve la lista cruda de vuelos."""
    query = build_query(origin, destination, depart_month)
    headers = {"Content-Type": "application/json", "X-Access-Token": token}
    response = requests.post(BASE_URL, json={"query": query}, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    if "errors" in data:
        raise RuntimeError(data["errors"])

    return data["data"]["prices_one_way"]


def parse_flight(raw: dict) -> dict:
    """Convierte un vuelo crudo en un diccionario limpio."""
    departure = datetime.fromisoformat(raw["departure_at"].replace("Z", "+00:00"))
    price = raw["value"]
    duration_minutes = raw["trip_duration"]
    horas, minutos = divmod(duration_minutes, 60)

    return {
        "fecha": departure.date(),
        "hora_salida": departure.strftime("%H:%M"),
        "precio": price,
        "duracion_minutos": duration_minutes,
        "duracion_texto": f"{horas}h {minutos}min",
        "link": f"https://www.aviasales.com/search/{raw['ticket_link']}",
        "precio_por_minuto": round(price / duration_minutes, 2) if duration_minutes else None,
    }


def find_best_options(flights: list[dict], target_date: date) -> dict:
    """Calcula el más barato, más rápido, mejor relación, y precios por día."""
    if not flights:
        return {}

    cheapest = min(flights, key=lambda f: f["precio"])
    fastest = min(flights, key=lambda f: f["duracion_minutos"])
    best_value = min(flights, key=lambda f: f["precio_por_minuto"])

    def cheapest_on(d):
        same_day = [f for f in flights if f["fecha"] == d]
        return min(same_day, key=lambda f: f["precio"]) if same_day else None

    return {
        "mas_barato": cheapest,
        "mas_rapido": fastest,
        "mejor_relacion": best_value,
        "dia_anterior": cheapest_on(target_date - timedelta(days=1)),
        "dia_objetivo": cheapest_on(target_date),
        "dia_siguiente": cheapest_on(target_date + timedelta(days=1)),
    }


# ── Interfaz ────────────────────────────────────────────────────────────

st.title("✈️ Comparador de Vuelos Low-Cost")
st.caption("Parte de Automation Lab — encontrá el mejor vuelo según precio, velocidad o ambos.")

token = st.secrets.get("TRAVELPAYOUTS_TOKEN", None)

if not token:
    st.warning("No se encontró el token en st.secrets. Pegalo acá solo para pruebas locales:")
    token = st.text_input("Token de Travelpayouts", type="password")

col1, col2 = st.columns(2)
with col1:
    origin = st.text_input("Origen (código IATA)", value="MAD", max_chars=3).upper()
with col2:
    destination = st.text_input("Destino (código IATA)", value="BCN", max_chars=3).upper()

target_date = st.date_input("Fecha de viaje", value=date.today() + timedelta(days=30))

if st.button("🔍 Buscar vuelos"):
    if not token:
        st.error("Necesitás un token para buscar vuelos.")
    else:
        depart_month = target_date.strftime("%Y-%m-01")
        try:
            with st.spinner("Buscando vuelos..."):
                raw_flights = get_flights(origin, destination, depart_month, token)
                flights = [parse_flight(f) for f in raw_flights]
                best = find_best_options(flights, target_date)

            if not best:
                st.info("No se encontraron vuelos para esa ruta y mes.")
            else:
                st.success(f"Se encontraron {len(flights)} vuelos.")

                st.subheader("🏆 Mejores opciones")
                c1, c2, c3 = st.columns(3)

                with c1:
                    st.metric("💰 Más barato", f"{best['mas_barato']['precio']} €")
                    st.caption(f"{best['mas_barato']['fecha']} — {best['mas_barato']['duracion_texto']}")
                    st.link_button("Ver vuelo", best['mas_barato']['link'])

                with c2:
                    st.metric("⚡ Más rápido", best['mas_rapido']['duracion_texto'])
                    st.caption(f"{best['mas_rapido']['fecha']} — {best['mas_rapido']['precio']} €")
                    st.link_button("Ver vuelo", best['mas_rapido']['link'])

                with c3:
                    st.metric("⚖️ Mejor relación", f"{best['mejor_relacion']['precio_por_minuto']} €/min")
                    st.caption(f"{best['mejor_relacion']['fecha']} — {best['mejor_relacion']['precio']} €")
                    st.link_button("Ver vuelo", best['mejor_relacion']['link'])

                st.divider()
                st.subheader("📅 Precio por día (± 1 día)")
                d1, d2, d3 = st.columns(3)

                for col, label, key in [
                    (d1, "Día anterior", "dia_anterior"),
                    (d2, "Día elegido", "dia_objetivo"),
                    (d3, "Día siguiente", "dia_siguiente"),
                ]:
                    with col:
                        flight = best[key]
                        st.write(f"**{label}**")
                        if flight:
                            st.write(f"{flight['fecha']} — {flight['precio']} €")
                            st.link_button("Ver vuelo", flight['link'])
                        else:
                            st.write("Sin datos")

        except requests.exceptions.HTTPError as e:
            st.error(f"Error de conexión con la API: {e}")
        except RuntimeError as e:
            st.error(f"Error de la API: {e}")
        except Exception as e:
            st.error(f"Ocurrió un error inesperado: {e}")

st.divider()
st.caption("🚀 Automation Lab — Project #5")