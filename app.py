import streamlit as st
import pandas as pd
import os
from datetime import datetime
from streamlit_drawable_canvas import st_canvas

# --- CONFIGURACIÓN Y CARGA ---
st.set_page_config(page_title="Campofert - Registro Multinómina", layout="centered")

def obtener_datos():
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            # Usamos openpyxl para leer el archivo maestro
            df = pd.read_excel(ruta, engine='openpyxl', dtype={'ID': str})
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            st.error(f"Error al leer el Excel: {e}")
            return None
    return None

def guardar_asistencia(datos):
    """Guarda los datos en un archivo acumulado sin borrar lo anterior"""
    ruta_log = "asistencias_acumuladas.xlsx"
    df_nuevo = pd.DataFrame([datos])
    
    if os.path.exists(ruta_log):
        df_existente = pd.read_excel(ruta_log, engine='openpyxl', dtype={'ID': str})
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        df_final.to_excel(ruta_log, index=False, engine='openpyxl')
    else:
        df_nuevo.to_excel(ruta_log, index=False, engine='openpyxl')

df_maestro = obtener_datos()
empresas_base = ["Campofert", "Campolab", "Temporal - Misión"]
empresas_lista = sorted(df_maestro['Empresa'].unique().tolist()) if df_maestro is not None else empresas_base

st.title("🌱 Sistema de Firmas - Capacitaciones")

# --- LÓGICA DE IDENTIFICACIÓN ---
cedula_input = st.text_input("Número de Identificación (ID):").strip()
datos_finales = None
es_invitado = False

if cedula_input:
    if df_maestro is not None:
        resultado = df_maestro[df_maestro['ID'] == cedula_input]
        
        if not resultado.empty:
            persona = resultado.iloc[0]
            st.success(f"✅ Usuario Encontrado: **{persona['Apellidos y Nombres']}**")
            datos_finales = {
                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "ID": cedula_input,
                "Nombre": persona['Apellidos y Nombres'],
                "Empresa": persona['Empresa'],
                "Cargo": persona['Cargo']
            }
        else:
            st.warning("⚠️ ID no encontrado.")
            es_invitado = st.checkbox("¿Eres personal nuevo o externo (Invitado)?")
            if es_invitado:
                with st.form("registro_invitado"):
                    nombre_inv = st.text_input("Apellidos y Nombres completos:")
                    empresa_inv = st.selectbox("Selecciona tu Empresa:", empresas_lista)
                    cargo_inv = st.text_input("Cargo actual:")
                    enviar_inv = st.form_submit_button("Validar Datos")
                    if enviar_inv and nombre_inv and cargo_inv:
                        datos_finales = {
                            "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                            "ID": cedula_input,
                            "Nombre": nombre_inv,
                            "Empresa": empresa_inv,
                            "Cargo": cargo_inv
                        }

# --- SECCIÓN DE FIRMA ---
if datos_finales:
    st.write("---")
    st.write(f"### Firma de Asistencia - {datos_finales['Nombre']}")
    
    canvas_result = st_canvas(
        stroke_width=3, stroke_color="#1a3c55", background_color="#f0f2f6",
        height=150, drawing_mode="freedraw", key="canvas_firma"
    )

    if st.button("Confirmar Registro"):
        if canvas_result.image_data is not None:
            # 1. Guardar en el Excel acumulado
            guardar_asistencia(datos_finales)
            st.balloons()
            st.success("¡Registro guardado en asistencias_acumuladas.xlsx!")
            st.write("Datos procesados:", datos_finales)
        else:
            st.error("Por favor, firma antes de confirmar.")