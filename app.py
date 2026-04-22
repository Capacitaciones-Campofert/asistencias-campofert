import streamlit as st
import pandas as pd
import os
import io
import base64
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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert - Registro de Asistencia", layout="centered", page_icon="🌱")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CONFIGURACIÓN DE CORREO (SECRETS) ---
# Configura esto en el panel de Streamlit Cloud (Settings > Secrets)
EMAIL_USER = "gestionhumanacpfert@gmail.com"
EMAIL_PASS = st.secrets.get("email_password", "bhbwshtosozexhcr") # Fallback para pruebas

# --- LEER TEMA DESDE EL URL ---
params = st.query_params
tema_raw = params.get("tema") or params.get("Tema") or "CAPACITACIÓN GENERAL"
tema_actual = tema_raw.replace("+", " ").upper()

# =============================================================================
# FUNCIONES DE BASE DE DATOS
# =============================================================================

def obtener_datos():
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, engine='openpyxl', dtype={'ID': str})
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            st.error(f"Error al leer empleados.xlsx: {e}")
    return None

def guardar_en_google_sheets(datos):
    try:
        df_existente = conn.read(worksheet="Hoja", ttl=0)
        df_nuevo = pd.DataFrame([datos])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        conn.update(worksheet="Hoja", data=df_final)
        return True
    except Exception as e:
        st.error(f"Error de conexión con Sheets: {e}")
        return False

# =============================================================================
# FUNCIONES DE PDF CON FOTO Y FIRMA
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Títulos y Encabezado
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 730, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 710, "CAMPOFERT S.A.S / CAMPOLAB")

    # Información
    p.setFont("Helvetica", 11)
    y_info = 670
    p.drawString(70, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(70, y_info - 20, f"Identificación: {datos['ID']}")
    p.drawString(70, y_info - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(70, y_info - 60, f"Tema: {datos['Tema']}")
    p.drawString(70, y_info - 80, f"Fecha/Hora: {datos['Fecha']}")
    
    p.line(70, y_info - 90, 530, y_info - 90)

    # --- INSERTAR FOTO DE EVIDENCIA ---
    p.drawString(70, 550, "EVIDENCIA FOTOGRÁFICA (IDENTIDAD):")
    if imagen_foto is not None:
        img_foto = Image.open(imagen_foto)
        p.drawImage(ImageReader(img_foto), 70, 360, width=180, height=140, preserveAspectRatio=True)

    # --- INSERTAR FIRMA ---
    p.drawString(350, 550, "FIRMA DEL TRABAJADOR:")
    if imagen_firma is not None:
        img_firma = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
        p.drawImage(ImageReader(img_firma), 350, 380, width=150, height=80, mask='auto')
    
    p.drawString(350, 370, "__________________________")
    p.setFont("Helvetica-Oblique", 9)
    p.drawString(350, 355, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def enviar_respaldo(datos, pdf_buffer):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USER
    msg['To'] = EMAIL_USER
    msg['Subject'] = f"✅ Auditoría Asistencia: {datos['Nombre']}"

    cuerpo = f"Registro de asistencia generado para {datos['Nombre']} el {datos['Fecha']}."
    msg.attach(MIMEText(cuerpo, 'plain'))

    adjunto = MIMEBase('application', 'octet-stream')
    adjunto.set_payload(pdf_buffer.getvalue())
    encoders.encode_base64(adjunto)
    adjunto.add_header('Content-Disposition', f"attachment; filename=Auditoria_{datos['ID']}.pdf")
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

# =============================================================================
# INTERFAZ DE USUARIO
# =============================================================================

st.title("Sistema de Registro de Capacitación")
st.info(f"📋 Tema: **{tema_actual}**")

df_maestro = obtener_datos()
if 'finalizado' not in st.session_state:
    st.session_state.finalizado = False

if not st.session_state.finalizado:
    cedula_input = st.text_input("Ingresa tu ID / Cédula:").strip()
    
    if cedula_input:
        resultado = df_maestro[df_maestro['ID'] == cedula_input] if df_maestro is not None else pd.DataFrame()
        
        if not resultado.empty:
            persona = resultado.iloc[0]
            st.success(f"✅ Usuario: {persona['Apellidos y Nombres']}")
            
            # --- PASO 1: FOTO OBLIGATORIA ---
            st.subheader("📸 Paso 1: Evidencia Fotográfica")
            foto = st.camera_input("Captura tu foto para auditoría")
            
            if foto:
                # --- PASO 2: FIRMA ---
                st.subheader("✍️ Paso 2: Firma Digital")
                canvas_result = st_canvas(
                    stroke_width=3, stroke_color="#000000", background_color="#eeeeee",
                    height=150, drawing_mode="freedraw", key="firma_audit"
                )

                if st.button("🚀 Confirmar Registro"):
                    if canvas_result.image_data is not None:
                        datos = {
                            "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M"),
                            "ID": cedula_input,
                            "Nombre": persona['Apellidos y Nombres'],
                            "Empresa": persona['Empresa'],
                            "Cargo": persona['Cargo'],
                            "Tema": tema_actual
                        }
                        
                        # Guardar y generar certificado
                        if guardar_en_google_sheets(datos):
                            pdf = generar_pdf(datos, canvas_result.image_data, foto)
                            enviar_respaldo(datos, pdf)
                            st.session_state.pdf_final = pdf
                            st.session_state.archivo_nombre = f"Certificado_{cedula_input}.pdf"
                            st.session_state.finalizado = True
                            st.rerun()
                    else:
                        st.error("Por favor, firma antes de confirmar.")
        else:
            st.warning("ID no encontrado en la base de datos.")

else:
    st.balloons()
    st.success("¡Registro completado y validado con éxito!")
    st.download_button("📥 Descargar Certificado con Evidencia", 
                       data=st.session_state.pdf_final.getvalue(), 
                       file_name=st.session_state.archivo_nombre, 
                       mime="application/pdf")
    
    if st.button("🔄 Nuevo Registro"):
        st.session_state.finalizado = False
        st.rerun()
