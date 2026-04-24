import streamlit as st
import pandas as pd
import os
import io
import pytz
import threading
import urllib.parse
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw
from streamlit_gsheets import GSheetsConnection
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert People - Gestión Humana", layout="centered", page_icon="🌱")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS CORPORATIVO DE ALTO IMPACTO ---
st.markdown("""
<style>
    .stApp { background-color: #F8F9F5; }
    
    /* Contenedores */
    .main-card {
        background-color: white;
        padding: 25px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border-top: 5px solid #1B5E20;
    }
    
    /* Botones */
    .stButton > button {
        background-color: #2E7D32;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.7rem 1.5rem;
        font-weight: bold;
        width: 100%;
        transition: 0.3s;
    }
    .stButton > button:hover {
        background-color: #F9A825;
        color: #1B5E20;
    }
    
    /* Inputs */
    .stTextInput > div > div > input {
        border: 2px solid #E0E0E0;
        border-radius: 8px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #2E7D32;
    }

    h1, h2, h3 { color: #1B5E20; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
    
    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #1B5E20; }
    [data-testid="stSidebar"] * { color: white !important; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES OPTIMIZADAS ---
@st.cache_data(ttl=600)
def cargar_logos():
    """Carga los logos en caché para no saturar el procesador"""
    logos = {}
    if os.path.exists("logo_campofert.png"): logos['campofert'] = ImageReader("logo_campofert.png")
    if os.path.exists("logo_campolab.png"): logos['campolab'] = ImageReader("logo_campolab.png")
    return logos

def proceso_pesado_email(datos, firma, foto):
    """Ejecuta el envío de correo en un hilo separado (Background)"""
    try:
        buffer = generar_pdf_local(datos, firma, foto)
        remitente = "gestionhumanacpfert@gmail.com"
        password = "bhbwshtosozexhcr"
        
        msg = MIMEMultipart()
        msg['Subject'] = f"✅ Registro: {datos['Nombre']} - {datos['Tema']}"
        msg['From'] = remitente
        msg['To'] = remitente
        
        msg.attach(MIMEText(f"Registro automático de asistencia.\nColaborador: {datos['Nombre']}\nID: {datos['ID']}", 'plain'))
        
        buffer.seek(0)
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(buffer.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f"attachment; filename=Registro_{datos['ID']}.pdf")
        msg.attach(part)
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(remitente, password)
            server.sendmail(remitente, remitente, msg.as_string())
    except Exception as e:
        print(f"Error en segundo plano: {e}")

def generar_pdf_local(datos, imagen_firma, imagen_foto):
    """Genera el PDF optimizado sin QR"""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Colores
    verde = (0.10, 0.36, 0.16)
    
    # Diseño de Cabecera
    p.setFillColorRGB(0.10, 0.36, 0.16)
    p.rect(0, height-100, width, 100, fill=1, stroke=0)
    
    # Logos (si existen)
    logos = cargar_logos()
    if 'campofert' in logos: p.drawImage(logos['campofert'], 30, height-80, width=80, preserveAspectRatio=True, mask='auto')
    
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, height-60, "CERTIFICADO DE ASISTENCIA CORPORATIVO")
    
    # Cuerpo
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, height-150, "Se certifica la participación activa de:")
    
    p.setFillColorRGB(0.1, 0.3, 0.1)
    p.setFont("Helvetica-Bold", 20)
    p.drawCentredString(width/2, height-185, datos['Nombre'].upper())
    
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, height-210, f"Cédula: {datos['ID']}")
    
    # Cuadro de Detalles
    p.setStrokeColorRGB(0.1, 0.3, 0.1)
    p.roundRect(50, height-320, width-100, 80, 10, stroke=1, fill=0)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(70, height-270, f"CAPACITACIÓN: {datos['Tema']}")
    p.setFont("Helvetica", 11)
    p.drawString(70, height-290, f"Empresa: {datos['Empresa']}  |  Cargo: {datos['Cargo']}")
    p.drawString(70, height-305, f"Fecha: {datos['Fecha']}")

    # Foto y Firma
    if imagen_foto:
        img_f = Image.open(imagen_foto).convert("RGB")
        p.drawImage(ImageReader(img_f), 80, 200, width=100, height=100)
    
    if imagen_firma is not None:
        img_s = Image.fromarray(imagen_firma.astype("uint8"), "RGBA")
        p.drawImage(ImageReader(img_s), width-250, 210, width=150, height=60, mask='auto')
    
    p.line(width-260, 205, width-80, 205)
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(width-170, 190, "Firma del Asistente")
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# FLUJO DE PANTALLAS
# =============================================================================

# Manejo de Roles
if 'rol' not in st.session_state:
    st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
    st.image("logo_campofert.png" if os.path.exists("logo_campofert.png") else "🌱", width=200)
    st.title("Sistema Campofert People")
    st.markdown("</div>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("👷 Ingresar como Colaborador"):
            st.session_state.rol = "Empleado"
            st.rerun()
    with c2:
        if st.button("🛡️ Acceso Administrativo"):
            st.session_state.rol = "Admin"
            st.rerun()
    st.stop()

# --- VISTA ADMINISTRADOR ---
if st.session_state.rol == "Admin":
    with st.sidebar:
        st.header("⚙️ Gestión")
        menu = st.radio("Módulos", ["Dashboard", "Generar Links", "Registro Interno", "Cerrar"])
        if menu == "Cerrar":
            st.session_state.clear()
            st.rerun()

    if menu == "Generar Links":
        st.title("🔗 Generador de Enlaces")
        cap_name = st.text_input("Nombre de la Capacitación:")
        if cap_name:
            cod = urllib.parse.quote_plus(cap_name.upper())
            st.code(f"https://tu-app.streamlit.app/?tema={cod}")

# --- VISTA REGISTRO (LO QUE VE EL TRABAJADOR) ---
if st.session_state.rol == "Empleado" or (st.session_state.rol == "Admin" and menu == "Registro Interno"):
    tema_actual = st.query_params.get("tema", "CAPACITACIÓN GENERAL").replace("+", " ").upper()
    
    st.markdown(f"<div class='main-card'>", unsafe_allow_html=True)
    st.subheader(f"📍 Registro: {tema_actual}")
    
    if 'paso' not in st.session_state: st.session_state.paso = 1

    if st.session_state.paso == 1:
        cedula = st.text_input("Ingrese su Cédula para iniciar:", key="ced")
        if cedula:
            # Búsqueda rápida
            if st.button("Continuar ➡️"):
                st.session_state.cedula = cedula
                st.session_state.paso = 2
                st.rerun()

    elif st.session_state.paso == 2:
        st.info("📸 Tome una foto para validar su identidad")
        foto = st.camera_input("Foto de Verificación")
        if foto:
            st.session_state.foto_data = foto
            if st.button("Siguiente ➡️"):
                st.session_state.paso = 3
                st.rerun()

    elif st.session_state.paso == 3:
        st.info("✍️ Por favor firme en el recuadro")
        canvas_res = st_canvas(stroke_width=3, stroke_color="#1B5E20", height=150, width=350, key="firma_c")
        
        if st.button("✅ FINALIZAR REGISTRO"):
            # 1. Preparar Datos
            datos = {
                "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M"),
                "ID": st.session_state.cedula,
                "Nombre": "NOMBRE_CARGADO", # Aquí conectarías con tu lógica de empleados.xlsx
                "Empresa": "CAMPOFERT",
                "Cargo": "OPERATIVO",
                "Tema": tema_actual
            }
            
            # 2. Generar PDF Inmediato para el usuario (RAPIDEZ)
            pdf_user = generar_pdf_local(datos, canvas_res.image_data, st.session_state.foto_data)
            st.session_state.pdf_buffer = pdf_user
            
            # 3. Lanzar procesos pesados en SEGUNDO PLANO
            hilo = threading.Thread(target=proceso_pesado_email, args=(datos, canvas_res.image_data, st.session_state.foto_data))
            hilo.start()
            
            st.session_state.paso = 4
            st.rerun()

    elif st.session_state.paso == 4:
        st.balloons()
        st.success("¡Registro Completado con Éxito!")
        st.download_button("📥 DESCARGAR CERTIFICADO", st.session_state.pdf_buffer.getvalue(), f"Certificado_{st.session_state.cedula}.pdf", "application/pdf")
        if st.button("Hacer otro registro"):
            st.session_state.paso = 1
            st.rerun()
    
    st.markdown("</div>", unsafe_allow_html=True)
