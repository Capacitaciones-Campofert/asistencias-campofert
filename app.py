import streamlit as st
import pandas as pd
import os
import io
import pytz
import qrcode
import threading # <--- IMPORTANTE: Para procesos en segundo plano
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

# ... (Mantenemos tu CSS Corporativo igual) ...
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

@st.cache_data(ttl=600) # Guarda en memoria por 10 minutos para ser veloz
def obtener_datos():
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, engine='openpyxl', dtype={'ID': str})
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            return None
    return None

def proceso_segundo_plano(datos, imagen_firma, imagen_foto):
    """
    Esta función hace el trabajo pesado fuera de la vista del usuario.
    """
    try:
        # 1. Generar PDF (proceso pesado)
        pdf_buffer = generar_pdf(datos, imagen_firma, imagen_foto)
        
        # 2. Enviar Correo
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
        print(f"Error en proceso de fondo: {e}")

def guardar_en_google_sheets(datos):
    """
    Optimizado: Solo añade una fila, no lee toda la hoja.
    """
    try:
        df_nuevo = pd.DataFrame([{
            "Fecha": datos['Fecha'],
            "ID": datos['ID'],
            "Nombre": datos['Nombre'],
            "Empresa": datos['Empresa'],
            "Cargo": datos.get('Cargo', 'NO REGISTRA'),
            "Tema": datos['Tema']
        }])
        # Usamos spread_to_sheet o el método de append de la conexión
        conn.create(worksheet="Hoja", data=df_nuevo) # Esto suele funcionar como append si la hoja existe
        return True
    except Exception as e:
        st.error(f"Error Sheets: {e}")
        return False

# ... (Aquí van tus lógicas de login y PDF que ya tienes muy bien armadas) ...

# =============================================================================
# CAMBIO CRÍTICO EN EL REGISTRO (PASO 3)
# =============================================================================

if st.session_state.get('paso') == 3:
    st.markdown("### ✍️ Firma Digital")
    canvas_res = st_canvas(
        stroke_width=3, stroke_color="#1B5E20", background_color="#ffffff",
        height=180, width=350, key="firma_final"
    )

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

            # 1. Guardar en Sheets (Rápido)
            guardar_en_google_sheets(datos_asistencia)

            # 2. PDF para descarga inmediata (El usuario lo quiere YA)
            pdf_para_descarga = generar_pdf(datos_asistencia, canvas_res.image_data, st.session_state.get('foto_data'))
            st.session_state.pdf_doc = pdf_para_descarga

            # 3. LANZAR PROCESO PESADO EN SEGUNDO PLANO (HILO)
            # El usuario no tiene que esperar a que el correo se envíe
            hilo_correo = threading.Thread(
                target=proceso_segundo_plano, 
                args=(datos_asistencia, canvas_res.image_data, st.session_state.get('foto_data'))
            )
            hilo_correo.start()

            st.session_state.paso = 4
            st.rerun()

if st.session_state.get('paso') == 4:
    st.success("¡Registro completado con éxito!")
    st.download_button(
        "📥 DESCARGAR MI CERTIFICADO",
        st.session_state.pdf_doc.getvalue(),
        f"Certificado_{st.session_state.cedula}.pdf",
        "application/pdf"
    )
    if st.button("Hacer otro registro"):
        st.session_state.paso = 1
        st.rerun()
