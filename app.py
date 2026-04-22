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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert - Registro de Asistencia", layout="centered", page_icon="🌱")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# =============================================================================
# FUNCIONES DE APOYO
# =============================================================================

def obtener_datos():
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, engine='openpyxl', dtype={'ID': str})
            df.columns = df.columns.str.strip()
            return df
        except:
            return None
    return None

def guardar_en_google_sheets(datos):
    try:
        df_existente = conn.read(worksheet="Hoja", ttl=0)
        df_nuevo = pd.DataFrame([datos])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        conn.update(worksheet="Hoja", data=df_final)
        return True
    except:
        return False

# =============================================================================
# GENERACIÓN DE PDF (DISEÑO SOLICITADO)
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # 1. Logos en el PDF
    try:
        if os.path.exists("logo_campofert.png"):
            p.drawImage("logo_campofert.png", 50, 720, width=80, preserveAspectRatio=True)
        if os.path.exists("logo_campolab.png"):
            p.drawImage("logo_campolab.png", 470, 720, width=80, preserveAspectRatio=True)
    except:
        pass

    # 2. Títulos
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 700, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 680, "CAMPOFERT S.A.S / CAMPOLAB")

    # 3. Información
    p.setFont("Helvetica", 11)
    y = 630
    p.drawString(70, y,      f"Participante: {datos['Nombre']}")
    p.drawString(70, y - 20, f"Identificación: {datos['ID']}")
    p.drawString(70, y - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(70, y - 60, f"Tema: {datos['Tema']}")
    p.drawString(70, y - 80, f"Fecha/Hora: {datos['Fecha']}")
    p.line(70, y - 90, 530, y - 90)

    # 4. Foto (Sin palabra "evidencia")
    if imagen_foto is not None:
        img_foto = Image.open(imagen_foto)
        p.drawImage(ImageReader(img_foto), (width/2)-100, 300, width=200, height=150, preserveAspectRatio=True)

    # 5. Firma (Como pie de firma debajo de la foto)
    if imagen_firma is not None:
        img_firma = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
        p.drawImage(ImageReader(img_firma), (width/2)-60, 210, width=120, height=60, mask='auto')
    
    p.line((width/2)-80, 215, (width/2)+80, 215)
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(width / 2, 200, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# INTERFAZ DE LA APP (LOGOS AL COMIENZO)
# =============================================================================

# Mostramos los logos al inicio de la App
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    if os.path.exists("logo_campofert.png"):
        st.image("logo_campofert.png", width=100)
with col3:
    if os.path.exists("logo_campolab.png"):
        st.image("logo_campolab.png", width=100)

st.title("Registro de Capacitación")

# Lógica de Tema
params = st.query_params
tema_actual = (params.get("tema") or "CAPACITACIÓN GENERAL").replace("+", " ").upper()
st.info(f"📋 Tema: {tema_actual}")

if 'paso' not in st.session_state:
    st.session_state.paso = 1

df_maestro = obtener_datos()

if st.session_state.paso == 1:
    cedula = st.text_input("Ingresa tu Cédula:").strip()
    if cedula:
        res = df_maestro[df_maestro['ID'] == cedula] if df_maestro is not None else pd.DataFrame()
        if not res.empty:
            st.session_state.persona = res.iloc[0]
            st.session_state.cedula = cedula
            st.success(f"Bienvenido, {st.session_state.persona['Apellidos y Nombres']}")
            if st.button("Siguiente ➡️"):
                st.session_state.paso = 2
                st.rerun()
        else:
            st.error("ID no encontrado.")

elif st.session_state.paso == 2:
    st.subheader("📸 Paso 2: Foto de Identidad")
    foto = st.camera_input("Captura tu rostro")
    if foto:
        st.session_state.foto_data = foto
        if st.button("Continuar a Firma ➡️"):
            st.session_state.paso = 3
            st.rerun()

elif st.session_state.paso == 3:
    st.subheader("✍️ Paso 3: Firma")
    canvas_res = st_canvas(stroke_width=3, stroke_color="#000000", background_color="#ffffff", height=150, key="f")
    
    if st.button("Finalizar Registro ✅"):
        if canvas_res.image_data is not None:
            datos = {
                "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona['Apellidos y Nombres'],
                "Empresa": st.session_state.persona['Empresa'],
                "Tema": tema_actual
            }
            if guardar_en_google_sheets(datos):
                pdf = generar_pdf(datos, canvas_res.image_data, st.session_state.foto_data)
                st.session_state.pdf_doc = pdf
                st.session_state.paso = 4
                st.rerun()
        else:
            st.error("Falta la firma.")

elif st.session_state.paso == 4:
    st.balloons()
    st.success("¡Registro Exitoso!")
    st.download_button("📥 Descargar Certificado", data=st.session_state.pdf_doc.getvalue(), file_name="Certificado.pdf", mime="application/pdf")
    if st.button("Hacer otro registro"):
        st.session_state.paso = 1
        st.rerun()
