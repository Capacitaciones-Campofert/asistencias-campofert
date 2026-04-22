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
# GENERACIÓN DE PDF (DISEÑO DE ALTA CALIDAD)
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # 1. Logos en el PDF con escalado de alta calidad
    try:
        # Usamos un ancho proporcional que se vea nítido en impresión (aprox 1.5 - 2 pulgadas)
        if os.path.exists("logo_campofert.png"):
            p.drawImage("logo_campofert.png", 50, 710, width=110, preserveAspectRatio=True, mask='auto')
        if os.path.exists("logo_campolab.png"):
            p.drawImage("logo_campolab.png", 450, 710, width=110, preserveAspectRatio=True, mask='auto')
    except:
        pass

    # 2. Títulos
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 690, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 670, "CAMPOFERT S.A.S / CAMPOLAB")

    # 3. Información
    p.setFont("Helvetica", 11)
    y = 610
    p.drawString(70, y,      f"Participante: {datos['Nombre']}")
    p.drawString(70, y - 20, f"Identificación: {datos['ID']}")
    p.drawString(70, y - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(70, y - 60, f"Tema: {datos['Tema']}")
    p.drawString(70, y - 80, f"Fecha/Hora: {datos['Fecha']}")
    p.line(70, y - 90, 530, y - 90)

    # 4. Foto de Identidad
    if imagen_foto is not None:
        img_foto = Image.open(imagen_foto)
        p.drawImage(ImageReader(img_foto), (width/2)-100, 280, width=200, height=150, preserveAspectRatio=True)

    # 5. Pie de Firma centrado debajo de la foto
    if imagen_firma is not None:
        img_firma = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
        p.drawImage(ImageReader(img_firma), (width/2)-60, 190, width=120, height=60, mask='auto')
    
    p.line((width/2)-80, 195, (width/2)+80, 195)
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(width / 2, 180, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# INTERFAZ DE LA APP (LOGOS VISIBLES Y NÍTIDOS)
# =============================================================================

# Diseño de encabezado con logos más grandes y centrados
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if os.path.exists("logo_campofert.png"):
        # Usamos use_container_width=True para que el navegador maneje la resolución
        st.image("logo_campofert.png", width=180)

with col3:
    if os.path.exists("logo_campolab.png"):
        st.image("logo_campolab.png", width=180)

st.markdown("<h1 style='text-align: center;'>Registro de Capacitación</h1>", unsafe_allow_html=True)
st.markdown("---")

# Lógica de Tema
params = st.query_params
tema_actual = (params.get("tema") or "CAPACITACIÓN GENERAL").replace("+", " ").upper()
st.info(f"📋 **TEMA ACTUAL:** {tema_actual}")

if 'paso' not in st.session_state:
    st.session_state.paso = 1

df_maestro = obtener_datos()

if st.session_state.paso == 1:
    cedula = st.text_input("Por favor, ingresa tu Cédula:").strip()
    if cedula:
        res = df_maestro[df_maestro['ID'] == cedula] if df_maestro is not None else pd.DataFrame()
        if not res.empty:
            st.session_state.persona = res.iloc[0]
            st.session_state.cedula = cedula
            st.success(f"Hola, {st.session_state.persona['Apellidos y Nombres']}. ¡Bienvenido!")
            if st.button("Continuar al registro ➡️"):
                st.session_state.paso = 2
                st.rerun()
        else:
            st.error("Cédula no encontrada en la base de datos.")

elif st.session_state.paso == 2:
    st.subheader("📸 Captura de Identidad")
    st.write("Colócate frente a la cámara para validar tu asistencia.")
    foto = st.camera_input("Foto de validación")
    if foto:
        st.session_state.foto_data = foto
        if st.button("Ir a la firma ✍️"):
            st.session_state.paso = 3
            st.rerun()

elif st.session_state.paso == 3:
    st.subheader("✍️ Firma Digital")
    st.write("Firma dentro del recuadro blanco:")
    canvas_res = st_canvas(
        stroke_width=3, 
        stroke_color="#000000", 
        background_color="#ffffff", 
        height=200, 
        width=400,
        key="firma_final"
    )
    
    if st.button("Finalizar y Generar Certificado ✅"):
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
            st.error("Es necesario firmar para completar el proceso.")

elif st.session_state.paso == 4:
    st.balloons()
    st.success("¡Tu asistencia ha sido registrada correctamente!")
    st.download_button(
        label="📥 Descargar mi Certificado (PDF)",
        data=st.session_state.pdf_doc.getvalue(),
        file_name=f"Certificado_{st.session_state.cedula}.pdf",
        mime="application/pdf"
    )
    if st.button("Realizar otro registro"):
        st.session_state.paso = 1
        st.rerun()
