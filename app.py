import re
import time
import requests
import streamlit as st
from datetime import datetime
from urllib.parse import urlparse
from st_keyup import st_keyup


st.set_page_config(
    page_title="People FINDER :)",
    page_icon="🔎",
    layout="centered"
)


# -----------------------------
# Basic style
# -----------------------------
st.markdown(
    """
    <style>
    .main {
        background-color: #f7f8fa;
    }

    .title-box {
        text-align: center;
        padding: 35px 15px 15px 15px;
    }

    .title {
        font-size: 42px;
        font-weight: 800;
        color: #111827;
        letter-spacing: -1px;
    }

    .subtitle {
        font-size: 15px;
        color: #6b7280;
        margin-top: 8px;
    }

    .info-box {
        background: white;
        padding: 18px;
        border-radius: 16px;
        border: 1px solid #e5e7eb;
        margin-top: 20px;
    }

    .result-card {
        background: white;
        padding: 16px;
        border-radius: 14px;
        border: 1px solid #e5e7eb;
        margin-bottom: 12px;
    }

    .small-muted {
        font-size: 13px;
        color: #6b7280;
    }

    div[data-testid="stTextInput"] input {
        border-radius: 14px;
        padding: 16px;
        font-size: 18px;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# -----------------------------
# Helpers
# -----------------------------
def is_valid_email(email: str) -> bool:
    pattern = r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def extract_domain(email: str) -> str:
    return email.split("@")[-1].lower().strip()


def extract_username(email: str) -> str:
    return email.split("@")[0].lower().strip()


def domain_name_from_url(url: str) -> str:
    try:
        netloc = urlparse(url).netloc
        return netloc.replace("www.", "")
    except Exception:
        return ""


def build_queries(email: str):
    username = extract_username(email)
    domain = extract_domain(email)
    company = domain.split(".")[0]

    queries = [
        f'"{email}"',
        f'"{username}" "{domain}"',
        f'"{username}" "{company}"',
        f'"{email}" LinkedIn',
        f'"{email}" company',
        f'"{email}" contact',
        f'"{username}" "{domain}" LinkedIn',
        f'"{username}" "{domain}" profile',
        f'"{username}" "{company}" profile',
        f'"{username}" "{company}" email',
    ]

    return queries


@st.cache_data(ttl=3600, show_spinner=False)
def brave_search(query: str, api_key: str, count: int = 8):
    url = "https://api.search.brave.com/res/v1/web/search"

    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key
    }

    params = {
        "q": query,
        "count": count,
        "safesearch": "moderate",
        "freshness": "py"
    }

    response = requests.get(url, headers=headers, params=params, timeout=20)

    if response.status_code != 200:
        raise Exception(f"Brave API error {response.status_code}: {response.text}")

    data = response.json()
    results = data.get("web", {}).get("results", [])

    cleaned_results = []

    for item in results:
        title = clean_text(item.get("title", ""))
        url = item.get("url", "")
        description = clean_text(item.get("description", ""))

        if not url:
            continue

        cleaned_results.append({
            "query": query,
            "title": title,
            "url": url,
            "source": domain_name_from_url(url),
            "description": description
        })

    return cleaned_results


def deduplicate_results(results):
    seen = set()
    unique = []

    for item in results:
        url = item.get("url", "").strip().lower()

        if not url or url in seen:
            continue

        seen.add(url)
        unique.append(item)

    return unique


def calculate_confidence(email: str, results):
    email_lower = email.lower()
    username = extract_username(email)
    domain = extract_domain(email)

    score = 0

    for item in results:
        text = f"{item.get('title', '')} {item.get('description', '')} {item.get('url', '')}".lower()

        if email_lower in text:
            score += 3
        if username in text:
            score += 1
        if domain in text:
            score += 1

    if score >= 10:
        return "Alta"
    elif score >= 5:
        return "Media"
    elif score >= 1:
        return "Baja"
    else:
        return "Sin coincidencias claras"


def generate_report(email: str, results):
    domain = extract_domain(email)
    username = extract_username(email)
    confidence = calculate_confidence(email, results)

    lines = []
    lines.append("PEOPLE FINDER :)")
    lines.append("Reporte de información pública")
    lines.append("")
    lines.append(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Correo analizado: {email}")
    lines.append(f"Usuario detectado: {username}")
    lines.append(f"Dominio detectado: {domain}")
    lines.append(f"Nivel de confianza general: {confidence}")
    lines.append("")
    lines.append("Nota importante:")
    lines.append("Este reporte solo incluye información pública encontrada en resultados web.")
    lines.append("Las coincidencias pueden no pertenecer a la misma persona.")
    lines.append("No debe usarse para acoso, doxxing, extracción de datos privados o fines no autorizados.")
    lines.append("")
    lines.append("Resultados encontrados:")
    lines.append("")

    if not results:
        lines.append("No se encontraron resultados públicos claros.")
    else:
        for index, item in enumerate(results, start=1):
            lines.append(f"{index}. {item.get('title', 'Sin título')}")
            lines.append(f"Fuente: {item.get('source', '')}")
            lines.append(f"URL: {item.get('url', '')}")
            lines.append(f"Descripción: {item.get('description', '')}")
            lines.append(f"Consulta usada: {item.get('query', '')}")
            lines.append("")

    return "\n".join(lines)


def run_people_search(email: str, api_key: str):
    all_results = []
    queries = build_queries(email)

    for query in queries:
        try:
            results = brave_search(query, api_key, count=8)
            all_results.extend(results)
            time.sleep(0.2)
        except Exception as error:
            st.warning(f"No se pudo completar una búsqueda: {query}")

    unique_results = deduplicate_results(all_results)

    return unique_results


# -----------------------------
# UI
# -----------------------------
st.markdown(
    """
    <div class="title-box">
        <div class="title">People FINDER :)</div>
        <div class="subtitle">Busca coincidencias públicas usando un correo electrónico.</div>
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <div class="info-box">
        <b>Uso recomendado:</b> validación profesional, investigación comercial básica o revisión de información pública.
        <br>
        <span class="small-muted">
        No busca datos privados, filtraciones, contraseñas, direcciones personales ni información sensible.
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

