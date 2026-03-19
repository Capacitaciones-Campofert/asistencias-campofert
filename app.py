import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image
# Librería para la conexión a la nube
from streamlit_gsheets import GSheetsConnection

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert - Sistema de Firmas", layout="centered", page_icon="🌱")

# --- 1. CONEXIÓN A GOOGLE SHEETS ---
# Usa la URL que pegaste en Settings > Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. LEER TEMA DESDE EL URL ---
params = st.query_params
tema_raw = params.get("tema") or params.get("Tema") or "CAPACITACIÓN GENERAL"
tema_actual = tema_raw.replace("+", " ").upper()

# --- FUNCIONES DE BASE DE DATOS ---

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

def guardar_en_google_sheets(datos):
    try:
        # Fíjate que NO haya espacio después del 1: "Hoja 1"
        df_existente = conn.read(worksheet="Hoja") 
        
        df_nuevo = pd.DataFrame([datos])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        
        # Aquí también: "Hoja 1" sin espacios al final
        conn.update(worksheet="Hoja", data=df_final)
        return True
    except Exception as e:
        st.error(f"Error crítico al guardar en la nube: {e}")
        return False

def actualizar_excel_acumulado_local(datos):
    """Respaldo local en el servidor de Streamlit (opcional)"""
    ruta_excel = "asistencias_acumuladas.xlsx"
    df_nuevo = pd.DataFrame([datos])
    if os.path.exists(ruta_excel):
        df_existente = pd.read_excel(ruta_excel, dtype={'ID': str})
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
    else:
        df_final = df_nuevo
    df_final.to_excel(ruta_excel, index=False)

# --- FUNCIONES DE PDF CON LOGOS ---

def generar_pdf(datos, imagen_firma):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Agregar Logos (Campofert y Campolab)
    try:
        if os.path.exists("logo_campofert.png"):
            p.drawImage("logo_campofert.png", 70, 740, width=90, preserveAspectRatio=True, mask='auto')
        if os.path.exists("logo_campolab.png"):
            p.drawImage("logo_campolab.png", 450, 740, width=90, preserveAspectRatio=True, mask='auto')
    except:
        pass

    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(300, 710, "CERTIFICADO DE ASISTENCIA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(300, 690, "CAMPOFERT S.A.S / CAMPOLAB")
    
    p.drawString(100, 640, f"Participante: {datos['Nombre']}")
    p.drawString(100, 620, f"Identificación: {datos['ID']}")
    p.drawString(100, 600, f"Empresa: {datos['Empresa']}")
    p.drawString(100, 580, f"Cargo: {datos['Cargo']}")
    p.drawString(100, 560, f"Fecha: {datos['Fecha']}")
    
    p.line(100, 550, 500, 550)
    p.setFont("Helvetica-Bold", 13)
    p.drawString(100, 530, f"Capacitación: {datos['Tema']}")
    
    # Dibujar la firma del canvas
    p.setFont("Helvetica", 10)
    p.drawString(100, 420, "__________________________")
    p.drawString(100, 405, "Firma del Trabajador")
    
    img = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    p.drawImage(ImageReader(img_byte_arr), 100, 425, width=160, height=70, mask='auto')
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# --- INTERFAZ DE USUARIO ---

col_v1, col_v2, col_v3 = st.columns([2, 5, 2])
with col_v2:
    c1, c2 = st.columns(2, vertical_alignment="center")
    if os.path.exists("logo_campofert.png"):
        c1.image("logo_campofert.png", use_container_width=True)
    if os.path.exists("logo_campolab.png"):
        c2.image("logo_campolab.png", use_container_width=True)

st.title("Registro de Capacitación")
st.info(f"📋 Tema: **{tema_actual}**")

df_maestro = obtener_datos()
empresas_lista = sorted(df_maestro['Empresa'].unique().tolist()) if df_maestro is not None else ["Campofert", "Campolab"]

if 'finalizado' not in st.session_state:
    st.session_state.finalizado = False

if not st.session_state.finalizado:
    cedula_input = st.text_input("Ingresa tu ID / Cédula:").strip()
    datos_finales = None

    if cedula_input:
        resultado = df_maestro[df_maestro['ID'] == cedula_input] if df_maestro is not None else pd.DataFrame()
        if not resultado.empty:
            persona = resultado.iloc[0]
            st.success(f"✅ Usuario: {persona['Apellidos y Nombres']}")
            datos_finales = {
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ID": cedula_input,
                "Nombre": persona['Apellidos y Nombres'],
                "Empresa": persona['Empresa'],
                "Cargo": persona['Cargo'],
                "Tema": tema_actual
            }
        else:
            st.warning("ID no encontrado. ¿Eres invitado?")
            if st.checkbox("Registrar como Invitado"):
                with st.form("form_invitado"):
                    n = st.text_input("Nombre Completo:")
                    e = st.selectbox("Empresa:", empresas_lista)
                    c = st.text_input("Cargo:")
                    if st.form_submit_button("Validar") and n and c:
                        datos_finales = {
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "ID": cedula_input,
                            "Nombre": n,
                            "Empresa": e,
                            "Cargo": c,
                            "Tema": tema_actual
                        }

    if datos_finales:
        st.write("### Firma aquí")
        canvas_result = st_canvas(stroke_width=3, stroke_color="#1a3c55", background_color="#f0f2f6", height=150, drawing_mode="freedraw", key="firma_pad")
        
        if st.button("🚀 Confirmar Registro"):
            if canvas_result.image_data is not None:
                # 1. GUARDAR EN LA NUBE (OBLIGATORIO)
                exito = guardar_en_google_sheets(datos_finales) # <--- CORREGIDO AQUÍ
                
                if exito:
                    # 2. Generar PDF
                    pdf_memoria = generar_pdf(datos_finales, canvas_result.image_data)
                    st.session_state.pdf_final = pdf_memoria
                    st.session_state.archivo_nombre = f"Asistencia_{datos_finales['ID']}.pdf"
                    st.session_state.finalizado = True
                    st.rerun()
            else:
                st.error("Por favor, firma antes de continuar.")

else:
    st.balloons()
    st.success("¡Registro guardado exitosamente en la nube de Campofert!")
    st.download_button(label="📥 Descargar Certificado (PDF)", data=st.session_state.pdf_final.getvalue(), file_name=st.session_state.archivo_nombre, mime="application/pdf")
    
    if st.button("🔄 Registrar otra persona"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()