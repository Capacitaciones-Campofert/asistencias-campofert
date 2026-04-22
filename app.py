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
    """Lee la base de datos de empleados desde Google Sheets"""
    try:
        df = conn.read(worksheet="Empleados", ttl=0)
        df.columns = df.columns.str.strip()
        return df
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return None

def enviar_respaldo_gestion_humana(datos, pdf_buffer):
    """Envía el PDF por correo electrónico"""
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER 
    msg['Subject'] = f"✅ Nueva Asistencia: {datos['Nombre']} - {datos['Tema']}"

    cuerpo_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="border: 1px solid #2e7d32; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2e7d32;">Respaldo de Capacitación</h2>
                <p><strong>Empleado:</strong> {datos['Nombre']}</p>
                <p><strong>Cédula:</strong> {datos['ID']}</p>
                <p><strong>Tema:</strong> {datos['Tema']}</p>
            </div>
        </body>
    </html>
    """
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
    except Exception as e:
        st.error(f"Error enviando correo: {e}")
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
        st.error(f"Error al guardar en Sheets: {e}")
        return False

def generar_pdf(datos, imagen_firma, imagen_foto):
    """Crea el certificado en PDF"""
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    try:
        if os.path.exists("logo_campofert.png"):
            p.drawImage(ImageReader("logo_campofert.png"), 50, 620, width=135, preserveAspectRatio=True, mask='auto')
        if os.path.exists("logo_campolab.png"):
            p.drawImage(ImageReader("logo_campolab.png"), 430, 620, width=135, preserveAspectRatio=True, mask='auto')
    except: pass

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 620, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 600, "CAMPOFERT S.A.S / CAMPOLAB")

    p.setFont("Helvetica", 11)
    y_info = 520
    p.drawString(100, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(100, y_info - 20, f"Identificación: {datos['ID']}")
    p.drawString(100, y_info - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(100, y_info - 60, f"Cargo: {datos.get('Cargo', 'NO REGISTRA')}")
    p.setFont("Helvetica-Bold", 11)
    p.drawString(100, y_info - 80, f"Tema: {datos['Tema']}")
    p.setFont("Helvetica", 11)
    p.drawString(100, y_info - 100, f"Fecha/Hora: {datos['Fecha']}")
    p.line(100, y_info - 110, 510, y_info - 110)

    if imagen_foto is not None:
        p.drawImage(ImageReader(imagen_foto), (width/2)-90, 240, width=180, height=135, preserveAspectRatio=True)

    if imagen_firma is not None:
        img_f = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
        p.drawImage(ImageReader(img_f), (width/2)-75, 150, width=150, height=70, mask='auto')
    
    p.line((width/2)-80, 150, (width/2)+80, 150)
    p.setFont("Helvetica-Oblique", 10)
    p.drawCentredString(width/2, 135, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# 3. INTERFAZ Y LÓGICA DE PASOS
# =============================================================================

# Diseño de Logos superiores
col_v1, col_v2, col_v3 = st.columns([2, 5, 2])
with col_v2:
    c1, c2 = st.columns(2)
    if os.path.exists("logo_campofert.png"):
        c1.image("logo_campofert.png", use_container_width=True)
    if os.path.exists("logo_campolab.png"):
        c2.image("logo_campolab.png", use_container_width=True)

st.markdown("<h1 style='text-align: center;'>Registro de Capacitación</h1>", unsafe_allow_html=True)

# Leer tema del URL
params = st.query_params
tema_actual = (params.get("tema") or "CAPACITACIÓN GENERAL").replace("+", " ").upper()
st.info(f"📋 **TEMA ACTUAL:** {tema_actual}")

# Inicializar sesión
if 'paso' not in st.session_state:
    st.session_state.paso = 1

# Cargar base de datos
df_maestro = obtener_datos()
if df_maestro is not None:
    empresas_lista = sorted(df_maestro['Empresa'].unique().tolist())
else:
    empresas_lista = ["Campofert", "Campolab"]

# --- PASO 1: VALIDACIÓN ---
if st.session_state.paso == 1:
    cedula_input = st.text_input("Ingresa tu ID / Cédula:").strip()
    if cedula_input:
        if df_maestro is not None:
            df_maestro['ID'] = df_maestro['ID'].astype(str)
            res = df_maestro[df_maestro['ID'] == cedula_input]
            
            if not res.empty:
                fila = res.iloc[0]
                st.session_state.persona = fila.to_dict()
                st.session_state.cedula = cedula_input
                st.success(f"✅ Bienvenido, {st.session_state.persona.get('Apellidos y Nombres')}")
                if st.button("Continuar ➡️"):
                    st.session_state.paso = 2
                    st.rerun()
            else:
                st.warning("ID no encontrado. ¿Eres invitado?")
                if st.checkbox("Registrar como Invitado"):
                    with st.form("invitado"):
                        n = st.text_input("Nombre Completo:")
                        e = st.selectbox("Empresa:", empresas_lista)
                        c = st.text_input("Cargo:")
                        if st.form_submit_button("Validar Invitado") and n and c:
                            st.session_state.persona = {'Apellidos y Nombres': n, 'Empresa': e, 'Cargo': c}
                            st.session_state.cedula = cedula_input
                            st.session_state.paso = 2
                            st.rerun()

# --- PASO 2: CÁMARA ---
elif st.session_state.paso == 2:
    st.subheader("📸 Captura de Identidad")
    foto = st.camera_input("Foto de validación")
    if foto:
        st.session_state.foto_data = foto
        if st.button("Ir a la firma ✍️"):
            st.session_state.paso = 3
            st.rerun()

# --- PASO 3: FIRMA Y CIERRE ---
elif st.session_state.paso == 3:
    st.subheader("✍️ Firma Digital")
    canvas_res = st_canvas(
        stroke_width=3, stroke_color="#000000", background_color="#ffffff", 
        height=180, width=350, key="firma_final"
    )
    
    if st.button("Finalizar y Generar Certificado ✅"):
        if canvas_res.image_data is not None:
            datos_asistencia = {
                "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %I:%M:%S %p"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona['Apellidos y Nombres'],
                "Empresa": st.session_state.persona['Empresa'],
                "Cargo": st.session_state.persona.get('Cargo', 'NO REGISTRA'),
                "Tema": tema_actual
            }
            
            with st.spinner("Procesando..."):
                if guardar_en_google_sheets(datos_asistencia):
                    pdf = generar_pdf(datos_asistencia, canvas_res.image_data, st.session_state.get('foto_data'))
                    enviar_respaldo_gestion_humana(datos_asistencia, pdf)
                    pdf.seek(0)
                    st.session_state.pdf_doc = pdf
                    st.session_state.paso = 4
                    st.rerun()
        else:
            st.error("Es necesario firmar.")

# --- PASO 4: ÉXITO ---
elif st.session_state.paso == 4:
    st.balloons()
    st.success("¡Registro completado!")
    if st.session_state.get('pdf_doc'):
        st.download_button(
            label="📥 Descargar Certificado",
            data=st.session_state.pdf_doc.getvalue(),
            file_name=f"Certificado_{st.session_state.cedula}.pdf",
            mime="application/pdf"
        )
    if st.button("Nuevo Registro"):
        for k in ['cedula','persona','pdf_doc','foto_data']: st.session_state.pop(k, None)
        st.session_state.paso = 1
        st.rerun()
