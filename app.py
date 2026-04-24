import streamlit as st
import pandas as pd
import os
import io
import pytz
import qrcode
import threading # Mejora: Procesos en segundo plano para el correo
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

# --- CSS CORPORATIVO (Mantenido igual) ---
CSS_CORPORATIVO = """
<style>
    .stApp { background-color: #F5F5F0; }
    [data-testid="stSidebar"] { background-color: #1B5E20; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stButton > button {
        background-color: #2E7D32; color: white; border: none;
        border-radius: 8px; font-weight: bold; padding: 0.5rem 1rem;
    }
    .stButton > button:hover { background-color: #F9A825; color: #1B5E20; }
    h1, h2, h3 { color: #1B5E20; }
    footer { visibility: hidden; }
</style>
"""
st.markdown(CSS_CORPORATIVO, unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- LEER TEMA Y CONFIGURACIÓN ---
params = st.query_params
tema_desde_url = params.get("tema") or params.get("Tema")
if tema_desde_url:
    st.session_state.tema_actual = tema_desde_url.replace("+", " ").upper()
elif 'tema_actual' not in st.session_state:
    st.session_state.tema_actual = "CAPACITACIÓN GENERAL"

tema_actual = st.session_state.tema_actual
rol_url = params.get("rol")

# =============================================================================
# FUNCIONES OPTIMIZADAS
# =============================================================================

@st.cache_data(ttl=600) # Mejora: Lectura veloz de empleados (cache 10 min)
def obtener_datos():
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, engine='openpyxl', dtype={'ID': str})
            df.columns = df.columns.str.strip()
            return df
        except Exception:
            return None
    return None

def proceso_segundo_plano(datos, imagen_firma, imagen_foto):
    """ Función para enviar correo sin bloquear la pantalla del usuario """
    try:
        pdf_buffer = generar_pdf(datos, imagen_firma, imagen_foto)
        mi_correo = "gestionhumanacpfert@gmail.com"
        password = "bhbwshtosozexhcr"

        msg = MIMEMultipart()
        msg['From'] = mi_correo
        msg['To'] = mi_correo
        msg['Subject'] = f"✅ Respaldo: {datos['Nombre']} - {datos['Tema']}"

        cuerpo = f"Registro de asistencia recibido para {datos['Nombre']}."
        msg.attach(MIMEText(cuerpo, 'plain'))

        pdf_buffer.seek(0)
        adjunto = MIMEBase('application', 'octet-stream')
        adjunto.set_payload(pdf_buffer.read())
        encoders.encode_base64(adjunto)
        adjunto.add_header('Content-Disposition', f"attachment; filename=Asistencia_{datos['ID']}.pdf")
        msg.attach(adjunto)

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mi_correo, password)
        server.sendmail(mi_correo, mi_correo, msg.as_string())
        server.quit()
    except Exception as e:
        print(f"Error en envío de fondo: {e}")

def guardar_en_google_sheets(datos):
    """ Mejora: Escritura directa para evitar lentitud """
    try:
        df_nuevo = pd.DataFrame([datos])
        conn.create(worksheet="Hoja", data=df_nuevo)
        return True
    except Exception as e:
        st.error(f"Error en base de datos: {e}")
        return False

def generar_pdf(datos, imagen_firma, imagen_foto):
    """ Tu lógica de diseño de PDF (mantén aquí el código de diseño que ya tenías) """
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    # ... (Aquí va tu código de diseño de ReportLab: logos, textos, cuadros) ...
    # Por ahora agrego una estructura básica para que no de error:
    p.drawString(100, 750, f"Certificado para: {datos['Nombre']}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# SEGURIDAD Y LOGIN (Mantenido igual)
# =============================================================================
if rol_url == "Empleado":
    st.session_state.rol = "Empleado"

if 'rol' not in st.session_state:
    st.markdown('<h1 style="text-align:center;">🌱 Campofert People</h1>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("👷 COLABORADOR", use_container_width=True):
        st.session_state.rol = "Empleado"
        st.rerun()
    if c2.button("🛡️ ADMINISTRADOR", use_container_width=True):
        st.session_state.esperando_admin = True
    
    if st.session_state.get('esperando_admin'):
        clave = st.text_input("Clave de acceso", type="password")
        if st.button("Validar ✅"):
            if clave == "campofert2026":
                st.session_state.rol = "Admin"
                st.rerun()
            else:
                st.error("Clave incorrecta")
    st.stop()

# =============================================================================
# MENÚ Y PANEL ADMINISTRATIVO (Respetado 100%)
# =============================================================================
if st.session_state.rol == "Empleado":
    st.markdown("<style>[data-testid='stSidebar'] {display:none;}</style>", unsafe_allow_html=True)
    menu = "📋 Registro Asistencia"
else:
    with st.sidebar:
        st.image("logo_campofert.png") if os.path.exists("logo_campofert.png") else None
        st.markdown("### Panel Administrativo")
        menu = st.radio("Módulos", ["📋 Registro Asistencia", "👥 Empleados", "📤 Cargar Archivo", "📊 Dashboard", "📄 Historial", "📁 Reportes"])
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

# =============================================================================
# LÓGICA DE LOS MÓDULOS
# =============================================================================

# Aquí incluyes el código de tus otros módulos (Dashboard, Historial, etc.)
# No cambian en nada visual, solo funcionarán más rápido al leer datos.

if menu == "📋 Registro Asistencia":
    if 'paso' not in st.session_state: st.session_state.paso = 1
    
    # ... (Tu lógica de paso 1 y 2 de identificación y foto) ...
    
    # MEJORA EN EL PASO 3 (Finalización rápida)
    if st.session_state.get('paso') == 3:
        st.markdown("### ✍️ Firma Digital")
        canvas_res = st_canvas(stroke_width=3, stroke_color="#1B5E20", height=180, width=350, key="firma_final")

        if st.button("Finalizar y Generar Certificado ✅"):
            if canvas_res.image_data is not None:
                datos_asistencia = {
                    "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M:%S"),
                    "ID": st.session_state.cedula,
                    "Nombre": st.session_state.persona['Apellidos y Nombres'],
                    "Empresa": st.session_state.persona['Empresa'],
                    "Cargo": st.session_state.persona.get('Cargo', 'NO REGISTRA'),
                    "Tema": tema_actual
                }

                # 1. Guardar en Sheets (Ahora es inmediato)
                guardar_en_google_sheets(datos_asistencia)

                # 2. PDF para descarga instantánea
                pdf_para_descarga = generar_pdf(datos_asistencia, canvas_res.image_data, st.session_state.get('foto_data'))
                st.session_state.pdf_doc = pdf_para_descarga

                # 3. LANZAR ENVÍO DE CORREO EN SEGUNDO PLANO
                threading.Thread(
                    target=proceso_segundo_plano, 
                    args=(datos_asistencia, canvas_res.image_data, st.session_state.get('foto_data'))
                ).start()

                st.session_state.paso = 4
                st.rerun()

    if st.session_state.get('paso') == 4:
        st.success("¡Registro completado con éxito!")
        st.download_button("📥 DESCARGAR MI CERTIFICADO", st.session_state.pdf_doc.getvalue(), f"Certificado_{st.session_state.cedula}.pdf")
        if st.button("Hacer otro registro"):
            st.session_state.paso = 1
            st.rerun()
