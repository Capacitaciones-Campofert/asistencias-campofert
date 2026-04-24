import streamlit as st
import pandas as pd
import os
import io
import threading
import pytz
from datetime import datetime
from io import BytesIO
from streamlit_drawable_canvas import st_canvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image
from streamlit_gsheets import GSheetsConnection
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# =============================================================================
# CONFIG
# =============================================================================

st.set_page_config(
    page_title="Campofert Enterprise",
    layout="centered",
    page_icon="🌱",
    initial_sidebar_state="collapsed"
)

conn = st.connection("gsheets", type=GSheetsConnection)

EMAIL_USER = "gestionhumanacpfert@gmail.com"
EMAIL_PASS = st.secrets.get("email_password", "xxxxx")

# =============================================================================
# CACHE LAYER (CRÍTICO PARA ESCALA)
# =============================================================================

@st.cache_data(ttl=3600)
def get_empleados():
    if os.path.exists("empleados.xlsx"):
        df = pd.read_excel("empleados.xlsx", engine="openpyxl", dtype={"ID": str})
        df.columns = df.columns.str.strip()
        return df
    return pd.DataFrame()


@st.cache_data(ttl=10)
def get_registros():
    try:
        return conn.read(worksheet="Hoja", ttl=0)
    except:
        return pd.DataFrame()

# =============================================================================
# BACKGROUND QUEUE (EMAIL + PROCESOS PESADOS)
# =============================================================================

def send_email(data, pdf_buffer):

    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_USER
        msg['Subject'] = f"Asistencia {data['Nombre']}"

        body = f"""
        <h3>Registro exitoso</h3>
        <p><b>Nombre:</b> {data['Nombre']}</p>
        <p><b>ID:</b> {data['ID']}</p>
        <p><b>Tema:</b> {data['Tema']}</p>
        """

        msg.attach(MIMEText(body, 'html'))

        pdf_buffer.seek(0)
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_buffer.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename=cert.pdf')

        msg.attach(part)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_USER, msg.as_string())
        server.quit()

    except Exception as e:
        print("EMAIL ERROR:", e)


def async_email(data, pdf):
    threading.Thread(
        target=send_email,
        args=(data, pdf),
        daemon=True
    ).start()

# =============================================================================
# SHEETS WRITER OPTIMIZADO (ANTI COLAPSO)
# =============================================================================

def save_to_sheets(data):

    try:
        new_row = pd.DataFrame([{
            "Fecha": data['Fecha'],
            "ID": data['ID'],
            "Nombre": data['Nombre'],
            "Empresa": data['Empresa'],
            "Cargo": data.get('Cargo', ''),
            "Tema": data['Tema']
        }])

        df_old = get_registros()

        df_final = pd.concat([df_old, new_row], ignore_index=True)

        conn.update(worksheet="Hoja", data=df_final)

        get_registros.clear()

        return True

    except Exception as e:
        st.error(e)
        return False

# =============================================================================
# DATA
# =============================================================================

df_emp = get_empleados()

# =============================================================================
# TEMA GLOBAL
# =============================================================================

params = st.query_params
tema_actual = params.get("tema", "CAPACITACIÓN GENERAL").replace("+", " ").upper()

# =============================================================================
# LOGIN SYSTEM
# =============================================================================

if "rol" not in st.session_state:

    st.title("🌱 Campofert Enterprise")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("👷 Colaborador", use_container_width=True):
            st.session_state.rol = "Empleado"
            st.rerun()

    with c2:
        if st.button("🛡️ Admin", use_container_width=True):
            st.session_state.admin_login = True
            st.rerun()

    # ================= ADMIN LOGIN =================
    if st.session_state.get("admin_login"):

        st.subheader("🔐 Acceso Admin")

        clave = st.text_input("Clave", type="password")

        if clave:

            if clave == "campofert2026":
                st.session_state.rol = "Admin"
                st.rerun()
            elif len(clave) > 0:
                st.error("Clave incorrecta")

    st.stop()

# =============================================================================
# EMPLEADO FLOW
# =============================================================================

if st.session_state.rol == "Empleado":

    st.subheader("📋 Registro Asistencia")
    st.info(f"Tema: {tema_actual}")

    if "step" not in st.session_state:
        st.session_state.step = 1

    if st.session_state.step == 1:

        ced = st.text_input("Cédula")

        if ced:

            user = df_emp[df_emp["ID"].astype(str) == ced]

            if not user.empty:
                st.session_state.user = user.iloc[0].to_dict()
                st.session_state.ced = ced

                if st.button("Continuar"):
                    st.session_state.step = 2
                    st.rerun()

    elif st.session_state.step == 2:

        photo = st.camera_input("Foto")

        if photo:
            st.session_state.photo = photo

            if st.button("Firma"):
                st.session_state.step = 3
                st.rerun()

    elif st.session_state.step == 3:

        firma = st_canvas(
            stroke_width=3,
            stroke_color="#1B5E20",
            background_color="#fff",
            height=180
        )

        if st.button("Finalizar"):

            data = {
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "ID": st.session_state.ced,
                "Nombre": st.session_state.user["Apellidos y Nombres"],
                "Empresa": st.session_state.user["Empresa"],
                "Cargo": st.session_state.user.get("Cargo", ""),
                "Tema": tema_actual
            }

            if save_to_sheets(data):

                pdf = BytesIO()
                pdf.write(b"PDF_CERTIFICADO_SIMPLIFICADO")
                pdf.seek(0)

                async_email(data, pdf)

                st.success("Registro exitoso")
                st.download_button("Descargar PDF", pdf, "certificado.pdf")

                st.session_state.step = 1

# =============================================================================
# ADMIN FULL SYSTEM
# =============================================================================

elif st.session_state.rol == "Admin":

    with st.sidebar:

        st.title("🛡️ Admin Panel")

        menu = st.radio(
            "Opciones",
            [
                "⚙️ Tema",
                "👥 Empleados",
                "📤 Cargar",
                "📊 Dashboard",
                "📄 Historial",
                "📁 Reportes"
            ]
        )

        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()

    # ================= MÓDULOS =================

    if menu == "👥 Empleados":
        st.dataframe(df_emp)

    elif menu == "📄 Historial":
        st.dataframe(get_registros())

    elif menu == "📊 Dashboard":

        df = get_registros()

        st.metric("Registros", len(df))
        st.metric("Personas", df["ID"].nunique() if not df.empty else 0)

    elif menu == "📁 Reportes":

        df = get_registros()

        st.download_button(
            "Descargar CSV",
            df.to_csv(index=False),
            "reporte.csv"
        )

# =============================================================================
# END SYSTEM
# =============================================================================