email = st_keyup(
    "Correo",
    value="",
    placeholder="ejemplo@empresa.com",
    debounce=900,
    key="email_input",
    label_visibility="collapsed"
)

api_key = st.secrets.get("BRAVE_API_KEY", "")

if email:
    email = email.strip().lower()

    if not is_valid_email(email):
        st.info("Escribe un correo válido para iniciar la búsqueda automática.")
    else:
        if not api_key:
            st.error("Falta configurar BRAVE_API_KEY en .streamlit/secrets.toml")
        else:
            with st.spinner("Buscando información pública..."):
                results = run_people_search(email, api_key)

            confidence = calculate_confidence(email, results)
            report = generate_report(email, results)

            st.markdown("### Resumen")
            st.write(f"**Correo analizado:** {email}")
            st.write(f"**Dominio:** {extract_domain(email)}")
            st.write(f"**Resultados únicos encontrados:** {len(results)}")
            st.write(f"**Nivel de confianza:** {confidence}")

            st.download_button(
                label="Descargar reporte TXT",
                data=report,
                file_name=f"people_finder_{email.replace('@', '_at_')}.txt",
                mime="text/plain"
            )

            st.markdown("### Resultados encontrados")

            if not results:
                st.warning("No se encontraron resultados públicos claros.")
            else:
                for item in results[:25]:
                    st.markdown(
                        f"""
                        <div class="result-card">
                            <b>{item.get("title", "Sin título")}</b><br>
                            <span class="small-muted">{item.get("source", "")}</span><br><br>
                            {item.get("description", "")}<br><br>
                            <a href="{item.get("url", "")}" target="_blank">Abrir fuente</a>
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
else:
    st.caption("Empieza escribiendo un correo. La búsqueda se activará automáticamente cuando el formato sea válido.")
