import streamlit as st
import pandas as pd
import os
import io
import pytz
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

# =============================================================================
# 1. CONFIGURACIÓN Y CONEXIONES
# =============================================================================
st.set_page_config(page_title="Campofert - Registro de Asistencia", layout="centered", page_icon="🌱")

# Conexión a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Configuración de Correo
EMAIL_USER = "gestionhumanacpfert@gmail.com"
EMAIL_PASS = "bhbwshtosozexhcr" 

# =============================================================================
# 2. FUNCIONES DE APOYO
# =============================================================================

def obtener_datos():
    """Carga la base de datos de empleados con manejo de errores"""
    try:
        # Intenta leer la pestaña 'Empleados'. Si falla, devolverá un DataFrame vacío.
        df = conn.read(worksheet="Empleados", ttl=0)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        # Si hay error, mostramos un mensaje amigable y permitimos continuar como invitado
        st.warning(f"No se pudo conectar con la pestaña 'Empleados'. Verifica el nombre en Google Sheets.")
        return pd.DataFrame()

def enviar_respaldo_gestion_humana(datos, pdf_buffer):
    """Envía el PDF por correo electrónico"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER 
    msg['Subject'] = f"✅ Nueva Asistencia: {datos['Nombre']} - {datos['Tema']}"

    cuerpo_html = f"<html><body><h2>Respaldo de Capacitación</h2><p>Empleado: {datos['Nombre']}</p></body></html>"
    msg.attach(MIMEText(cuerpo_html, 'html'))

    pdf_buffer.seek(0)
    adjunto = MIMEBase('application', 'octet-stream')
    adjunto.set_payload(pdf_buffer.read())
    encoders.encode_base64(adjunto)
    adjunto.add_header('Content-Disposition', f"attachment; filename=Asistencia_{datos['ID']}.pdf")
    msg.attach(adjunto)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_USER, msg.as_string())
        server.quit()
        return True
    except:
        return False

def guardar_en_google_sheets(datos):
    """Guarda el registro en la pestaña 'Hoja'"""
    try:
        df_existente = conn.read(worksheet="Hoja", ttl=0)
        df_nuevo = pd.DataFrame([datos])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        conn.update(worksheet="Hoja", data=df_final)
        return True
    except Exception as e:
        st.error(f"Error al guardar en la pestaña 'Hoja': {e}")
        return False

def generar_pdf(datos, imagen_firma, imagen_foto):
    """Crea el certificado en PDF"""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Logos
    try:
        if os.path.exists("logo_campofert.png"):
            p.drawImage(ImageReader("logo_campofert.png"), 50, 620, width=135, preserveAspectRatio=True, mask='auto')
        if os.path.exists("logo_campolab.png"):
            p.drawImage(ImageReader("logo_campolab.png"), 430, 620, width=135, preserveAspectRatio=True, mask='auto')
    except: pass

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 620, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    
    p.setFont("Helvetica", 11)
    y_info = 520
    p.drawString(100, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(100, y_info - 20, f"Identificación: {datos['ID']}")
    p.drawString(100, y_info - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(100, y_info - 60, f"Cargo: {datos.get('Cargo', 'NO REGISTRA')}")
    p.drawString(100, y_info - 80, f"Tema: {datos['Tema']}")
    p.drawString(100, y_info - 100, f"Fecha/Hora: {datos['Fecha']}")

    if imagen_foto is not None:
        p.drawImage(ImageReader(imagen_foto), (width/2)-90, 240, width=180, height=135, preserveAspectRatio=True)

    if imagen_firma is not None:
        img_f = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
        p.drawImage(ImageReader(img_f), (width/2)-75, 150, width=150, height=70, mask='auto')
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# 3. INTERFAZ Y LÓGICA
# =============================================================================

# Banner de logos
col_l, col_r = st.columns([1,1])
with col_l:
    if os.path.exists("logo_campofert.png"): st.image("logo_campofert.png", width=150)
with col_r:
    if os.path.exists("logo_campolab.png"): st.image("logo_campolab.png", width=150)

st.title("Registro de Capacitación")

# Parámetros URL
params = st.query_params
tema_actual = (params.get("tema") or "CAPACITACIÓN GENERAL").replace("+", " ").upper()
st.info(f"📋 Tema: {tema_actual}")

if 'paso' not in st.session_state:
    st.session_state.paso = 1

df_maestro = obtener_datos()

# --- PASO 1: VALIDACIÓN ---
if st.session_state.paso == 1:
    cedula_input = st.text_input("Ingresa tu Cédula:").strip()
    
    if cedula_input:
        encontrado = False
        if not df_maestro.empty:
            df_maestro['ID'] = df_maestro['ID'].astype(str)
            res = df_maestro[df_maestro['ID'] == cedula_input]
            if not res.empty:
                st.session_state.persona = res.iloc[0].to_dict()
                st.session_state.cedula = cedula_input
                st.success(f"✅ Hola, {st.session_state.persona.get('Apellidos y Nombres')}")
                if st.button("Continuar ➡️"):
                    st.session_state.paso = 2
                    st.rerun()
                encontrado = True
        
        if not encontrado:
            st.warning("Cédula no encontrada. Por favor, regístrate como invitado:")
            with st.form("invitado"):
                n = st.text_input("Nombre Completo:")
                e = st.selectbox("Empresa:", ["Campofert", "Campolab", "Invitado"])
                c = st.text_input("Cargo:")
                if st.form_submit_button("Validar como Invitado") and n:
                    st.session_state.persona = {'Apellidos y Nombres': n, 'Empresa': e, 'Cargo': c}
                    st.session_state.cedula = cedula_input
                    st.session_state.paso = 2
                    st.rerun()

# --- PASO 2: CÁMARA ---
elif st.session_state.paso == 2:
    st.subheader("📸 Foto de Identidad")
    foto = st.camera_input("Capturar")
    if foto:
        st.session_state.foto_data = foto
        if st.button("Siguiente: Firma ✍️"):
            st.session_state.paso = 3
            st.rerun()

# --- PASO 3: FIRMA ---
elif st.session_state.paso == 3:
    st.subheader("✍️ Firma Digital")
    canvas_res = st_canvas(stroke_width=3, stroke_color="#000000", background_color="#ffffff", height=180, width=350, key="f1")
    
    if st.button("Finalizar Registro ✅"):
        if canvas_res.image_data is not None:
            datos = {
                "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M:%S"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona['Apellidos y Nombres'],
                "Empresa": st.session_state.persona['Empresa'],
                "Cargo": st.session_state.persona.get('Cargo', 'Invitado'),
                "Tema": tema_actual
            }
            if guardar_en_google_sheets(datos):
                pdf = generar_pdf(datos, canvas_res.image_data, st.session_state.get('foto_data'))
                enviar_respaldo_gestion_humana(datos, pdf)
                pdf.seek(0)
                st.session_state.pdf_doc = pdf
                st.session_state.paso = 4
                st.rerun()
        else:
            st.error("Debes firmar.")

# --- PASO 4: DESCARGA ---
elif st.session_state.paso == 4:
    st.success("¡Registro Exitoso!")
    st.download_button("📥 Descargar PDF", data=st.session_state.pdf_doc.getvalue(), file_name="Certificado.pdf")
    if st.button("Nuevo Registro"):
        st.session_state.clear()
        st.rerun()
