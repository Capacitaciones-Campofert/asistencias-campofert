import streamlit as st
import pandas as pd
import os, io, pytz, smtplib
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image
from streamlit_gsheets import GSheetsConnection
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

st.set_page_config(page_title='Campofert - Registro de Asistencia', layout='centered', page_icon='🌱')
conn = st.connection('gsheets', type=GSheetsConnection)
EMAIL_USER = 'gestionhumanacpfert@gmail.com'
EMAIL_PASS = st.secrets.get('email_password', '')


def obtener_datos():
    try:
        df = conn.read(worksheet='Empleados', ttl=0)
        df.columns = df.columns.str.strip()
        if 'ID' in df.columns:
            df['ID'] = df['ID'].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"No se pudo conectar con la pestaña 'Empleados': {e}")
        return pd.DataFrame()


def guardar_en_google_sheets(datos):
    try:
        try:
            df_existente = conn.read(worksheet='Hoja', ttl=0)
        except:
            df_existente = pd.DataFrame()
        df_nuevo = pd.DataFrame([datos])
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        conn.update(worksheet='Hoja', data=df_final)
        return True
    except Exception as e:
        st.error(f'Error guardando en Google Sheets: {e}')
        return False


def generar_pdf(datos, firma, foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    p.setFont('Helvetica-Bold', 16)
    p.drawCentredString(w/2, 750, 'CERTIFICADO DE ASISTENCIA')
    p.setFont('Helvetica', 11)
    y = 700
    for t in [f"Nombre: {datos['Nombre']}", f"ID: {datos['ID']}", f"Empresa: {datos['Empresa']}", f"Cargo: {datos['Cargo']}", f"Tema: {datos['Tema']}", f"Fecha: {datos['Fecha']}"]:
        p.drawString(60, y, t)
        y -= 22
    if foto is not None:
        try:
            img = Image.open(foto)
            p.drawImage(ImageReader(img), 200, 380, width=180, height=135)
        except:
            pass
    if firma is not None:
        try:
            imgf = Image.fromarray(firma.astype('uint8'), 'RGBA')
            p.drawImage(ImageReader(imgf), 220, 250, width=140, height=60, mask='auto')
        except:
            pass
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer


def enviar_correo(datos, pdf):
    if not EMAIL_PASS:
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = EMAIL_USER
        msg['Subject'] = f"Nueva Asistencia {datos['Nombre']}"
        msg.attach(MIMEText('Adjunto certificado.', 'plain'))
        pdf.seek(0)
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename=certificado.pdf')
        msg.attach(part)
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, EMAIL_USER, msg.as_string())
        server.quit()
        return True
    except:
        return False

params = st.query_params
tema = (params.get('tema') or 'CAPACITACIÓN GENERAL').replace('+', ' ').upper()

if 'paso' not in st.session_state:
    st.session_state.paso = 1

st.title('Registro de Capacitación')
st.info(f'Tema actual: {tema}')

df_maestro = obtener_datos()

if st.session_state.paso == 1:
    cedula = st.text_input('Ingresa tu cédula').strip()
    if cedula:
        res = pd.DataFrame()
        if not df_maestro.empty and 'ID' in df_maestro.columns:
            res = df_maestro[df_maestro['ID'] == cedula]
        if not res.empty:
            persona = res.iloc[0].to_dict()
            st.session_state.persona = persona
            st.session_state.cedula = cedula
            st.success(f"Hola {persona.get('Apellidos y Nombres','Usuario')}")
            if st.button('Continuar'):
                st.session_state.paso = 2
                st.rerun()
        else:
            st.warning('No encontrado. Registro como invitado.')
            nombre = st.text_input('Nombre completo')
            empresa = st.selectbox('Empresa', ['Campofert','Campolab','Invitado'])
            cargo = st.text_input('Cargo')
            if st.button('Continuar como invitado') and nombre:
                st.session_state.persona = {'Apellidos y Nombres': nombre, 'Empresa': empresa, 'Cargo': cargo}
                st.session_state.cedula = cedula
                st.session_state.paso = 2
                st.rerun()

elif st.session_state.paso == 2:
    foto = st.camera_input('Tomar foto')
    if foto:
        st.session_state.foto = foto
        if st.button('Ir a firma'):
            st.session_state.paso = 3
            st.rerun()

elif st.session_state.paso == 3:
    canvas_res = st_canvas(stroke_width=3, stroke_color='#000', background_color='#fff', height=180, width=350, key='firma')
    if st.button('Finalizar'):
        if canvas_res.image_data is not None:
            datos = {
                'Fecha': datetime.now(pytz.timezone('America/Bogota')).strftime('%d/%m/%Y %H:%M:%S'),
                'ID': st.session_state.cedula,
                'Nombre': st.session_state.persona['Apellidos y Nombres'],
                'Empresa': st.session_state.persona['Empresa'],
                'Cargo': st.session_state.persona.get('Cargo','NO REGISTRA'),
                'Tema': tema
            }
            if guardar_en_google_sheets(datos):
                pdf = generar_pdf(datos, canvas_res.image_data, st.session_state.get('foto'))
                enviar_correo(datos, pdf)
                st.session_state.pdf = pdf
                st.session_state.paso = 4
                st.rerun()
        else:
            st.error('Debes firmar.')

elif st.session_state.paso == 4:
    st.success('Registro exitoso')
    st.download_button('Descargar PDF', data=st.session_state.pdf.getvalue(), file_name='certificado.pdf', mime='application/pdf')
    if st.button('Nuevo registro'):
        st.session_state.clear()
        st.rerun()
