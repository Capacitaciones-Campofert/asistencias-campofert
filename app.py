import streamlit as st
import pandas as pd
import os
import io
import pytz
import qrcode
import threading
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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert - Registro de Asistencia", layout="centered", page_icon="🌱")

# --- CSS CORPORATIVO (RESTAURADO AL 100%) ---
CSS_CORPORATIVO = """
<style>
    .stApp { background-color: #F5F5F0; }
    [data-testid="stSidebar"] { background-color: #1B5E20; padding-top: 20px; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stButton > button {
        background-color: #2E7D32; color: white; border: none;
        border-radius: 8px; font-weight: bold; padding: 0.6rem 1.2rem;
        width: 100%;
    }
    .stButton > button:hover { background-color: #F9A825; color: #1B5E20; }
    h1, h2, h3 { color: #1B5E20; font-family: 'Arial'; }
    .metric-card { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); text-align: center; }
</style>
"""
st.markdown(CSS_CORPORATIVO, unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CARGA DE DATOS (IMPORTANTE PARA EL DASHBOARD) ---
@st.cache_data(ttl=60)
def cargar_asistencia():
    try:
        return conn.read(worksheet="Hoja", ttl=0)
    except:
        return pd.DataFrame(columns=["Fecha", "ID", "Nombre", "Empresa", "Cargo", "Tema"])

@st.cache_data(ttl=600)
def obtener_datos_empleados():
    if os.path.exists("empleados.xlsx"):
        df = pd.read_excel("empleados.xlsx", engine='openpyxl', dtype={'ID': str})
        df.columns = df.columns.str.strip()
        return df
    return None

# --- VARIABLES DE ESTADO ---
params = st.query_params
tema_actual = params.get("tema", "CAPACITACIÓN GENERAL").replace("+", " ").upper()
if 'paso' not in st.session_state: st.session_state.paso = 1

# =============================================================================
# FUNCIONES DE FONDO (OPTIMIZADAS)
# =============================================================================

def enviar_correo_hilo(datos, firma, foto):
    try:
        pdf_buf = generar_pdf_completo(datos, firma, foto)
        mi_correo = "gestionhumanacpfert@gmail.com"
        password = "bhbwshtosozexhcr"
        msg = MIMEMultipart()
        msg['Subject'] = f"✅ Registro Asistencia: {datos['Nombre']}"
        msg.attach(MIMEText(f"Se ha registrado una nueva asistencia para el tema: {datos['Tema']}", 'plain'))
        pdf_buf.seek(0)
        adj = MIMEBase('application', 'octet-stream')
        adj.set_payload(pdf_buf.read())
        encoders.encode_base64(adj)
        adj.add_header('Content-Disposition', f"attachment; filename=Certificado_{datos['ID']}.pdf")
        msg.attach(adj)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mi_correo, password)
        server.sendmail(mi_correo, mi_correo, msg.as_string())
        server.quit()
    except: pass

