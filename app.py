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

    # 1. LOGOS (Más GRANDES y VISIBLES, posición y=700)
    try:
        if os.path.exists("logo_campofert.png"):
            img_cf = Image.open("logo_campofert.png")
            # Aumentamos ancho a 130 y posición y=700
            p.drawImage(ImageReader(img_cf), 50, 700, width=130, preserveAspectRatio=True, mask='auto')
        
        if os.path.exists("logo_campolab.png"):
            img_cl = Image.open("logo_campolab.png")
            # Aumentamos ancho a 130 y posición y=700
            p.drawImage(ImageReader(img_cl), 430, 700, width=130, preserveAspectRatio=True, mask='auto')
    except:
        pass

    # 2. TÍTULOS (Subimos de 670 a 720 para dar más aire)
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 720, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 695, "CAMPOFERT S.A.S / CAMPOLAB")

    # 3. INFORMACIÓN DEL PARTICIPANTE
    p.setFont("Helvetica", 11)
    y_info = 610
    p.drawString(100, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(100, y_info - 20, f"Identificación: {datos['ID']}")
    p.drawString(100, y_info - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(100, y_info - 60, f"Cargo: {datos.get('Cargo', 'NO REGISTRA')}")
    p.drawString(100, y_info - 80, f"Tema: {datos['Tema']}")
    p.drawString(100, y_info - 100, f"Fecha/Hora: {datos['Fecha']}")
    p.line(100, y_info - 110, 510, y_info - 110)

    # 4. FOTO Y FIRMA (Una debajo de la otra, centradas)
    
    # --- LA FOTO ---
    if imagen_foto is not None:
        img_foto = Image.open(imagen_foto)
        # La centramos usando (width/2) - (ancho_imagen/2)
        p.drawImage(ImageReader(img_foto), (width/2)-90, 280, width=180, height=135, preserveAspectRatio=True)

    # --- LA FIRMA (Justo debajo de la foto) ---
    if imagen_firma is not None:
        try:
            img_f = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
            # La ponemos en y=200 para que quede debajo de la foto
            p.drawImage(ImageReader(img_f), (width/2)-75, 200, width=150, height=70, mask='auto')
        except:
            pass
    
    # Línea de firma y pie de página final
    p.line((width/2)-80, 200, (width/2)+80, 200)
    p.setFont("Helvetica-Oblique", 10)
    p.drawCentredString(width/2, 185, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# INTERFAZ DE LA APP
# =============================================================================

st.markdown("---")

# --- CSS PARA ALINEAR LOGOS ARRIBA ---
# Este bloque corrige la desalineación vertical que notaste.
st.markdown(
    """
    <style>
    [data-testid="stHorizontalBlock"] img {
        vertical-align: top;
    }
    </style>
    """,
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    if os.path.exists("logo_campofert.png"):
        # Cargamos con PIL y Image.open para asegurar nitidez (no pixelado)
        img_cf_ui = Image.open("logo_campofert.png")
        st.image(img_cf_ui, width=180)

with col3:
    if os.path.exists("logo_campolab.png"):
        # Cargamos con PIL para mantener calidad
        img_cl_ui = Image.open("logo_campolab.png")
        st.image(img_cl_ui, width=180)

st.markdown("<h1 style='text-align: center;'>Registro de Capacitación</h1>", unsafe_allow_html=True)
st.markdown("---")

# --- LÓGICA DE TEMA Y PASOS ---
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
        height=180, 
        width=350,
        key="firma_final"
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
            
            # ACCIÓN: Guardar en la nube (Google Sheets)
            if guardar_en_google_sheets(datos_asistencia):
                # Generar el PDF para la descarga
                pdf = generar_pdf(datos_asistencia, canvas_res.image_data, st.session_state.foto_data)
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
