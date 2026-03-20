import streamlit as st
import pandas as pd
import os
import io
import base64
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
        # 1. Llamamos a la conexión sin pasarle la URL (ya está en Secrets)
        # Esto evita el error de "Spreadsheet must be specified"
        conn = st.connection("gsheets", type=GSheetsConnection)
        
        # 2. Leemos la pestaña "Hoja" (Asegúrate que se llame así en el Excel)
        # El parámetro ttl=0 fuerza a traer los datos reales, no de memoria
        df_existente = conn.read(worksheet="Hoja", ttl=0) 
        
        # 3. Preparamos y unimos los datos
        df_nuevo = pd.DataFrame([datos])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        
        # 4. Actualizamos la nube
        conn.update(worksheet="Hoja", data=df_final)
        return True
    
    except Exception as e:
        # Este mensaje nos dirá si el error cambió de 404 a otra cosa
        st.error(f"Error de conexión: {e}")
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
    width, height = letter

    # --- AQUÍ PEGAS LOS CÓDIGOS LARGOS DE LA PÁGINA ---
    # Asegúrate de que el texto empiece por "data:image/png;base64,..."
    
    logo_campofert_64 = """data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAOEAAADhCAMAAAAJbSJIAAAA51BMVEX///8YVjP+zwqUyD2PxS7V6bgRUy/+zAAARxkASR09bFAATicASyETVDDa497i6eWsvrOHoJFJdFrv8/EKVS+l0WFxj31ghG73+vgoYECpu7AARRTq7+wATybK1c7T3de5yL9pinZSemLs9d8APgCXrJ97mIbE0cn2+u+QxjP/9tj/++3//vj+44mQqJkyZkj/+eP+3m3/77z+1DL/7LD+5pT+4oL+2VL/88vF4Jy93I4ANQD/8b7+10T+4Hb+21/+2Ev/6J/k8dKy13rQ5q+czE3C35ep02may0fv9+Tb7MO02H+Iwhcr19rBAAAMVklEQVR4nO2ceZ+aOhfHxbaYCIgiVRZRpKLtzFTaznR7bm+n271dbt//63myAWFxQZ0B+8nvn46QQL6ck3OSENpqCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCTVQly8uPry7eHFVdzvuQpcfXt9etztU7fbfH28u6m7SKfXi9TXh4oV+3978Gca8urnO0yWU7Zfnb8nL5+0NeAzy+kPdTTxOrzeZj2d8V3crD9er7fZLGG8v627pYbq63YuP6Kbuxh6ii/0MyMz4su7mVtdNBT6MeH1unvq8GiDWeSWON9UB251zQvx4AOBZIR7golQv6m75nqoYZHidx0D14nDA9qe6G7+XDudDXfF13a3fQ4dFmQSx+dHm3VGA7fZ13QA7dRwfMuLnugl26PORJkRq9vDt6mi+dudN3RBb9fp4E7Y7jU6Kx/M1PGO8OoEJkerG2KK3JwHsNHfh5vI0Jmzf1g2yUUcMubOqG2Sjbk8E2Fw3PRFgu/O8bpINOmbalNWnulE26GTdsLEd8ZDlp3J1GrqccapA09xQczLAxk6hTkjY0KHp6QJNU2dQb3a/LNxXDSVsXX7++zSQTUr5zrhv8b/JpoQj8TrXz5szCdYXigrHfgbyYser++107Zc3jVqo6QFJkmSojFaZwxdvDoDsdDq3nwup3prcG0ypCKEkaQr0ltPMmXcvK0F2On+/LqR5axYa7iK8N5oyMUIsBdiDHn/u6tXb/bokKvXxVcE1dWesAUWWZOP+cErEEWJLulGo86cvbz7tgCRbowquOfSXtqsqGr5qkwgxpAe7zpAvcfl5c3DFrll8TzFbd1VI6RpIiFukglxwLc0gKCe8+VBwzZ4z9rBr8tdrHCGB9ObbgitxzQLd0B9JQJULF2siIY470MwH148EEuWEt58LrmlNB13AueYZEOK4A8zBLFP6w8v29fPi1K8XBhAqBeM1nhBDeiBaZ4JrYTQ26c8l4G2iazyhRDOIs2FYMlwNkpxwvoTYWRe2U6yJhiteecc7J0JNUV176Q/ztfT+PJ8TzpFQVoAyd/R8DTxcgaqyH11zCdHQBgbhrFB8ujY25IRzIkSuCaPByioUdYL9XbO5hLIHzJFfiJ0Tf4SiplmZrmGEOMUHYS9fBA1XIrAzJzSeEEfNaDAtumYYeHBrQj8LQjSbsEfFnDDBOeE4uiYQugpQx07RNVeDqFJOaC5hFE4LB2dh4B7pms0hLEh3xvIhOeE8CPnVldNJaQihNV13YdXhylZpsoLGDlCJRnWztUpXV45FA67Zna/7U72QgO5dk/LVlcPQPBUCxQ5GoT8rJJ+apEcncE1mNNceD5xVA4yWUc89Cs1EPQ1A28BGq/n9xCbtnuNvNBoEnoSN1muY0XKqSIjRkNFMAweR3UZ7+uTXt/99/34PHJu1L6FGIr9nG8twtUcQefrl0fuvjx88fPjw2bNnj++BY7N2EcaRP5oP+nsEEWK0r/88I2gPqJpKiNA83NOMedjfI4g8/fLr/X+Pfzzk0RpKSIOIC+xgiYLITn+8+vnl0b9fHz8rIWscITUalLpVgsiDMqM1jVCTZRz5gRksQ3+30Vo/kyCyC60hhAuzO14708KyaEFPf2Kj/fi9N1lDCK3J7viIjIaCyLau1mTCLUJB5Nu/KPL/PpCswYQ0iPxzsNGaS3hF/bFCEDkbwqsnyB9PZ7RmET59/9/30pHIH0P45PfdoTWE8OEd8wlCQSgIBWHr5++7J6x3naZ154APHn6rl/DXXRvx2Y96AVutR3iwdod6/LRuwtbVr0d3qCd14wkJCd2hrMlstsfa4B0LNaJaG/QZ1h7l1oanQghVbezUSNm3IYBqVLL9dqOWCwjBYlebp4Ebv5PXZBWOdq+F3o1Cl7xcVroV6gw8VANuJ7TGbvalvOIOjmvpgRqy18uV9tPsQTgzi1u1VLuON9C+yl48npbQd9m2A1nBin+APTrvqRXixmr2aBxUqLSTcMY8QwHRIAzXcw9Sj9VqQFxjZ4IVg8AuwiH7Hg4MYrdcGQAfks37DzcDTKhWDOWUcPO7lDnpg4rNb6b0PVmStbQjWhP2MkbHQscn7F+k4YTvsElJdIIUpr8menmrs8eHkyVujNfTs4f17Ksgcl1SG5WydFpJzVVKRTfHyFH2EUxsVYrLW2FXdV01CtEB4ALg2q2Wjf+N0M3XEXRdc84ej4NLeoZPfywAAH8hT/cD03WBPco5veXg464ZJB+GjxY04gGwWGYLqdEyrY0u5gLk0ehE1+r/BZJK5Z/WEhNqZh7fCuIjjke3d6Es6bQk5L4yylVdmUR0h+6N0hQXZ+iVxkoCA1fu47gIdD0CMis05+/gKCo9bqoKa9oyCekKS1aOSQvh/eRG7GWmhprRMlQNN4FGXxr+S4cJlkf4/VJ6clc33d8FlhFPGAzSF/puv9VPSyp2TKiE3PY3xU4f5Bik19UgeSRFwjlXSJLRPRLCaImvrvZ3E66gRNu8CRBKnIjFYkL0XLlT0Of3L6gDRihlMq0sxQ7ZzWZghfSJPGHAWq8xTteJCfGl8AFrNyEJz+WnsFizFRWkWxETQvw3GkSyZnnElYBKncqzGKFENr0Dtv1bGdPrBuynGu8LVyJMyPqhCkk/JGaSTAhME9AM5k4TQnRD4KKs2V/ApFJpPxxvTUAWaa8G5n6v5wegQKgGK302SkjMsKf3bXIKThNCGODazOFcH1/XAZR81Pf7S0+Jrd6bjUgsXU2nqM9NXVqbUK0iEi+klBAiHhzVp2mlUgzSVGVTLnFUYo9pxqApoUp7y4A+RI2O84akZ6Mewgjj3jOjzoVtZRFvV7q0RUNqUHfSyuZDcg+4jtsyJ1nPiQmVdBfx9nyIgyN9Mhv53SROU8SEMBkeEyYpHgIRx1fWjDANYnQbDuixByfbyW0M8pgHWUKSxhQu/OJS5AERQpjm7+1jGnsb4QSHGWWZHiA+nRDC+NNtknES3imk7SWE8jitTZrvhYyIGxPqkLhAljAkpbl29yDrUNSGqc22E5KmehssTAIt97Bo41PC+KLUanE/J+1FTkQIIfcBuw6YVQrxe4y//wJ6hpAckyI7UUR6n08JtYh7clsJx/KWSIPbmDGw5XKE6RnidfjeRKQjIstTQv7G2GGQqSnpmjvheDQ48YQRDcqcJPYcMaHMTT62Ew62ZQs8l+EfFu1xScZPrEBZ4u9oLJMj9PjaBq01AzQUpSJJTfUzhFLpTnLcZwgh7/1bCf1tGX8HYTJLpeOzuF+dklBTcoKjqoRDMmYBq9KTxEs17kDGS/cihPzEo5KXkhhojHKaO1UJaUfUpHyssQKLRRp+HryClQn9tDYlG7FIw69TlEUaYvDMWD1WRUI6clByqwZo9tSNswX3gQ55HJUI+YiwjPs8zRZpjCbo+WxB/gRl7a5I2DJIVI4HGFR4BowXg2jGTz7Fy2b8vQglmPQ3ulqCLUUzftr5u2UZnzx6/vEmDaxKqLOxGExWMWZ0ZoNGyX3SSz3WS306z6hGKAGGOPW02Dkt8qfCpqCbRm1kgAuTVc3BYtw7jBDN61ggdrvL0AlHNps0a4sZC9nuuGzkvSehBIw+qs3mg9QhQvKsFHXgz/xBOvLOEvqkXarhT1qW7tgqauB4toNwWvz0E2sdz+xkxVO9ZDXRm8W9tHz2tC8hP3tS2RDQyM+e2Cg1sxJFxtrIuaDiQTopg8FWQisInXHpMq/jFrOrQmcKYeYbp8wMeD/CzEw3Wei1ouwM2PQmRcL8NBm1ydpKuJ4a41X5l4szSc0ymiAeb4ccPRzZWkVCZQC5+kaSlKyAXzxQI/bkc6uJ48x3D2qXVt9IOBpG3Ql3IqMw/V9VNFlxjTQJrkwYrySF+ZWo3YRAn2l0fq7l3oWEgK1EISdOsn9+vdRRVTrfRaXcuNRGwrC/9ENuKpTTahR5LkDSjOx/EdRyDBN1JBvHWphbTWSE8bohJXTRycWcEaL41yf1o0FufG+F6LgLTCNMhxtLdCWXf1FmOYEEAYBSkL7yI9fn8yy5PT49X4fB1l32Q30265VtxLfilVudrcbqyaosrZeu/baSZeOEkKwTlwZzdN3s7SaZ66YHM+FDT5ej85UKde9UHOEfKkF4/nJcNJ9b1PAS8t60IvO5ujYECAkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQkJCQlV0v8B7A5BRIoRv3EAAAAASUVORK5CYII=""" # <--- AQUÍ
    
    logo_campolab_64 = """data:image/png;base64,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""" # <--- Y AQUÍ

    # --- FUNCIÓN PARA CONVERTIR EL TEXTO EN IMAGEN ---
    def dibujar_logo_64(b64_string, x, y, ancho):
        try:
            if "base64," in b64_string:
                b64_string = b64_string.split("base64,")[1]
            img_data = base64.b64decode(b64_string)
            img = Image.open(io.BytesIO(img_data))
            p.drawImage(ImageReader(img), x, y, width=ancho, preserveAspectRatio=True, mask='auto')
        except Exception as e:
            # Si algo falla con el código, no bloquea el PDF
            st.error(f"Error en logo Base64: {e}")

    # --- DIBUJAR LOS LOGOS ---
    dibujar_logo_64(logo_campofert_64, 50, 725, 100)
    dibujar_logo_64(logo_campolab_64, 460, 725, 100)

    # --- TÍTULOS ---
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width/2, 705, "CERTIFICADO DE ASISTENCIA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width/2, 685, "CAMPOFERT S.A.S / CAMPOLAB")

    # --- INFORMACIÓN ---
    p.setFont("Helvetica", 11)
    y_p = 630
    p.drawString(100, y_p, f"Participante: {datos['Nombre']}")
    p.drawString(100, y_p-20, f"Identificación: {datos['ID']}")
    p.drawString(100, y_p-40, f"Empresa: {datos['Empresa']}")
    p.drawString(100, y_p-60, f"Cargo: {datos['Cargo']}")
    p.drawString(100, y_p-80, f"Fecha: {datos['Fecha']}")
    
    p.line(100, y_p-90, 510, y_p-90)
    
    p.setFont("Helvetica-Bold", 12)
    p.drawString(100, y_p-110, f"Capacitación: {datos['Tema']}")

    # --- FIRMA ---
    p.setFont("Helvetica", 9)
    p.drawString(100, 420, "__________________________")
    p.drawString(100, 408, "Firma del Trabajador")
    
    if imagen_firma is not None:
        try:
            img_f = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
            p.drawImage(ImageReader(img_f), 100, 422, width=150, height=60, mask='auto')
        except:
            pass

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