def generar_pdf_completo(datos, firma, foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    # Aquí iría tu diseño de ReportLab que ya tenías
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 700, "CERTIFICADO DE ASISTENCIA - CAMPOFERT")
    p.setFont("Helvetica", 12)
    p.drawString(100, 650, f"Nombre: {datos['Nombre']}")
    p.drawString(100, 630, f"Cédula: {datos['ID']}")
    p.drawString(100, 610, f"Tema: {datos['Tema']}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# INTERFAZ DE INGRESO (RESTAURADA SEGÚN IMAGEN 2)
# =============================================================================
if 'rol' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>🌱 Campofert People</h1>", unsafe_allow_html=True)
    st.write("")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👷 COLABORADOR"):
            st.session_state.rol = "Empleado"
            st.rerun()
    with col2:
        if st.button("🛡️ ADMINISTRADOR"):
            st.session_state.esperando_admin = True
    
    if st.session_state.get('esperando_admin'):
        clave = st.text_input("Clave Admin", type="password")
        if st.button("Validar"):
            if clave == "campofert2026":
                st.session_state.rol = "Admin"
                st.rerun()
            else: st.error("Clave Incorrecta")
    st.stop()

# =============================================================================
# PANEL Y MENÚ (RESTAURADO SEGÚN IMAGEN 1)
# =============================================================================
if st.session_state.rol == "Empleado":
    st.markdown("<style>[data-testid='stSidebar'] {display:none;}</style>", unsafe_allow_html=True)
    menu = "📋 Registro Asistencia"
else:
    with st.sidebar:
        if os.path.exists("logo_campofert.png"):
            st.image("logo_campofert.png")
        st.markdown("### 🛡️ Panel Administrativo")
        st.markdown("---")
        menu = st.radio("Seleccione módulo", ["📋 Registro Asistencia", "👥 Empleados", "📤 Cargar Archivo", "📊 Dashboard", "📄 Historial", "📁 Reportes"])
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

# =============================================================================
# LÓGICA DE MÓDULOS (MOSTRANDO INFORMACIÓN)
# =============================================================================

df_asistencia = cargar_asistencia()

if menu == "📊 Dashboard":
    st.markdown(f"## 📊 Dashboard Ejecutivo")
    c1, c2, c3 = st.columns(3)
    c1.metric("Registros", len(df_asistencia))
    c2.metric("Personas", df_asistencia['ID'].nunique())
    c3.metric("Capacitaciones", df_asistencia['Tema'].nunique())
    
    st.markdown("### Últimos registros")
    st.dataframe(df_asistencia.tail(10), use_container_width=True)

elif menu == "📋 Registro Asistencia":
    st.markdown(f"## 📝 Registro: {tema_actual}")
    df_emp = obtener_datos_empleados()
    
    if st.session_state.paso == 1:
        cedula = st.text_input("Ingrese su Cédula para iniciar:")
        if cedula:
            persona = df_emp[df_emp['ID'] == cedula] if df_emp is not None else pd.DataFrame()
            if not persona.empty:
                st.session_state.persona = persona.iloc[0].to_dict()
                st.session_state.cedula = cedula
                st.success(f"Bienvenido(a), {st.session_state.persona['Apellidos y Nombres']}")
                if st.button("Continuar"): 
                    st.session_state.paso = 2
                    st.rerun()
            else: st.error("Cédula no encontrada en la base de datos.")

    elif st.session_state.paso == 2:
        foto = st.camera_input("Toma una foto para el certificado")
        if foto:
            st.session_state.foto_data = foto
            if st.button("Siguiente: Firma"): 
                st.session_state.paso = 3
                st.rerun()

    elif st.session_state.paso == 3:
        st.markdown("### ✍️ Firme en el recuadro")
        canvas_res = st_canvas(stroke_width=3, stroke_color="#1B5E20", height=150, width=300, key="firma")
        if st.button("Finalizar Registro ✅"):
            datos = {
                "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M:%S"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona['Apellidos y Nombres'],
                "Empresa": st.session_state.persona['Empresa'],
                "Cargo": st.session_state.persona.get('Cargo', 'N/A'),
                "Tema": tema_actual
            }
            # Guardar y disparar hilo
            conn.create(worksheet="Hoja", data=pd.DataFrame([datos]))
            st.session_state.pdf_doc = generar_pdf_completo(datos, canvas_res.image_data, st.session_state.foto_data)
            threading.Thread(target=enviar_correo_hilo, args=(datos, canvas_res.image_data, st.session_state.foto_data)).start()
            st.session_state.paso = 4
            st.rerun()

    elif st.session_state.paso == 4:
        st.success("¡Registro completado!")
        st.download_button("📥 Descargar Certificado", st.session_state.pdf_doc.getvalue(), "Certificado.pdf")
        if st.button("Inicio"):
            st.session_state.paso = 1
            st.rerun()

elif menu == "👥 Empleados":
    df_emp = obtener_datos_empleados()
    st.markdown("## 👥 Base de Datos de Empleados")
    if df_emp is not None:
        st.dataframe(df_emp, use_container_width=True)
    else: st.warning("No hay archivo empleados.xlsx cargado.")

elif menu == "📄 Historial":
    st.markdown("## 📄 Historial Completo de Asistencias")
    st.dataframe(df_asistencia, use_container_width=True)
