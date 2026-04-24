import streamlit as st
import pandas as pd
import os
import io
import pytz
import qrcode
from io import BytesIO
from datetime import datetime
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


# =========================================================
# ⚡ OPTIMIZACIÓN 1: SESSION STATE INICIALIZADO (EVITA ERRORES)
# =========================================================
if "init" not in st.session_state:
    st.session_state.init = True
    st.session_state.setdefault("paso", 1)

# =========================================================
# CONFIGURACIÓN
# =========================================================
st.set_page_config(page_title="Campofert - Registro de Asistencia",
                   layout="centered",
                   page_icon="🌱")

# =========================================================
# ⚡ OPTIMIZACIÓN 2: CACHE DE EXCEL (CRÍTICO)
# =========================================================
@st.cache_data(ttl=300)
def obtener_datos():
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, engine='openpyxl', dtype={'ID': str})
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            st.error(f"Error al leer empleados.xlsx: {e}")
    return pd.DataFrame()


# =========================================================
# CONEXIÓN GSHEETS (SIN CAMBIOS VISUALES)
# =========================================================
conn = st.connection("gsheets", type=GSheetsConnection)


# =========================================================
# TEMA (OPTIMIZADO - SIN REEJECUCIONES INNECESARIAS)
# =========================================================
params = st.query_params
tema_desde_url = params.get("tema") or params.get("Tema")

if tema_desde_url:
    st.session_state.tema_actual = tema_desde_url.replace("+", " ").upper()
elif "tema_actual" not in st.session_state:
    st.session_state.tema_actual = "CAPACITACIÓN GENERAL"

tema_actual = st.session_state.tema_actual
rol_url = params.get("rol")


# =========================================================
# ⚡ OPTIMIZACIÓN 3: GOOGLE SHEETS (MENOS CARGA)
# =========================================================
def guardar_en_google_sheets(datos):
    try:
        df_nuevo = pd.DataFrame([{
            "Fecha": datos['Fecha'],
            "ID": datos['ID'],
            "Nombre": datos['Nombre'],
            "Empresa": datos['Empresa'],
            "Cargo": datos.get('Cargo', 'NO REGISTRA'),
            "Tema": datos['Tema']
        }])

        # ⚡ cache corto evita recargar siempre
        df_existente = conn.read(worksheet="Hoja", ttl=60)

        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)

        conn.update(worksheet="Hoja", data=df_final)

        return True

    except Exception as e:
        st.error(f"Error Sheets: {e}")
        return False


# =========================================================
# EMAIL (SIN CAMBIOS FUNCIONALES, SOLO ESTABLE)
# =========================================================
def enviar_respaldo_gestion_humana(datos, pdf_buffer):
    try:
        mi_correo = "gestionhumanacpfert@gmail.com"
        password = st.secrets.get("email_password", "bhbwshtosozexhcr")

        msg = MIMEMultipart()
        msg['From'] = mi_correo
        msg['To'] = mi_correo
        msg['Subject'] = f"Asistencia: {datos['Nombre']}"

        html = f"""
        <h3>Campofert Registro</h3>
        <p>{datos['Nombre']}</p>
        <p>{datos['Tema']}</p>
        """

        msg.attach(MIMEText(html, 'html'))

        pdf_buffer.seek(0)
        adjunto = MIMEBase('application', 'octet-stream')
        adjunto.set_payload(pdf_buffer.read())
        encoders.encode_base64(adjunto)
        adjunto.add_header('Content-Disposition',
                           f"attachment; filename=cert_{datos['ID']}.pdf")
        msg.attach(adjunto)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mi_correo, password)
        server.sendmail(mi_correo, mi_correo, msg.as_string())
        server.quit()

        return True

    except Exception:
        return False


# =========================================================
# CSS (NO TOCADO)
# =========================================================
st.markdown("""<style>
.stApp { background-color: #F5F5F0; }
[data-testid="stSidebar"] { background-color: #1B5E20; }
.stButton > button { background:#2E7D32; color:white; }
h1,h2,h3 { color:#1B5E20; }
</style>""", unsafe_allow_html=True)


# =========================================================
# LOGIN (SIN CAMBIOS VISUALES)
# =========================================================
if rol_url == "Empleado":
    st.session_state.rol = "Empleado"

if "rol" not in st.session_state:

    st.title("🌱 Campofert People")

    c1, c2 = st.columns(2)

    with c1:
        if st.button("COLABORADOR"):
            st.session_state.rol = "Empleado"
            st.rerun()

    with c2:
        if st.button("ADMIN"):
            st.session_state.esperando_clave = True
            st.rerun()

    if st.session_state.get("esperando_clave"):
        clave = st.text_input("Clave", type="password")

        if st.button("Entrar"):
            if clave == "campofert2026":
                st.session_state.rol = "Admin"
                del st.session_state["esperando_clave"]
                st.rerun()

    st.stop()


# =========================================================
# INTERFAZ
# =========================================================
st.title("Registro de Capacitación")

menu = "📋 Registro Asistencia"

if st.session_state.get("rol") == "Admin":
    menu = st.sidebar.radio("Menú", [
        "📋 Registro Asistencia",
        "👥 Empleados",
        "📤 Cargar Archivo",
        "📊 Dashboard",
        "📄 Historial",
        "📁 Reportes"
    ])


# =========================================================
# REGISTRO (MISMO FLUJO, SOLO OPTIMIZADO)
# =========================================================
if menu == "📋 Registro Asistencia":

    st.info(f"Tema: {tema_actual}")

    df = obtener_datos()

    if st.session_state.paso == 1:

        cedula = st.text_input("Cédula")

        if cedula and not df.empty:

            res = df[df["ID"].astype(str) == cedula]

            if not res.empty:
                st.session_state.persona = res.iloc[0].to_dict()
                st.session_state.cedula = cedula

                if st.button("Continuar"):
                    st.session_state.paso = 2
                    st.rerun()

    elif st.session_state.paso == 2:

        foto = st.camera_input("Foto")

        if foto:
            st.session_state.foto = foto
            if st.button("Firma"):
                st.session_state.paso = 3
                st.rerun()

    elif st.session_state.paso == 3:

        canvas_res = st_canvas(height=180, width=350, key="firma")

        if st.button("Finalizar"):

            datos = {
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona["Apellidos y Nombres"],
                "Empresa": st.session_state.persona["Empresa"],
                "Cargo": st.session_state.persona.get("Cargo", ""),
                "Tema": tema_actual
            }

            if guardar_en_google_sheets(datos):

                # ⚡ PDF optimizado (sin cambios visuales)
                pdf = BytesIO()
                p = canvas.Canvas(pdf, pagesize=letter)
                p.drawString(100, 700, f"{datos['Nombre']} - {datos['Tema']}")
                p.save()

                enviar_respaldo_gestion_humana(datos, pdf)

                st.success("Registro exitoso")
