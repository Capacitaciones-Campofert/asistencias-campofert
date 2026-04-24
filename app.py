import streamlit as st
import pandas as pd
import os
import io
import pytz
import qrcode
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image
from streamlit_gsheets import GSheetsConnection

# =========================
# CONFIG RENDIMIENTO
# =========================
st.set_page_config(
    page_title="Campofert - Asistencia",
    layout="centered",
    page_icon="🌱",
    initial_sidebar_state="collapsed"
)

st.cache_data.clear()

# =========================
# CONEXIÓN SHEETS
# =========================
conn = st.connection("gsheets", type=GSheetsConnection)

# =========================
# CACHE EMPLEADOS (CLAVE)
# =========================
@st.cache_data(ttl=600)
def obtener_empleados():
    if os.path.exists("empleados.xlsx"):
        df = pd.read_excel("empleados.xlsx", dtype={"ID": str})
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame()

# =========================
# ESTADO GLOBAL
# =========================
if "rol" not in st.session_state:
    st.session_state.rol = None

if "tema" not in st.session_state:
    st.session_state.tema = "CAPACITACIÓN GENERAL"

# =========================
# LOGIN ADMIN (ENTER ENABLED)
# =========================
def login_admin():
    st.markdown("### 🔐 Acceso Admin")

    clave = st.text_input(
        "Clave",
        type="password",
        key="admin_key",
        on_change=None
    )

    if clave:
        if clave == "campofert2026":
            st.session_state.rol = "admin"
            st.rerun()
        else:
            st.error("Clave incorrecta")

# =========================
# LOGIN KIOSCO
# =========================
if st.session_state.rol is None:

    st.title("🌱 Campofert People")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("👷 COLABORADOR", use_container_width=True):
            st.session_state.rol = "empleado"
            st.rerun()

    with col2:
        if st.button("🛡️ ADMIN", use_container_width=True):
            login_admin()

    st.stop()

# =========================
# EMPLEADO FLOW
# =========================
if st.session_state.rol == "empleado":

    st.title("📋 Registro Asistencia")

    empleados = obtener_empleados()

    cedula = st.text_input("Cédula")

    persona = empleados[empleados["ID"] == cedula] if not empleados.empty else None

    if cedula and not persona.empty:

        datos = persona.iloc[0]

        st.success(f"Hola {datos['Apellidos y Nombres']}")

        foto = st.camera_input("Foto")

        firma = st_canvas(
            stroke_width=3,
            stroke_color="#1B5E20",
            background_color="#fff",
            height=160,
            width=300
        )

        if st.button("Finalizar"):

            datos_asistencia = {
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "ID": cedula,
                "Nombre": datos["Apellidos y Nombres"],
                "Empresa": datos["Empresa"],
                "Cargo": datos.get("Cargo", ""),
                "Tema": st.session_state.tema
            }

            df_exist = conn.read(worksheet="Hoja", ttl=0)
            df_new = pd.DataFrame([datos_asistencia])
            conn.update(worksheet="Hoja", data=pd.concat([df_exist, df_new]))

            st.success("Registro guardado")
            st.balloons()

    st.stop()

# =========================
# ADMIN PANEL (RESTO COMPLETO)
# =========================
if st.session_state.rol == "admin":

    st.sidebar.title("🛡️ ADMIN")

    menu = st.sidebar.radio("Menu", [
        "⚙️ Tema",
        "👥 Empleados",
        "📊 Dashboard",
        "📄 Historial",
        "📁 Reportes"
    ])

    # -------------------------
    if menu == "⚙️ Tema":
        nuevo = st.text_input("Tema capacitación")

        if st.button("Guardar"):
            st.session_state.tema = nuevo.upper()
            st.success("Actualizado")

    # -------------------------
    elif menu == "👥 Empleados":
        df = obtener_empleados()
        st.dataframe(df, use_container_width=True)

    # -------------------------
    elif menu == "📊 Dashboard":
        df = conn.read(worksheet="Hoja", ttl=0)
        st.metric("Registros", len(df))

    # -------------------------
    elif menu == "📄 Historial":
        df = conn.read(worksheet="Hoja", ttl=0)
        st.dataframe(df)

    # -------------------------
    elif menu == "📁 Reportes":
        df = conn.read(worksheet="Hoja", ttl=0)
        st.download_button("Descargar", df.to_csv(index=False))
