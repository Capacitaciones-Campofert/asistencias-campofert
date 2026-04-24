import streamlit as st
import pandas as pd
import os
import io
import pytz
import threading
import urllib.parse
from datetime import datetime
from streamlit_drawable_canvas import st_canvas
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from PIL import Image, ImageDraw
from streamlit_gsheets import GSheetsConnection
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert - Registro de Asistencia", layout="centered", page_icon="🌱")

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- ESTILOS CORPORATIVOS ---
st.markdown("""
<style>
    .stApp { background-color: #F5F5F0; }
    [data-testid="stSidebar"] { background-color: #1B5E20; min-width: 250px; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton > button {
        background-color: #2E7D32; color: white; border: none;
        border-radius: 8px; font-weight: bold; padding: 0.6rem 1.2rem; width: 100%;
    }
    .stButton > button:hover { background-color: #F9A825; color: #1B5E20; }
    h1, h2, h3 { color: #1B5E20; font-family: 'Arial'; }
    .highlight-box { background-color: #E8F5E9; padding: 15px; border-radius: 10px; border-left: 5px solid #2E7D32; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- FUNCIONES DE CARGA ---
@st.cache_data(ttl=60)
def obtener_datos_empleados():
    if os.path.exists("empleados.xlsx"):
        df = pd.read_excel("empleados.xlsx", engine='openpyxl', dtype={'ID': str})
        df.columns = df.columns.str.strip()
        return df
    return None

def cargar_asistencias_google():
    try:
        return conn.read(worksheet="Hoja", ttl=0)
    except:
        return pd.DataFrame(columns=["Fecha", "ID", "Nombre", "Empresa", "Cargo", "Tema"])

# =============================================================================
# PDF MULTINACIONAL CAMPOFERT (SIN QR - OPTIMIZADO)
# =============================================================================
def generar_pdf_pro(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    verde_oscuro = (0.10, 0.36, 0.16)
    verde_claro = (0.18, 0.52, 0.24)
    dorado = (0.95, 0.74, 0.12)
    gris_fondo = (0.96, 0.96, 0.96)
    codigo_verif = f"CPF-2026-{datetime.now().strftime('%M%S')}"

    # Fondo y Borde
    p.setFillColorRGB(1, 1, 1); p.rect(0, 0, width, height, fill=1, stroke=0)
    p.setStrokeColorRGB(*verde_oscuro); p.setLineWidth(1.4); p.roundRect(20, 20, width-40, height-40, 14)

    # Cabecera
    p.setFillColorRGB(*verde_oscuro); p.roundRect(20, height-125, width-40, 105, 14, fill=1, stroke=0)
    p.setFillColorRGB(*dorado); p.rect(20, height-125, width-40, 5, fill=1, stroke=0)

    # Logos
    try:
        if os.path.exists("logo_campofert.png"):
            p.drawImage(ImageReader("logo_campofert.png"), 35, height-112, width=95, height=72, preserveAspectRatio=True, mask='auto')
        if os.path.exists("logo_campolab.png"):
            p.drawImage(ImageReader("logo_campolab.png"), width-130, height-112, width=95, height=72, preserveAspectRatio=True, mask='auto')
    except: pass

    # Títulos
    p.setFillColorRGB(1, 1, 1); p.setFont("Helvetica-Bold", 18); p.drawCentredString(width/2, height-63, "CERTIFICADO DE ASISTENCIA")
    p.setFont("Helvetica", 10); p.drawCentredString(width/2, height-84, "Sistema de Gestión Humana y Seguridad en el Trabajo")
    p.setFont("Helvetica-Bold", 8); p.drawRightString(width-35, height-38, f"VERIF: {codigo_verif}")

    # Cuerpo
    p.setFillColorRGB(0, 0, 0); p.setFont("Helvetica", 12); p.drawCentredString(width/2, 610, "Por medio del presente documento se certifica que:")
    p.setFillColorRGB(*verde_oscuro); p.setFont("Helvetica-Bold", 24); p.drawCentredString(width/2, 570, datos["Nombre"].upper())
    p.setFillColorRGB(0, 0, 0); p.setFont("Helvetica", 12); p.drawCentredString(width/2, 545, f"Identificado(a) con documento No. {datos['ID']}")

    # Cuadro Tema
    p.setFillColorRGB(*gris_fondo); p.roundRect(60, 445, width-120, 75, 10, fill=1, stroke=0)
    p.setFillColorRGB(*verde_oscuro); p.setFont("Helvetica-Bold", 11); p.drawString(80, 495, "CAPACITACIÓN / ACTIVIDAD:")
    p.setFillColorRGB(0, 0, 0); p.setFont("Helvetica-Bold", 12); p.drawString(80, 472, datos["Tema"])

    p.setFont("Helvetica", 11)
    p.drawString(80, 420, f"Empresa: {datos['Empresa']}")
    p.drawString(80, 400, f"Cargo: {datos.get('Cargo','N/A')}")
    p.drawString(80, 380, f"Fecha Registro: {datos['Fecha']}")

    # Foto Circular
    base_y = 185
    if imagen_foto:
        try:
            img_raw = Image.open(imagen_foto).convert("RGB").resize((180, 180))
            mask = Image.new("L", (180, 180), 0)
            draw = ImageDraw.Draw(mask); draw.ellipse((0, 0, 180, 180), fill=255)
            circular = Image.new("RGBA", (180, 180)); circular.paste(img_raw, (0, 0)); circular.putalpha(mask)
            p.drawImage(ImageReader(circular), 75, base_y, width=110, height=110, mask='auto')
        except: pass

    # Firma
    if imagen_firma is not None:
        try:
            img_firma = Image.fromarray(imagen_firma.astype("uint8"), "RGBA")
            p.drawImage(ImageReader(img_firma), width-255, base_y + 28, width=145, height=55, mask='auto')
        except: pass
    
    p.setStrokeColorRGB(*verde_oscuro); p.line(width-275, base_y + 18, width-95, base_y + 18)
    p.setFont("Helvetica-Bold", 10); p.drawCentredString(width-185, base_y + 3, "Firma del Trabajador")

    # Pie
    p.setFillColorRGB(*verde_claro); p.roundRect(20, 20, width-40, 25, 0, fill=1, stroke=0)
    p.setFillColorRGB(1, 1, 1); p.setFont("Helvetica", 8); p.drawCentredString(width/2, 30, "Documento digital oficial Campofert S.A.S.")
    
    p.showPage(); p.save(); buffer.seek(0)
    return buffer

# --- PROCESO SEGUNDO PLANO PARA CORREO ---
def enviar_correo_background(datos, firma, foto):
    try:
        pdf_file = generar_pdf_pro(datos, firma, foto)
        remitente = "gestionhumanacpfert@gmail.com"
        clave_app = "bhbwshtosozexhcr"
        msg = MIMEMultipart()
        msg['Subject'] = f"✅ Registro: {datos['Nombre']}"; msg['From'] = remitente; msg['To'] = remitente
        msg.attach(MIMEText(f"Nuevo registro de asistencia: {datos['Tema']}", 'plain'))
        pdf_file.seek(0)
        adjunto = MIMEBase('application', 'octet-stream'); adjunto.set_payload(pdf_file.read())
        encoders.encode_base64(adjunto); adjunto.add_header('Content-Disposition', f"attachment; filename=Certificado.pdf")
        msg.attach(adjunto)
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls(); server.login(remitente, clave_app); server.sendmail(remitente, remitente, msg.as_string())
    except: pass

# =============================================================================
# LÓGICA DE NAVEGACIÓN
# =============================================================================
if 'rol' not in st.session_state:
    st.markdown("<h1 style='text-align: center;'>🌱 Campofert People</h1>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    if c1.button("👷 COLABORADOR"): st.session_state.rol = "Empleado"; st.rerun()
    if c2.button("🛡️ ADMINISTRADOR"): st.session_state.esperando_admin = True; st.rerun()
    if st.session_state.get('esperando_admin'):
        with st.form("login_admin"):
            pw = st.text_input("Clave de Acceso", type="password")
            if st.form_submit_button("Entrar"):
                if pw == "campofert2026": st.session_state.rol = "Admin"; st.rerun()
                else: st.error("Clave incorrecta")
    st.stop()

df_asistencias = cargar_asistencias_google()

if st.session_state.rol == "Admin":
    with st.sidebar:
        if os.path.exists("logo_campofert.png"): st.image("logo_campofert.png")
        st.markdown("### Panel Administrativo")
        menu = st.radio("Ir a:", ["📊 Dashboard", "🔗 Generador de Enlaces", "👥 Empleados", "📤 Cargar Archivo", "📄 Historial", "📋 Probar Registro"])
        st.markdown("---")
        if st.button("⬅️ REGRESAR AL INICIO"): st.session_state.clear(); st.rerun()
else:
    menu = "📋 Registro Asistencia"

# =============================================================================
# MÓDULOS
# =============================================================================

# --- NUEVO: GENERADOR DE ENLACES ---
if menu == "🔗 Generador de Enlaces":
    st.title("🔗 Generador de URL de Capacitación")
    st.markdown("Usa esta herramienta para crear el link que compartirás con los trabajadores.")
    
    nombre_cap = st.text_input("Nombre de la Capacitación:", placeholder="Ej: Seguridad en Alturas")
    
    if nombre_cap:
        # Limpiar y codificar el texto para URL
        tema_codificado = urllib.parse.quote_plus(nombre_cap.upper())
        # Obtener la URL base (funciona tanto local como en la nube)
        base_url = "https://campofert-asistencia.streamlit.app/" # Cambia esto por tu URL real de Streamlit Cloud
        enlace_final = f"{base_url}?tema={tema_codificado}"
        
        st.info("✅ Enlace generado con éxito:")
        st.code(enlace_final)
        st.markdown(f"[Haga clic aquí para probar el enlace]({enlace_final})")
        st.warning("Copia el código de arriba y envíalo por WhatsApp a los colaboradores.")

elif menu == "📊 Dashboard":
    st.title("📊 Dashboard")
    st.dataframe(df_asistencias.tail(10), use_container_width=True)

elif menu == "👥 Empleados":
    st.title("👥 Personal Registrado")
    df_e = obtener_datos_empleados()
    if df_e is not None: st.dataframe(df_e, use_container_width=True)
    else: st.info("Sube 'empleados.xlsx' en el módulo de carga.")

elif menu == "📋 Registro Asistencia" or menu == "📋 Probar Registro":
    tema_url = st.query_params.get("tema", "CAPACITACIÓN GENERAL").replace("+", " ").upper()
    if 'paso' not in st.session_state: st.session_state.paso = 1

    if st.session_state.paso in [2, 3]:
        if st.button("⬅️ Corregir / Volver"): st.session_state.paso -= 1; st.rerun()

    if st.session_state.paso == 1:
        st.markdown(f"<div class='highlight-box'><strong>Capacitación Actual:</strong><br>{tema_url}</div>", unsafe_allow_html=True)
        ced = st.text_input("Ingrese su Cédula:")
        if ced:
            df_m = obtener_datos_empleados()
            persona = df_m[df_m['ID'].astype(str) == ced] if df_m is not None else pd.DataFrame()
            if not persona.empty:
                st.session_state.persona = persona.iloc[0].to_dict()
                st.session_state.cedula = ced
                st.success(f"Bienvenido, {st.session_state.persona['Apellidos y Nombres']}")
                if st.button("Continuar"): st.session_state.paso = 2; st.rerun()
            else:
                with st.form("nuevo_u"):
                    nom = st.text_input("Nombre Completo"); emp = st.selectbox("Empresa", ["CAMPOFERT", "CAMPOLAB", "CONTRATISTA"]); car = st.text_input("Cargo")
                    if st.form_submit_button("Registrar y Continuar"):
                        st.session_state.persona = {'Apellidos y Nombres': nom.upper(), 'Empresa': emp, 'Cargo': car.upper()}
                        st.session_state.cedula = ced; st.session_state.paso = 2; st.rerun()
        if st.session_state.rol == "Empleado" and st.button("Salir"): st.session_state.clear(); st.rerun()

    elif st.session_state.paso == 2:
        st.title("📸 Registro Fotográfico")
        cam = st.camera_input("Foto")
        if cam:
            st.session_state.foto_data = cam
            if st.button("Siguiente"): st.session_state.paso = 3; st.rerun()

    elif st.session_state.paso == 3:
        st.title("✍️ Firma Digital")
        canvas_f = st_canvas(stroke_width=3, stroke_color="#1B5E20", height=180, width=350, key="firma")
        if st.button("Finalizar ✅"):
            datos = {"Fecha": datetime.now(pytz.timezone('America/Bogota')).strftime("%d/%m/%Y %H:%M:%S"), "ID": st.session_state.cedula, "Nombre": st.session_state.persona['Apellidos y Nombres'], "Empresa": st.session_state.persona['Empresa'], "Cargo": st.session_state.persona.get('Cargo', 'N/A'), "Tema": tema_url}
            conn.update(worksheet="Hoja", data=pd.concat([df_asistencias, pd.DataFrame([datos])], ignore_index=True))
            st.session_state.pdf_doc = generar_pdf_pro(datos, canvas_f.image_data, st.session_state.foto_data)
            threading.Thread(target=enviar_correo_background, args=(datos, canvas_f.image_data, st.session_state.foto_data)).start()
            st.session_state.paso = 4; st.rerun()

    elif st.session_state.paso == 4:
        st.balloons(); st.success("¡Registro Completado!")
        st.download_button("📥 Descargar Certificado", st.session_state.pdf_doc.getvalue(), f"Certificado_{st.session_state.cedula}.pdf", "application/pdf")
        if st.button("Nuevo Registro"):
            for k in ['cedula','persona','pdf_doc','foto_data']: st.session_state.pop(k, None)
            st.session_state.paso = 1; st.rerun()

elif menu == "📤 Cargar Archivo":
    st.title("📤 Actualizar Personal")
    file_up = st.file_uploader("Subir empleados.xlsx", type=["xlsx"])
    if file_up:
        with open("empleados.xlsx", "wb") as f: f.write(file_up.getbuffer())
        st.success("Archivo guardado correctamente.")

elif menu == "📄 Historial":
    st.title("📄 Historial")
    st.dataframe(df_asistencias, use_container_width=True)
