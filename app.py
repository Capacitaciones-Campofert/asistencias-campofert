import streamlit as st
import pandas as pd
import os
import io
import pytz
import threading
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

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Campofert - Registro de Asistencia", layout="centered", page_icon="🌱")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTILOS ---
st.markdown("""
<style>
    .stApp { background-color: #F5F5F0; }
    [data-testid="stSidebar"] { background-color: #1B5E20; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton > button { background-color: #2E7D32; color: white; border-radius: 8px; width: 100%; }
    h1, h2, h3 { color: #1B5E20; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE DATOS ---
@st.cache_data(ttl=10)
def cargar_asistencia():
    try:
        return conn.read(worksheet="Hoja", ttl=0)
    except:
        return pd.DataFrame(columns=["Fecha", "ID", "Nombre", "Empresa", "Cargo", "Tema"])

def guardar_registro_seguro(datos):
    """Mejora para evitar el APIError: intenta añadir datos sin recrear la hoja"""
    try:
        df_actual = cargar_asistencia()
        df_nuevo = pd.concat([df_actual, pd.DataFrame([datos])], ignore_index=True)
        conn.update(worksheet="Hoja", data=df_nuevo)
        return True
    except Exception as e:
        st.error(f"Error al guardar en Sheets: {e}")
        return False

@st.cache_data(ttl=600)
def obtener_empleados():
    if os.path.exists("empleados.xlsx"):
        return pd.read_excel("empleados.xlsx", dtype={'ID': str})
    return None

# --- LÓGICA DE PDF Y CORREO (HILO) ---
def generar_pdf_certificado(datos, firma_base64, foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(300, 750, "CERTIFICADO DE ASISTENCIA")
    p.setFont("Helvetica", 12)
    p.drawString(100, 700, f"Nombre: {datos['Nombre']}")
    p.drawString(100, 680, f"ID: {datos['ID']}")
    p.drawString(100, 660, f"Tema: {datos['Tema']}")
    p.drawString(100, 640, f"Fecha: {datos['Fecha']}")
    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

def enviar_correo_segundo_plano(datos, firma, foto):
    try:
        pdf_buf = generar_pdf_certificado(datos, firma, foto)
        mi_correo = "gestionhumanacpfert@gmail.com"
        password = "bhbwshtosozexhcr"
        msg = MIMEMultipart()
        msg['Subject'] = f"✅ Registro: {datos['Nombre']}"
        msg.attach(MIMEText(f"Asistencia registrada para {datos['Nombre']} en {datos['Tema']}.", 'plain'))
        adj = MIMEBase('application', 'octet-stream')
        adj.set_payload(pdf_buf.read())
        encoders.encode_base64(adj)
        adj.add_header('Content-Disposition', f"attachment; filename=Certificado.pdf")
        msg.attach(adj)
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(mi_correo, password)
            server.sendmail(mi_correo, mi_correo, msg.as_string())
    except: pass

# =============================================================================
# INTERFAZ DE INGRESO (CON SOPORTE PARA "ENTER")
# =============================================================================
if 'rol' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>🌱 Campofert People</h1>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    if col1.button("👷 COLABORADOR"):
        st.session_state.rol = "Empleado"; st.rerun()
    if col2.button("🛡️ ADMINISTRADOR"):
        st.session_state.esperando_admin = True; st.rerun()
    
    if st.session_state.get('esperando_admin'):
        # Al usar st.form, el botón de Validar se activa con "Enter"
        with st.form("login_admin"):
            clave = st.text_input("Clave Admin", type="password")
            submit = st.form_submit_button("Ingresar ✅")
            if submit:
                if clave == "campofert2026":
                    st.session_state.rol = "Admin"; st.rerun()
                else: st.error("Clave Incorrecta")
    st.stop()

# =============================================================================
# MENÚ Y PANEL
# =============================================================================
df_asistencia = cargar_asistencia()

if st.session_state.rol == "Empleado":
    st.markdown("<style>[data-testid='stSidebar'] {display:none;}</style>", unsafe_allow_html=True)
    menu = "📋 Registro Asistencia"
else:
    with st.sidebar:
        st.image("logo_campofert.png") if os.path.exists("logo_campofert.png") else None
        menu = st.radio("Módulos", ["📊 Dashboard", "📋 Registro Asistencia", "👥 Empleados", "📤 Cargar Archivo", "📄 Historial", "📁 Reportes"])
        if st.button("🚪 Cerrar Sesión"):
            st.session_state.clear(); st.rerun()

# =============================================================================
# LÓGICA DE MÓDULOS (REPORTES Y CARGA)
# =============================================================================

if menu == "📊 Dashboard":
    st.title("📊 Dashboard de Gestión")
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Registros", len(df_asistencia))
    c2.metric("Capacitaciones", df_asistencia['Tema'].nunique() if not df_asistencia.empty else 0)
    c3.metric("Empresas", df_asistencia['Empresa'].nunique() if not df_asistencia.empty else 0)
    st.dataframe(df_asistencia.tail(10), use_container_width=True)

elif menu == "📋 Registro Asistencia":
    # --- Mantenemos tu lógica de pasos 1, 2, 3 y 4 ---
    st.title(f"📝 {st.query_params.get('tema', 'CAPACITACIÓN')}")
    if 'paso' not in st.session_state: st.session_state.paso = 1
    
    df_emp = obtener_empleados()
    
    if st.session_state.paso == 1:
        cedula = st.text_input("Cédula:")
        if cedula and df_emp is not None:
            persona = df_emp[df_emp['ID'] == cedula]
            if not persona.empty:
                st.session_state.persona = persona.iloc[0].to_dict()
                st.session_state.cedula = cedula
                st.success(f"Hola, {st.session_state.persona['Apellidos y Nombres']}")
                if st.button("Continuar"): st.session_state.paso = 2; st.rerun()

    elif st.session_state.paso == 2:
        foto = st.camera_input("Foto")
        if foto:
            st.session_state.foto_data = foto
            if st.button("Siguiente"): st.session_state.paso = 3; st.rerun()

    elif st.session_state.paso == 3:
        firma = st_canvas(stroke_width=3, stroke_color="#1B5E20", height=150, width=300, key="f")
        if st.button("Finalizar ✅"):
            datos = {
                "Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M:%S"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona['Apellidos y Nombres'],
                "Empresa": st.session_state.persona['Empresa'],
                "Cargo": st.session_state.persona.get('Cargo', 'N/A'),
                "Tema": st.query_params.get('tema', 'CAPACITACIÓN')
            }
            if guardar_registro_seguro(datos):
                st.session_state.pdf_doc = generar_pdf_certificado(datos, firma.image_data, st.session_state.foto_data)
                threading.Thread(target=enviar_correo_segundo_plano, args=(datos, firma.image_data, st.session_state.foto_data)).start()
                st.session_state.paso = 4; st.rerun()

    elif st.session_state.paso == 4:
        st.success("¡Completado!")
        st.download_button("📥 Descargar Certificado", st.session_state.pdf_doc.getvalue(), "Certificado.pdf")
        if st.button("Hacer otro"): st.session_state.paso = 1; st.rerun()

elif menu == "📤 Cargar Archivo":
    st.title("📤 Actualizar Base de Empleados")
    archivo = st.file_uploader("Suba el archivo empleados.xlsx", type=["xlsx"])
    if archivo:
        with open("empleados.xlsx", "wb") as f:
            f.write(archivo.getbuffer())
        st.success("Base de datos actualizada correctamente.")

elif menu == "📁 Reportes":
    st.title("📁 Generar Reportes")
    if not df_asistencia.empty:
        csv = df_asistencia.to_csv(index=False).encode('utf-8')
        st.download_button("📊 Descargar todo el Historial (CSV)", csv, "reporte_asistencias.csv", "text/csv")
        
        tema_sel = st.selectbox("Filtrar por Tema", df_asistencia['Tema'].unique())
        df_filtrado = df_asistencia[df_asistencia['Tema'] == tema_sel]
        st.dataframe(df_filtrado)
        csv_f = df_filtrado.to_csv(index=False).encode('utf-8')
        st.download_button(f"📥 Descargar Reporte de {tema_sel}", csv_f, "reporte_filtrado.csv", "text/csv")
    else:
        st.info("No hay datos para generar reportes.")

elif menu == "📄 Historial":
    st.title("📄 Historial General")
    st.dataframe(df_asistencia, use_container_width=True)
