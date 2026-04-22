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
# GENERACIÓN DE PDF (DISEÑO CORREGIDO PARA LOGOS)
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # 1. LOGOS (Bajamos la posición Y a 700 para que no se corten)
    try:
        if os.path.exists("logo_campofert.png"):
            img_cf = Image.open("logo_campofert.png")
            p.drawImage(ImageReader(img_cf), 50, 700, width=110, preserveAspectRatio=True, mask='auto')
        
        if os.path.exists("logo_campolab.png"):
            img_cl = Image.open("logo_campolab.png")
            p.drawImage(ImageReader(img_cl), 450, 700, width=110, preserveAspectRatio=True, mask='auto')
    except:
        pass

    # 2. TÍTULOS (Bajamos su posición para dar espacio a los logos)
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 670, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 650, "CAMPOFERT S.A.S / CAMPOLAB")

    # 3. INFORMACIÓN
    p.setFont("Helvetica", 11)
    y_info = 590
    p.drawString(70, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(70, y_info - 20, f"Identificación: {datos['ID']}")
    p.drawString(70, y_info - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(70, y_info - 60, f"Tema: {datos['Tema']}")
    p.drawString(70, y_info - 80, f"Fecha/Hora: {datos['Fecha']}")
    p.line(70, y_info - 90, 530, y_info - 90)

    # 4. EVIDENCIAS (Organizadas en columnas)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(70, 480, "EVIDENCIA FOTOGRÁFICA (IDENTIDAD):")
    p.drawString(350, 480, "FIRMA DEL TRABAJADOR:")

    # Foto
    if imagen_foto is not None:
        img_foto = Image.open(imagen_foto)
        p.drawImage(ImageReader(img_foto), 70, 320, width=180, height=140, preserveAspectRatio=True)

    # Firma
    if imagen_firma is not None:
        img_firma = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
        p.drawImage(ImageReader(img_firma), 350, 320, width=150, height=80, mask='auto')
    
    p.line(350, 315, 510, 315)
    p.setFont("Helvetica-Oblique", 9)
    p.drawString(350, 300, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# INTERFAZ DE LA APP
# =============================================================================

st.markdown("---")
# Usamos Image.open para que se vean nítidos en la web también
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if os.path.exists("logo_campofert.png"):
        st.image(Image.open("logo_campofert.png"), width=180)
with col3:
    if os.path.exists("logo_campolab.png"):
        st.image(Image.open("logo_campolab.png"), width=180)

st.markdown("<h1 style='text-align: center;'>Registro de Capacitación</h1>", unsafe_allow_html=True)
st.markdown("---")

# Lógica de Tema y Pasos
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
            st.success(f"Hola, {st.session_state.persona['Apellidos y Nombres']}.")
            if st.button("Continuar al registro ➡️"):
                st.session_state.paso = 2
                st.rerun()
        else:
            st.error("Cédula no encontrada.")

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
    canvas_res = st_canvas(stroke_width=3, stroke_color="#000000", background_color="#ffffff", height=180, width=350, key="firma_final")
    
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
            
            if guardar_en_google_sheets(datos_asistencia):
                pdf = generar_pdf(datos_asistencia, canvas_res.image_data, st.session_state.foto_data)
                st.session_state.pdf_doc = pdf
                st.session_state.paso = 4
                st.rerun()
        else:
            st.error("Es necesario firmar.")

elif st.session_state.paso == 4:
    st.balloons()
    st.success("¡Tu asistencia ha sido registrada!")
    st.download_button(
        label="📥 Descargar Certificado (PDF)",
        data=st.session_state.pdf_doc.getvalue(),
        file_name=f"Certificado_{st.session_state.cedula}.pdf",
        mime="application/pdf"
    )
    if st.button("Realizar otro registro"):
        st.session_state.paso = 1
        st.rerun()
