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
# FUNCIONES DE APOYO

def obtener_datos():
    """Lee la base de empleados local para validación rápida"""
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, engine='openpyxl', dtype={'ID': str})
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            st.error(f"Error al leer empleados.xlsx: {e}")
    return None

def enviar_respaldo_gestion_humana(datos, pdf_buffer):
    mi_correo = "gestionhumanacpfert@gmail.com"
    password = "bhbwshtosozexhcr" # Recuerda usar "Contraseña de aplicación"

    msg = MIMEMultipart()
    msg['From'] = mi_correo
    msg['To'] = mi_correo # Se lo envía a sí mismo como respaldo
    msg['Subject'] = f"✅ Nueva Asistencia: {datos['Nombre']} - {datos['Tema']}"

    # Cuerpo del mensaje
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

    # ADJUNTO DEL PDF
    pdf_buffer.seek(0) # IMPORTANTE: Regresa al inicio del archivo
    adjunto = MIMEBase('application', 'octet-stream')
    adjunto.set_payload(pdf_buffer.read())
    encoders.encode_base64(adjunto)
    adjunto.add_header('Content-Disposition', f"attachment; filename=Asistencia_{datos['ID']}.pdf")
    msg.attach(adjunto)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mi_correo, password)
        server.sendmail(mi_correo, mi_correo, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def guardar_en_google_sheets(datos):
    try:
        df_existente = conn.read(worksheet="Hoja", ttl=0)
        df_nuevo = pd.DataFrame([{
            "Fecha": datos['Fecha'],
            "ID": datos['ID'],
            "Nombre": datos['Nombre'],
            "Empresa": datos['Empresa'],
            "Cargo": datos.get('Cargo', 'NO REGISTRA'),
            "Tema": datos['Tema']
        }])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        conn.update(worksheet="Hoja", data=df_final)
        return True
    except Exception as e:
        st.error(f"Error de conexión con Google Sheets: {e}")
        return False

# =============================================================================
# GENERACIÓN DE PDF (DISEÑO FINAL CORREGIDO)
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # 1. LOGOS (Posición Y=620 para visibilidad total y ancho de 135)
    try:
        if os.path.exists("logo_campofert.png"):
            img_cf = Image.open("logo_campofert.png")
            p.drawImage(ImageReader(img_cf), 50, 620, width=135, preserveAspectRatio=True, mask='auto')
        
        if os.path.exists("logo_campolab.png"):
            img_cl = Image.open("logo_campolab.png")
            p.drawImage(ImageReader(img_cl), 430, 620, width=135, preserveAspectRatio=True, mask='auto')
    except:
        pass

    # 2. TÍTULOS (Ajustados proporcionalmente hacia abajo)
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 620, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 600, "CAMPOFERT S.A.S / CAMPOLAB")

    # 3. INFORMACIÓN DEL PARTICIPANTE
    p.setFont("Helvetica", 11)
    y_info = 520
    p.drawString(100, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(100, y_info - 20, f"Identificación: {datos['ID']}")
    p.drawString(100, y_info - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(100, y_info - 60, f"Cargo: {datos.get('Cargo', 'NO REGISTRA')}")
    
    # --- TEMA EN NEGRILLA ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(100, y_info - 80, f"Tema: {datos['Tema']}")
    
    p.setFont("Helvetica", 11) # Volver a fuente normal
    p.drawString(100, y_info - 100, f"Fecha/Hora: {datos['Fecha']}")
    p.line(100, y_info - 110, 510, y_info - 110)

    # 4. FOTO Y FIRMA (Centradas en columna)
    if imagen_foto is not None:
        img_foto = Image.open(imagen_foto)
        p.drawImage(ImageReader(img_foto), (width/2)-90, 240, width=180, height=135, preserveAspectRatio=True)

    if imagen_firma is not None:
        try:
            img_f = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
            p.drawImage(ImageReader(img_f), (width/2)-75, 150, width=150, height=70, mask='auto')
        except:
            pass
    
    p.line((width/2)-80, 150, (width/2)+80, 150)
    p.setFont("Helvetica-Oblique", 10)
    p.drawCentredString(width/2, 135, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# INTERFAZ DE STREAMLIT (LOGO FIJO Y ALINEADO)
# =============================================================================

# CSS para asegurar que las columnas de logos se alineen por el centro verticalmente
st.markdown(
    """
    <style>
    [data-testid="stHorizontalBlock"] {
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# BANNER SUPERIOR (Fuera de los pasos para que no desaparezca)
col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
with col_logo1:
    if os.path.exists("logo_campofert.png"):
        st.image(Image.open("logo_campofert.png"), width=160)
with col_logo3:
    if os.path.exists("logo_campolab.png"):
        st.image(Image.open("logo_campolab.png"), width=160)

st.markdown("<h1 style='text-align: center;'>Registro de Capacitación</h1>", unsafe_allow_html=True)
st.markdown("---")

# =============================================================================
# LÓGICA DE PASOS
# =============================================================================

params = st.query_params
tema_actual = (params.get("tema") or "CAPACITACIÓN GENERAL").replace("+", " ").upper()
st.info(f"📋 **TEMA ACTUAL:** {tema_actual}")

if 'paso' not in st.session_state:
    st.session_state.paso = 1

df_maestro = obtener_datos()

if st.session_state.paso == 1:
    cedula = st.text_input("Por favor, ingresa tu Cédula:").strip()
    if cedula:
        # Intentamos buscar en el Excel local
        res = df_maestro[df_maestro['ID'].astype(str) == cedula] if df_maestro is not None else pd.DataFrame()
        
        if not res.empty:
            # CASO 1: El empleado existe en la base de datos
            st.session_state.persona = res.iloc[0].to_dict()
            st.session_state.cedula = cedula
            st.success(f"Hola, {st.session_state.persona['Apellidos y Nombres']}. ¡Bienvenido!")
            if st.button("Continuar al registro ➡️"):
                st.session_state.paso = 2
                st.rerun()
        else:
            # CASO 2: El empleado NO existe - Mostramos formulario de registro
            st.warning("⚠️ Cédula no encontrada. Si eres nuevo, regístrate a continuación:")
            
            # Usamos un formulario para agrupar los datos del nuevo empleado
            with st.form("registro_nuevo_empleado"):
                nombre_nuevo = st.text_input("Nombres y Apellidos Completos:")
                empresa_nueva = st.selectbox("Selecciona tu Empresa:", ["CAMPOFERT", "CAMPOLAB"])
                cargo_nuevo = st.text_input("Tu Cargo:")
                
                boton_registro = st.form_submit_button("Registrarme y Continuar ➡️")
                
                if boton_registro:
                    if nombre_nuevo and cargo_nuevo:
                        # Guardamos los datos manualmente en la sesión
                        st.session_state.persona = {
                            'Apellidos y Nombres': nombre_nuevo.upper(),
                            'Empresa': empresa_nueva,
                            'Cargo': cargo_nuevo.upper()
                        }
                        st.session_state.cedula = cedula
                        st.session_state.paso = 2
                        st.rerun()
                    else:
                        st.error("Por favor, completa todos los campos para poder continuar.")

elif st.session_state.paso == 2:
    st.subheader("📸 Captura de Identidad")
    foto = st.camera_input("Foto de validación")
    if foto:
        st.session_state.foto_data = foto
        if st.button("Ir a la firma ✍️"):
            st.session_state.paso = 3
            st.rerun()

elif st.session_state.paso == 3:
    st.subheader("✍️ Firma Digital")
    canvas_res = st_canvas(
        stroke_width=3, stroke_color="#000000", background_color="#ffffff", 
        height=180, width=350, key="firma_final"
    )
    
    # Asegúrate de que este 'if' tenga exactamente 4 espacios desde el margen del 'elif'
    if st.button("Finalizar y Generar Certificado ✅"):
        if canvas_res.image_data is not None:
            # 1. Preparar Diccionario de Datos
            datos_asistencia = {
                "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M:%S"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona['Apellidos y Nombres'],
                "Empresa": st.session_state.persona['Empresa'],
                "Cargo": st.session_state.persona.get('Cargo', 'NO REGISTRA'),
                "Tema": tema_actual
            }
            
            # 2. Guardar en Google Sheets
            if guardar_en_google_sheets(datos_asistencia):
                # 3. Generar PDF (incluyendo la foto si la capturaste)
                pdf = generar_pdf(datos_asistencia, canvas_res.image_data, st.session_state.get('foto_data'))
                
                # 4. Enviar Respaldo
                enviar_respaldo_gestion_humana(datos_asistencia, pdf)
                
                # 5. Preparar descarga y saltar al paso final
                pdf.seek(0) 
                st.session_state.pdf_doc = pdf
                st.session_state.paso = 4
                st.rerun()
        else:
            st.error("Es necesario firmar para completar el proceso.")

elif st.session_state.paso == 4:
    st.balloons()
    st.success("¡Tu asistencia ha sido registrada correctamente!")
    
    # Verificación de seguridad para el botón de descarga
    if st.session_state.get('pdf_doc'):
        st.download_button(
            label="📥 Descargar mi Certificado (PDF)",
            data=st.session_state.pdf_doc.getvalue(),
            file_name=f"Certificado_{st.session_state.cedula}.pdf",
            mime="application/pdf"
        )
    
    if st.button("Realizar otro registro"):
        # Limpiamos datos sensibles antes de reiniciar
        keys_to_reset = ['cedula', 'persona', 'pdf_doc', 'foto_data', 'finalizado']
        for key in keys_to_reset:
            if key in st.session_state:
                del st.session_state[key]
        
        st.session_state.paso = 1
        st.rerun()
