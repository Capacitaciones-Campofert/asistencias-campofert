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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert - Sistema de Firmas", layout="centered", page_icon="🌱")

# --- FUNCIONES DE BASE DE DATOS ---
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

# --- FUNCIONES DE BASE DE DATOS (VERSIÓN SEGURA PARA LA NUBE) ---
def guardar_asistencia_segura(datos):
    """Guarda cada firma en un archivo CSV individual para evitar que el Excel se bloquee"""
    # 1. Creamos una carpeta para los registros si no existe
    ruta_carpeta = "REGISTROS_TEMPORALES"
    if not os.path.exists(ruta_carpeta):
        os.makedirs(ruta_carpeta)
    
    # 2. Creamos un nombre único usando la Cédula + Fecha + Hora
    # Ejemplo: registro_1119888169_20260319_1450.csv
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"registro_{datos['ID']}_{timestamp}.csv"
    ruta_completa = os.path.join(ruta_carpeta, nombre_archivo)
    
    # 3. Guardamos solo esta fila en un archivo pequeñito
    df_fila = pd.DataFrame([datos])
    df_fila.to_csv(ruta_completa, index=False, encoding='utf-8-sig')
    
    return ruta_completa

# --- FUNCIONES DE ARCHIVOS (PDF Y AUTO-GUARDADO) ---
def generar_pdf(datos, imagen_firma):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Encabezado estilo corporativo
    p.setFont("Helvetica-Bold", 16)
    p.drawString(100, 750, "CERTIFICADO DE ASISTENCIA - CAMPOFERT")
    
    p.setFont("Helvetica", 12)
    p.drawString(100, 700, f"Participante: {datos['Nombre']}")
    p.drawString(100, 680, f"Identificación: {datos['ID']}")
    p.drawString(100, 660, f"Empresa: {datos['Empresa']}")
    p.drawString(100, 640, f"Cargo: {datos['Cargo']}")
    p.drawString(100, 620, f"Fecha de Registro: {datos['Fecha']}")
    
    p.line(100, 610, 500, 610)
    p.drawString(100, 590, "Capacitación: FORMACIÓN INTEGRAL Y SEGURIDAD")
    
    # Insertar Firma
    p.drawString(100, 465, "Firma del Trabajador")
    p.line(100, 480, 300, 480)
    
    img = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr.seek(0)
    p.drawImage(ImageReader(img_byte_arr), 100, 485, width=150, height=60, mask='auto')
    
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def guardar_pdf_en_servidor(pdf_buffer, id_empleado, nombre_empleado):
    ruta_carpeta = "CERTIFICADOS_RRHH"
    if not os.path.exists(ruta_carpeta):
        os.makedirs(ruta_carpeta)
    
    nombre_limpio = nombre_empleado.replace(" ", "_").strip()
    nombre_base = f"Asistencia_{id_empleado}_{nombre_limpio}"
    
    contador = 1
    nombre_archivo = f"{nombre_base}.pdf"
    ruta_completa = os.path.join(ruta_carpeta, nombre_archivo)
    
    while os.path.exists(ruta_completa):
        contador += 1
        nombre_archivo = f"{nombre_base} ({contador}).pdf"
        ruta_completa = os.path.join(ruta_carpeta, nombre_archivo)
    
    with open(ruta_completa, "wb") as f:
        f.write(pdf_buffer.getbuffer())
    return nombre_archivo

# --- FLUJO PRINCIPAL DE STREAMLIT ---
st.title("🌱 Registro de Capacitación Campofert")

df_maestro = obtener_datos()
empresas_lista = sorted(df_maestro['Empresa'].unique().tolist()) if df_maestro is not None else ["Campofert", "Campolab", "Temporal"]

# Manejo de estado de la aplicación
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
                "Cargo": persona['Cargo']
            }
        else:
            st.warning("ID no encontrado en la base de datos maestra.")
            if st.checkbox("¿Registrar como Invitado / Personal Nuevo?"):
                with st.form("form_invitado"):
                    n = st.text_input("Apellidos y Nombres completos:")
                    e = st.selectbox("Empresa:", empresas_lista)
                    c = st.text_input("Cargo:")
                    if st.form_submit_button("Validar Datos") and n and c:
                        datos_finales = {
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "ID": cedula_input, "Nombre": n, "Empresa": e, "Cargo": c
                        }

    if datos_finales:
        st.write("### Dibuja tu firma abajo")
        canvas_result = st_canvas(
            stroke_width=3, stroke_color="#1a3c55", background_color="#f0f2f6", 
            height=150, drawing_mode="freedraw", key="firma_pad"
        )

        if st.button("🚀 Confirmar Registro Final"):
            if canvas_result.image_data is not None:
                # 1. Guardar en Excel para consolidado de RRHH
                guardar_asistencia_segura(datos_finales)
                
                # 2. Generar PDF
                pdf_memoria = generar_pdf(datos_finales, canvas_result.image_data)
                
                # 3. Guardar copia automática en carpeta local con contador
                nombre_pdf = guardar_pdf_en_servidor(pdf_memoria, datos_finales['ID'], datos_finales['Nombre'])
                
                # Guardar en sesión para la pantalla final
                st.session_state.pdf_final = pdf_memoria
                st.session_state.archivo_nombre = nombre_pdf
                st.session_state.finalizado = True
                st.rerun()
            else:
                st.error("Por favor, dibuja tu firma antes de continuar.")

else:
    # --- PANTALLA DE ÉXITO ---
    st.balloons()
    st.success(f"¡Registro exitoso! El documento se guardó como: {st.session_state.archivo_nombre}")
    
    st.download_button(
        label="📥 Descargar copia del Certificado",
        data=st.session_state.pdf_final.getvalue(),
        file_name=st.session_state.archivo_nombre,
        mime="application/pdf"
    )
    
    if st.button("🔄 Siguiente Persona"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
