import streamlit as st
import pandas as pd
import os
import io
import pytz
import qrcode
import threading
import random
import plotly.express as px
from io import BytesIO
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

# =============================================================================
# CONFIGURACIÓN DE PÁGINA
# =============================================================================
st.set_page_config(
    page_title="REGISTRO DE ASISTENCIA DIGITAL",
    layout="centered",
    page_icon="🌱"
)

# =============================================================================
# SESSION STATE
# =============================================================================
TOTAL_PAGINAS = 4
st.session_state.setdefault("rol", None)
st.session_state.setdefault("paso", 0)          # 0 = autorización imagen
st.session_state.setdefault("tema_actual", None)
st.session_state.setdefault("modulo", None)
st.session_state.setdefault("esperando_clave", False)

# =============================================================================
# CSS CORPORATIVO
# =============================================================================
CSS_CORPORATIVO = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;600;700;800&display=swap');

    * {
        font-family: 'Century Gothic', 'CenturyGothic', 'Nunito', 'Apple Gothic', sans-serif !important;
    }

    .stApp { background-color: #F5F5F0; }
    [data-testid="stSidebar"] { background-color: #1B5E20; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    .stButton > button {
        background-color: #2E7D32 !important; 
        color: white !important; 
        border: none !important;
        border-radius: 8px !important; 
        
        /* 1. Peso de negrilla estándar (Bold) */
        /* Quitamos el 800/900 y dejamos 700 para que sea elegante */
        font-weight: 900 !important; 
        font-size: 18px !important; 
        
        /* 2. ELIMINAMOS EL text-shadow */
        /* Al quitar esto, la letra recupera su forma original y limpia */
        text-shadow: none !important;
        
        padding: 0.6rem 1.5rem !important;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
        
        /* Bajamos un poco el espaciado ya que la letra no es tan ancha ahora */
        letter-spacing: 1px !important;
        text-transform: uppercase !important;
    }

    .stButton > button:hover { 
        background-color: #F9A825 !important; 
        color: #1B5E20 !important;
        /* Aseguramos que no haya sombra tampoco al pasar el mouse */
        text-shadow: none !important;
    }
    .stButton > button:hover { background-color: #F9A825; color: #1B5E20; }

    h1, h2, h3 {
        color: #1B5E20;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
        font-weight: 800 !important;
        letter-spacing: 1px;
    }

    .stTextInput > div > div > input {
        border: 2px solid #2E7D32; border-radius: 6px;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #F9A825; box-shadow: 0 0 0 2px rgba(249,168,37,0.3);
    }

    [data-testid="stMetricValue"] {
        color: #2E7D32; font-weight: bold;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
    }

    .stTabs [data-baseweb="tab"] {
        color: #2E7D32; font-weight: bold;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid #F9A825 !important; color: #1B5E20 !important;
    }

    footer { visibility: hidden; }

    .stDownloadButton > button {
        background-color: #F9A825; color: #1B5E20;
        font-weight: bold; border: none; border-radius: 8px;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
    }
    .stDownloadButton > button:hover { background-color: #2E7D32; color: white; }

    p, span, div, label, td, th {
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
    }

    /* Botones cámara en español */
    [data-testid="stCameraInputButton"]:first-child::after {
        content: 'Tomar Foto' !important;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
    }
    [data-testid="stCameraInputButton"]:last-child::after {
        content: 'Tomar Foto' !important;
        font-family: 'Century Gothic', 'Nunito', sans-serif !important;
    }
    [data-testid="stCameraInputButton"] span { display: none !important; }

    /* Limpieza y ajuste de logos GIGANTES en el encabezado */
    .hero-logos {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: transparent !important;
        width: 100%;
    }

    .hero-logos img {
        height: 65px !important; 
        width: auto !important;
        background-color: transparent !important; /* Quita el fondo blanco */
        background: transparent !important;       /* Refuerzo */
        border: none !important;
        box-shadow: none !important;
        filter: brightness(1.1); /* Ajusta el brillo de los logos blancos */
        object-fit: contain;
    }

    /* Estilo para el contenedor verde del banner */
    .hero-gerencia {
        background: linear-gradient(135deg,#0f4d1c,#1b5e20,#2e7d32) !important;
        border-radius: 26px !important;
        padding: 28px 25px !important;
        margin-bottom: 20px !important;
        border: none !important;
        text-align: center !important;
        box-shadow: 0 18px 40px rgba(0,0,0,.16) !important;
    }
    
    /* Título siempre blanco */
    .hero-gerencia h1 {
        color: white !important;
        margin: 10px 0 0 0 !important;
        font-size: 32px !important;
        font-weight: 800 !important;
        letter-spacing: 1px !important;
        text-shadow: none !important;
    }

    /* Logos sin cuadros blancos */
    .hero-logos img {
        height: 65px !important; 
        width: auto !important;
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        filter: brightness(1.1) !important;
        object-fit: contain !important;
    }

    /* Texto técnico pequeño y blanco */
    .hero-mini {
        font-size: 11px !important;
        color: rgba(255, 255, 255, 0.9) !important;
        margin-top: 15px !important;
        opacity: 0.85 !important;
    }
</style>
"""
st.markdown(CSS_CORPORATIVO, unsafe_allow_html=True)

# =============================================================================
# CONEXIÓN A DATOS
# =============================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

EMAIL_USER = st.secrets.get("email_user", "gestionhumanacpfert@gmail.com")
EMAIL_PASS = st.secrets.get("email_password", "eliwdxcfoseragcn")
ADMIN_PASS = st.secrets.get("admin_password", "campofert2026")

# =============================================================================
# PARÁMETROS URL
# =============================================================================
params = st.query_params
tema_desde_url = params.get("tema") or params.get("Tema")
if tema_desde_url:
    st.session_state.tema_actual = tema_desde_url.replace("+", " ").strip().upper()
if not st.session_state.tema_actual:
    st.session_state.tema_actual = "CAPACITACIÓN GENERAL"
tema_actual = st.session_state.tema_actual

rol_url = params.get("rol")
if rol_url and st.session_state.rol is None:
    if rol_url.lower() == "empleado":
        st.session_state.rol = "Empleado"
    elif rol_url.lower() == "admin":
        st.session_state.rol = "Admin"

# =============================================================================    
# LOGOS EN CACHÉ (se leen una sola vez, se comparten entre sesiones)
# =============================================================================
@st.cache_resource(show_spinner=False)
def cargar_logos():
    logos = {}
    for clave, ruta in [("campofert", "logo_campofert.png"), ("campolab", "logo_campolab.png")]:
        if os.path.exists(ruta):
            logos[clave] = Image.open(ruta).copy()
    return logos

LOGOS = cargar_logos()

# =============================================================================
# FUNCIONES DE DATOS
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def obtener_datos():
    """TTL de 1h: el maestro no cambia durante una capacitación."""
    ruta = "empleados.xlsx"
    if os.path.exists(ruta):
        try:
            df = pd.read_excel(ruta, engine="openpyxl", dtype={"ID": str})
            df.columns = df.columns.str.strip()
            return df
        except Exception as e:
            st.error(f"Error al leer empleados.xlsx: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60, show_spinner=False)
def leer_asistencias():
    """TTL de 60s — equilibrio entre frescura y presión en la API."""
    try:
        df = conn.read(worksheet="Hoja")
        return df if df is not None else pd.DataFrame()
    except Exception as e:
        st.error(f"Error leyendo asistencias: {e}")
        return pd.DataFrame()

def guardar_en_google_sheets(datos):
    try:
        if not datos.get("ID") or not datos.get("Nombre"):
            st.error("Datos incompletos")
            return False

        nueva_fila = pd.DataFrame([{
            "Fecha":   datos.get("Fecha"),
            "ID":      str(datos.get("ID")),
            "Nombre":  datos.get("Nombre"),
            "Empresa": datos.get("Empresa"),
            "Cargo":   datos.get("Cargo", "NO REGISTRA"),
            "Tema":    datos.get("Tema"),
        }])

        # Leer siempre fresco sin caché para no sobrescribir
        actual = conn.read(worksheet="Hoja", ttl=0)

        if actual is None or actual.empty:
            df_final = nueva_fila
        else:
            actual = actual.dropna(how="all")
            df_final = pd.concat([actual, nueva_fila], ignore_index=True)

        conn.update(worksheet="Hoja", data=df_final)
        leer_asistencias.clear()
        return True

    except Exception as e:
        st.error(f"Error guardando en Google Sheets: {e}")
        return False
# =============================================================================
# FUNCIÓN DE ENVÍO DE CORREO (MEJORADA ESTILO CÓDIGO 45)
# =============================================================================
def enviar_respaldo_async(datos, pdf_buffer):

    def _proceso_envio():
        try:
            print("📩 Enviando respaldo a RRHH...")

            msg = MIMEMultipart()
            msg['From'] = EMAIL_USER
            msg['To'] = EMAIL_USER
            msg['Subject'] = f"✅ Asistencia: {datos['Nombre']} - {datos['Tema']}"

            # 🧾 CUERPO
            cuerpo = f"""
            <html><body style="font-family: Arial;">
                <h2 style="color:#2E7D32;">📋 Respaldo de Asistencia</h2>
                <p><b>Empleado:</b> {datos['Nombre']}</p>
                <p><b>Cédula:</b> {datos['ID']}</p>
                <p><b>Empresa:</b> {datos['Empresa']}</p>
                <p><b>Cargo:</b> {datos.get('Cargo', 'NO REGISTRA')}</p>
                <p><b>Tema:</b> {datos['Tema']}</p>
                <p><b>Fecha:</b> {datos['Fecha']}</p>
                <hr>
                <small>Enviado automáticamente desde Campofert</small>
            </body></html>
            """
            msg.attach(MIMEText(cuerpo, 'html'))

            # 📎 ADJUNTO PDF
            pdf_buffer.seek(0)
            adjunto = MIMEBase('application', 'octet-stream')
            adjunto.set_payload(pdf_buffer.read())
            encoders.encode_base64(adjunto)
            adjunto.add_header(
                'Content-Disposition',
                f"attachment; filename=Certificado_{datos['ID']}.pdf"
            )
            msg.attach(adjunto)

            # 🚀 ENVÍO
            server = smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=30)
            server.login(EMAIL_USER, EMAIL_PASS)

            server.sendmail(
                EMAIL_USER,
                [EMAIL_USER],
                msg.as_string()
            )

            server.quit()

            print(f"✅ CORREO ENVIADO para {datos['ID']}")

        except Exception as e:
            import traceback
            print("❌ ERROR EN CORREO:")
            print(traceback.format_exc())

    # 🚀 ENVÍO EN SEGUNDO PLANO
    threading.Thread(target=_proceso_envio, daemon=True).start()

# =============================================================================
# GENERACIÓN DE PDF
# =============================================================================
def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    verde  = (0.10, 0.36, 0.16)
    verde2 = (0.18, 0.52, 0.24)
    dorado = (0.95, 0.74, 0.12)
    gris   = (0.96, 0.96, 0.96)
    codigo = f"CPF-2026-{random.randint(100000, 999999)}"

    # Fondo y marco
    p.setFillColorRGB(1, 1, 1)
    p.rect(0, 0, width, height, fill=1, stroke=0)
    p.setStrokeColorRGB(*verde)
    p.setLineWidth(1.4)
    p.roundRect(20, 20, width - 40, height - 40, 14)

    # Encabezado
    p.setFillColorRGB(*verde)
    p.roundRect(20, height - 125, width - 40, 105, 14, fill=1, stroke=0)
    p.setFillColorRGB(*dorado)
    p.rect(20, height - 125, width - 40, 5, fill=1, stroke=0)

    # Logos desde caché (sin leer disco por cada usuario)
    for clave, x in [("campofert", 35), ("campolab", width - 130)]:
        if clave in LOGOS:
            try:
                p.drawImage(ImageReader(LOGOS[clave]), x, height - 112,
                            width=95, height=72, preserveAspectRatio=True)
            except Exception as ex:
                print(f"[PDF LOGO] {ex}")

    # Títulos
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 63, "CERTIFICADO DE ASISTENCIA")
    p.setFont("Helvetica", 10)
    p.drawCentredString(width / 2, height - 84,
                        "Sistema de Gestión Humana y Seguridad en el Trabajo")
    p.setFont("Helvetica-Bold", 8)
    p.drawRightString(width - 35, height - 38, codigo)

    # Texto central
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 610, "Por medio del presente documento se certifica que:")
    p.setFillColorRGB(*verde)
    p.setFont("Helvetica-Bold", 24)
    p.drawCentredString(width / 2, 570, datos["Nombre"].upper())
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 545, f"Identificado(a) con documento No. {datos['ID']}")

    # Bloque capacitación
    p.setFillColorRGB(*gris)
    p.roundRect(60, 445, width - 120, 75, 10, fill=1, stroke=0)
    p.setFillColorRGB(*verde)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(80, 495, "CAPACITACIÓN / ACTIVIDAD:")
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica-Bold", 12)
    p.drawString(80, 472, datos["Tema"])

    # Datos
    p.setFont("Helvetica", 11)
    p.drawString(80, 420, f"Empresa: {datos['Empresa']}")
    p.drawString(80, 400, f"Cargo: {datos.get('Cargo', 'NO REGISTRA')}")
    p.drawString(80, 380, f"Fecha Registro: {datos['Fecha']}")

    base_y = 185

    # Foto (comprimida a 150px — suficiente en PDF)
    if imagen_foto is not None:
        try:
            img = Image.open(imagen_foto).convert("RGB")
            img.thumbnail((150, 150))
            p.drawImage(ImageReader(img), 75, base_y, width=110, height=110)
            p.setFont("Helvetica", 8)
            p.drawCentredString(130, base_y - 12, "Validación de Identidad")
        except Exception as ex:
            print(f"[PDF FOTO] {ex}")

    # Firma
    if imagen_firma is not None:
        try:
            p.drawImage(
                ImageReader(imagen_firma),
                width - 255,
                base_y + 28,
                width=145,
                height=55,
                preserveAspectRatio=True,
                
            )
        except Exception as ex:
            print(f"[PDF FIRMA] {ex}")

    p.setStrokeColorRGB(*verde)
    p.line(width - 275, base_y + 18, width - 95, base_y + 18)
    p.setFont("Helvetica-Bold", 10)
    p.drawCentredString(width - 185, base_y + 3, "Firma del Trabajador")

    # Pie
    p.setFillColorRGB(*verde2)
    p.roundRect(20, 20, width - 40, 25, 0, fill=1, stroke=0)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica", 8)
    p.drawCentredString(width / 2, 30,
                        "Documento digital oficial emitido por Campofert S.A.S.")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# PANTALLA DE LOGIN INICIAL
# =============================================================================
if "rol" not in st.session_state:
    st.session_state.rol = None

# Manejo de rol desde URL
if 'rol_url' in locals() and rol_url and rol_url.lower() == "empleado":
    st.session_state.rol = "Empleado"

if st.session_state.get("rol") is None:

    st.markdown("""
    <style>
    .stApp {
        background: linear-gradient(180deg,#f4f6f2,#eef3ef);
    }

    .hero-gerencia {
        background: linear-gradient(135deg,#0f4d1c,#1b5e20,#2e7d32);
        padding: 28px 25px;
        border-radius: 26px;
        text-align:center;
        color:white;
        box-shadow:0 18px 40px rgba(0,0,0,.16);
        margin-bottom:18px;
    }

    .hero-logos {
        display:flex;
        justify-content:space-between;
        align-items:center;
        margin-bottom:10px;
    }

    .hero-logo-img {
        background: transparent !important; /* Cambiado de white a transparent */
        height: 65px !important;            /* Ajustado para que el logo gigante no rompa el diseño */
        width: auto !important;              /* Cambiado de 110px a auto para no deformar */
        object-fit: contain;
    }

    .hero-gerencia h1 {
        margin:0;
        font-size:38px;
        font-weight:800;
        letter-spacing:1px;
        color: white !important;
    }

    .hero-mini {
        margin-top: 15px !important;
        font-size: 11px !important;         /* Texto más pequeño como pediste */
        opacity: .85;
        color: white !important;
    }

    .titulo-acceso {
        text-align:center;
        color:#1B5E20;
        font-size:36px;
        font-weight:800;
        margin-top:8px;
    }

    .sub-acceso {
        text-align:center;
        color:#6b7280;
        font-size:16px;
        margin-bottom:18px;
    }

    .stButton > button {
        height:70px !important;
        border-radius:18px !important;
        font-size:22px !important;
        font-weight:800 !important;
        border:none !important;
        background:linear-gradient(135deg,#1b5e20,#2e7d32) !important;
        color:white !important;
        box-shadow:0 10px 22px rgba(27,94,32,.20);
    }

    .stButton > button:hover {
        transform:translateY(-2px);
        background: #F9A825 !important;
        color: #1B5E20 !important;
    }

    .footer-premium {
        text-align:center;
        color:#7b7b7b;
        margin-top:18px;
        font-size:15px;
    }
    </style>
    """, unsafe_allow_html=True)

    import base64
    from io import BytesIO

    # Función unificada para logos
    def logo_to_base64(img_pil):
        buf = BytesIO()
        img_pil.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode("utf-8")

    # Generación segura de logos
    logo_cf_html = f'<img src="data:image/png;base64,{logo_to_base64(LOGOS["campofert"])}" class="hero-logo-img">' if "campofert" in LOGOS else "<div></div>"
    logo_cl_html = f'<img src="data:image/png;base64,{logo_to_base64(LOGOS["campolab"])}" class="hero-logo-img">' if "campolab" in LOGOS else "<div></div>"

    # 1. Lógica de paginación dinámica
    paso = st.session_state.get("paso", 0)
    
    if paso == 0:
        texto_pagina = ""  # No hay página, no hay barra separadora
    else:
        # Aquí incluimos la barra "|" dentro del string
        texto_pagina = f" | Página: {paso} de {TOTAL_PAGINAS}"

    # 2. El f-string corregido (quitamos la barra fija después de '2026-05-20')
    st.markdown(f"""
    <div class="hero-gerencia">
        <div class="hero-logos">
            {logo_cf_html}
            {logo_cl_html}
        </div>
        <h1>REGISTRO ASISTENCIA DIGITAL</h1>
        <div class="hero-mini">
            Código: I.FO.GH.03 | Versión: 03 | Fecha de emisión: 2014-12-01 |
            Fecha de actualización: 2026-05-20{texto_pagina}
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<div class="titulo-acceso">Acceso Corporativo</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-acceso">Seleccione el perfil para ingresar</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)

        with c1:
            if st.button("COLABORADOR", use_container_width=True):
                st.session_state.rol = "Empleado"
                st.session_state.paso = 0
                st.rerun()

        with c2:
            if st.button("ADMINISTRADOR", use_container_width=True):
                st.session_state.esperando_clave = True
                st.rerun()

        # Lógica de Login para Administrador
        if st.session_state.get("esperando_clave"):
            st.markdown("---")
            with st.form("login_admin", clear_on_submit=False):
                clave = st.text_input(
                    "🔑 Ingrese Clave de Administrador:",
                    type="password",
                    placeholder="Contraseña corporativa"
                )
                col_bt1, col_bt2 = st.columns(2)
                with col_bt1:
                    entrar = st.form_submit_button("Entrar")
                with col_bt2:
                    cancelar = st.form_submit_button("Cancelar")

                if entrar:
                    if clave == ADMIN_PASS:
                        st.session_state.rol = "Admin"
                        st.session_state.esperando_clave = False
                        st.rerun()
                    else:
                        st.error("Clave incorrecta ❌")

                if cancelar:
                    st.session_state.esperando_clave = False
                    st.rerun()

        st.markdown(
            '<div class="footer-premium">Campofert S.A.S • Campolab • Versión 2026</div>',
            unsafe_allow_html=True
        )

    st.stop()  
# =============================================================================
# BARRA SUPERIOR (botón volver + logos + título)
# =============================================================================
# Botón de inicio SOLO para admin
if st.session_state.rol == "Admin":

    col_volver, col_vacia = st.columns([1, 4])

    with col_volver:
        if st.button("⬅️ Inicio", use_container_width=True):

            for key in list(st.session_state.keys()):
                del st.session_state[key]

            st.rerun()

import base64
from io import BytesIO

def logo_b64(img_pil):
    buf = BytesIO()
    img_pil.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")

# Generación de logos limpia (sin cuadros blancos)
logo_cf = (
    f'<img src="data:image/png;base64,{logo_b64(LOGOS["campofert"])}" class="hero-logo-img">'
    if "campofert" in LOGOS else ""
)

logo_cl = (
    f'<img src="data:image/png;base64,{logo_b64(LOGOS["campolab"])}" class="hero-logo-img">'
    if "campolab" in LOGOS else ""
)

paso = st.session_state.get("paso", 0)
texto_pagina = f" | Página: {paso} de {TOTAL_PAGINAS}" if paso > 0 else ""

# RENDERIZADO FINAL: Quitamos todos los style='...' y usamos las clases CSS
st.markdown(f"""
    <div class="hero-gerencia">
        <div class="hero-logos">
            {logo_cf}
            {logo_cl}
        </div>
        <h1>REGISTRO ASISTENCIA DIGITAL</h1>
        <div class="hero-mini">
            Código: I.FO.GH.03 | Versión: 03 | Fecha de emisión: 2014-12-01 |
            Fecha de actualización: 2026-05-20{texto_pagina}
        </div>
    </div>
    """, unsafe_allow_html=True)
# =============================================================================
# MENÚ SEGÚN ROL
# =============================================================================
if st.session_state.rol == "Empleado":
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {display:none;}
        #MainMenu {visibility:hidden;}
        header {visibility:hidden;}
    </style>
    """, unsafe_allow_html=True)
    menu = "📋 Registro Asistencia"

else:
    with st.sidebar:
        if "campofert" in LOGOS:
            st.image(LOGOS["campofert"], width=180)
        st.markdown("## Panel Administrativo")
        st.markdown("Gestión Humana / Campofert")
        st.markdown("---")
        menu = st.radio("Seleccione módulo", [
            "⚙️ Configurar Tema",
            "📋 Registro Asistencia",
            "👥 Lista Empleados",
            "📤 Cargar Base de Personal",
            "📄 Cargar Dcto para Firma",
            "📊 Dashboard",
            "📄 Historial",
            "📁 Reportes",
        ])
        st.markdown("---")
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            del st.session_state["rol"]
            st.rerun()
# =============================================================================
# PANEL ADMIN
# =============================================================================
if st.session_state.rol == "Admin":

    if menu == "⚙️ Configurar Tema":
        st.markdown("## ⚙️ Configuración de la Capacitación")
        with st.container(border=True):
            st.markdown("### 1. Definir Tema")
            nuevo_tema = st.text_input(
                "Nombre de la capacitación o inducción:",
                placeholder="Ej: INDUCCIÓN SEGURIDAD Y SALUD 2026"
            )
            if st.button("💾 Guardar y Activar Tema"):
                if nuevo_tema:
                    st.session_state.tema_actual = nuevo_tema.upper()
                    st.success(f"✅ Tema actualizado: **{nuevo_tema.upper()}**")
                else:
                    st.error("⚠️ Por favor escribe un nombre antes de guardar.")

        if "tema_actual" in st.session_state:
            st.markdown("---")
            st.markdown("### 🔗 Enlace de Acceso para Colaboradores")
            tema_url  = st.session_state.tema_actual.replace(" ", "+")
            base_url  = "https://asistencias-campofert.streamlit.app/"
            url_final = f"{base_url}/?tema={tema_url}&rol=Empleado"
            st.info(f"Copia este enlace y envíalo por WhatsApp:\n\n**{url_final}**")
            col_qr1, col_qr2 = st.columns([1, 2])
            with col_qr1:
                qr  = qrcode.make(url_final)
                buf = BytesIO()
                qr.save(buf, format="PNG")
                st.image(buf.getvalue(), caption="QR para proyectar en sala", width=200)
            with col_qr2:
                st.markdown("""
                **Instrucciones:**
                1. El tema guardado aparecerá automáticamente en el certificado.
                2. Los empleados que usen el QR o el link entrarán directo al registro.
                3. No necesitas volver a configurar nada hasta la siguiente capacitación.
                """)

    if menu == "👥 Lista Empleados":
        st.markdown("## 👥 Base de Empleados")
        df_emp = obtener_datos()
        if df_emp is not None and not df_emp.empty:
            st.success(f"Total empleados cargados: {len(df_emp)}")
            buscar = st.text_input("🔎 Buscar empleado")
            if buscar:
                filtro = df_emp.astype(str).apply(
                    lambda x: x.str.contains(buscar, case=False, na=False)
                ).any(axis=1)
                df_emp = df_emp[filtro]
            st.dataframe(df_emp, use_container_width=True)
            excel = BytesIO()
            with pd.ExcelWriter(excel, engine="openpyxl") as writer:
                df_emp.to_excel(writer, index=False, sheet_name="Empleados")
            st.download_button("📥 Descargar Excel", excel.getvalue(), "empleados.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("No existe archivo empleados.xlsx")

    elif menu == "📤 Cargar Base de Personal":
        st.markdown("## 📤 Actualizar Base de Personal")
        archivo = st.file_uploader("Subir archivo Excel actualizado", type=["xlsx"])
        if archivo is not None:
            with open("empleados.xlsx", "wb") as f:
                f.write(archivo.getbuffer())
            obtener_datos.clear()
            st.success("✅ Archivo actualizado correctamente.")

    elif menu == "📄 Cargar Dcto para Firma":
        st.markdown("## 📄 Cargar Documento para Firma")
    
        archivo = st.file_uploader("Subir documento PDF", type=["pdf"])
        correo_responsable = st.text_input("Correo responsable (quien recibirá las firmas)")
        tipo_doc = st.selectbox("Tipo de documento", ["DOTACIÓN", "BIENESTAR", "OTRO"])
    
        if st.button("Guardar documento"):
    
            if archivo and correo_responsable:
    
                # 📁 Guardar archivo local
                os.makedirs("docs", exist_ok=True)
    
                ruta = f"docs/{archivo.name}"
                with open(ruta, "wb") as f:
                    f.write(archivo.getbuffer())
    
                # 📊 Guardar en Google Sheets
                nuevo = pd.DataFrame([{
                    "ID_DOC": random.randint(1000, 9999),
                    "NOMBRE_DOCUMENTO": archivo.name,
                    "RUTA_PDF": archivo.name,
                    "RESPONSABLE_CORREO": correo_responsable,
                    "TIPO": tipo_doc,
                    "FECHA": datetime.now().strftime("%d/%m/%Y %H:%M")
                }])
    
                try:
                    df = conn.read(worksheet="DOCUMENTOS")
                    if df is None or df.empty:
                        df = nuevo
                    else:
                        df = pd.concat([df, nuevo], ignore_index=True)
    
                    conn.update(worksheet="DOCUMENTOS", data=df)
    
                    st.success("✅ Documento cargado correctamente")
    
                except Exception as e:
                    st.error(f"Error guardando documento: {e}")
    
            else:
                st.warning("⚠️ Debes subir archivo y correo")
    
    elif menu == "📊 Dashboard":
        st.markdown("## 📊 Dashboard Ejecutivo")
    
        if st.button("🔄 Actualizar datos"):
            leer_asistencias.clear()
            st.rerun()
    
        try:
            df = leer_asistencias()
    
            if df.empty:
                st.warning("No hay registros.")
                st.stop()
    
            # =============================
            # 🔽 AQUÍ VA TU BLOQUE COMPLETO
            # =============================
    
            # LIMPIEZA
            df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
            df = df.dropna(subset=["Fecha"])
    
            # FILTROS
            with st.expander("🎯 Filtros", expanded=False):
                colf1, colf2, colf3 = st.columns(3)
    
                with colf1:
                    empresa_sel = st.multiselect(
                        "🏢 Empresa",
                        options=sorted(df["Empresa"].dropna().unique()),
                        default=sorted(df["Empresa"].dropna().unique())
                    )
    
                with colf2:
                    tema_sel = st.multiselect(
                        "📚 Tema",
                        options=sorted(df["Tema"].dropna().unique()),
                        default=sorted(df["Tema"].dropna().unique())
                    )
    
                with colf3:
                    fecha_sel = st.date_input(
                        "📅 Rango de fechas",
                        value=(df["Fecha"].min().date(), df["Fecha"].max().date())
                    )
    
            # FILTRADO
            df_filtrado = df[
                (df["Empresa"].isin(empresa_sel)) &
                (df["Tema"].isin(tema_sel))
            ].copy()
    
            if isinstance(fecha_sel, tuple) and len(fecha_sel) == 2:
                inicio, fin = fecha_sel
                df_filtrado = df_filtrado[
                    (df_filtrado["Fecha"].dt.date >= inicio) &
                    (df_filtrado["Fecha"].dt.date <= fin)
                ]
    
            if df_filtrado.empty:
                st.warning("⚠️ No hay datos con los filtros seleccionados.")
                st.stop()
    
            # KPIs
            total = len(df_filtrado)
            personas = df_filtrado["ID"].nunique()
            temas = df_filtrado["Tema"].nunique()
            empresas = df_filtrado["Empresa"].nunique()
    
            # CSS
            st.markdown("""
            <style>
            .card {
                background: white;
                padding: 18px;
                border-radius: 16px;
                box-shadow: 0 6px 16px rgba(0,0,0,0.08);
                border-left: 6px solid #2E7D32;
                text-align: center;
            }
            .card h3 { margin:0; font-size:14px; color:#6B7280; }
            .card h1 { margin:5px 0; font-size:30px; color:#1B5E20; }
            </style>
            """, unsafe_allow_html=True)
    
            k1, k2, k3, k4 = st.columns(4)
    
            with k1:
                st.markdown(f'<div class="card"><h3>📋 Registros</h3><h1>{total}</h1></div>', unsafe_allow_html=True)
            with k2:
                st.markdown(f'<div class="card"><h3>👥 Personas</h3><h1>{personas}</h1></div>', unsafe_allow_html=True)
            with k3:
                st.markdown(f'<div class="card"><h3>📚 Capacitaciones</h3><h1>{temas}</h1></div>', unsafe_allow_html=True)
            with k4:
                st.markdown(f'<div class="card"><h3>🏢 Empresas</h3><h1>{empresas}</h1></div>', unsafe_allow_html=True)
    
            st.markdown("---")
    
            # GRÁFICO
            df_fecha = df_filtrado.copy()
            df_fecha["Fecha"] = df_fecha["Fecha"].dt.date
            df_fecha = df_fecha.groupby("Fecha").size().reset_index(name="Registros")
    
            fig_line = px.line(df_fecha, x="Fecha", y="Registros", markers=True)
            st.plotly_chart(fig_line, use_container_width=True)
    
            st.markdown("---")
    
            # RESUMEN
            st.subheader("📋 Resumen por Empresa")
    
            resumen = df_filtrado.groupby("Empresa").agg(
                Registros=("ID", "count"),
                Personas=("ID", "nunique")
            ).reset_index()
    
            st.dataframe(resumen, use_container_width=True)
    
        except Exception as e:
            st.error(f"Error crítico en el Dashboard: {e}")
    
    
    elif menu == "📄 Historial":
        st.markdown("## 📄 Historial de Asistencias")
    
        try:
            df = leer_asistencias()
    
            ced = st.text_input("Buscar por cédula")
    
            if ced:
                df = df[df["ID"].astype(str) == ced]
    
            st.dataframe(df, use_container_width=True)
    
        except Exception as e:
            st.warning(f"Error historial: {e}")
    
    
    elif menu == "📁 Reportes":
        st.markdown("## 📁 Reportes")
    
        try:
            df = leer_asistencias()
    
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Descargar CSV", csv, "reporte.csv", "text/csv")
    
            excel = BytesIO()
            with pd.ExcelWriter(excel, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Reporte")
    
            st.download_button(
                "📥 Descargar Excel",
                excel.getvalue(),
                "reporte.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
        except Exception as e:
            st.warning(f"Error reportes: {e}")

# =============================================================================
# FLUJO EMPLEADO
# =============================================================================
if menu == "📋 Registro Asistencia":

    # Reset al entrar al módulo por primera vez
    if st.session_state.get("modulo") != "registro_asistencia":
        st.session_state.modulo    = "registro_asistencia"
        st.session_state.paso      = 0       # 0 = autorización de imagen
        st.session_state.persona   = None
        st.session_state.cedula    = None
        st.session_state.foto_data = None
        st.session_state.pdf_doc   = None

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 0 → AUTORIZACIÓN DE USO DE IMAGEN  (NUEVO)
    # ─────────────────────────────────────────────────────────────────────────
    if st.session_state.paso == 0:

        st.markdown("""
        <div style='background-color:#E8F5E9; border-left:5px solid #2E7D32;
                    padding:12px 16px; border-radius:6px; margin-bottom:1.2rem;'>
            📋 <strong>Antes de continuar, por favor lee y acepta la siguiente autorización.</strong>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style='
            border: 2px solid #1B5E20;
            border-radius: 12px;
            padding: 28px 32px;
            background-color: #ffffff;
            max-width: 680px;
            margin: 0 auto 20px auto;
            font-family: Arial, sans-serif;
        '>
            <h3 style='text-align:center; color:#1B5E20; font-size:17px; font-weight:800; margin-bottom:16px;'>
                AUTORIZACIÓN DE USO DE DATOS PERSONALES, DERECHOS DE IMAGEN Y FIRMA DIGITAL
            </h3>
            <p style='font-size:14px; color:#222; line-height:1.7; text-align:justify;'>
                Autorizo a la <strong>Organización, en calidad de responsable del
                tratamiento de datos personales, para que recopile, almacene y utilice la
                siguiente información: <strong>fotografía</strong> para validación de identidad,
                <strong>firma manuscrita digitalizada</strong> como constancia de asistencia, y
                <strong>datos de identificación</strong> (nombre, cédula, cargo, empresa).
            </p>
            <p style='font-size:14px; color:#222; line-height:1.7; text-align:justify; margin-top:12px;'>
                La finalidad del tratamiento es <strong>exclusivamente</strong> el registro y
                certificación de asistencia a capacitaciones y actividades corporativas, conforme
                a las obligaciones del SG-SST. Esta autorización se otorga de forma
                <strong>voluntaria, libre y espontánea</strong>, conforme a la
                <strong>Ley 1581 de 2012</strong> y el <strong>Decreto 1377 de 2013</strong>.
                El titular podrá ejercer sus derechos de acceso, corrección y supresión
                escribiendo a: <strong>gestionhumana@campofert.com</strong>
            </p>
            <p style='font-size:13px; color:#555; margin-top:16px; text-align:center;'>
                Al hacer clic en <em>"Acepto y Continuar"</em> confirmo que he leído y entendido
                esta autorización.
            </p>
        </div>
        """, unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Acepto y Continuar", use_container_width=True):
                st.session_state.paso = 1
                st.rerun()
        with col_b:
            if st.button("No Acepto / Salir", use_container_width=True):
                st.warning("Debes aceptar la autorización para continuar con el registro.")

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 1 → CÉDULA
    # ─────────────────────────────────────────────────────────────────────────
    elif st.session_state.paso == 1:

        st.markdown(f"""
            <div style='background-color:#E8F5E9; border-left:5px solid #2E7D32;
                        padding:12px 16px; border-radius:6px; margin-bottom:1rem;'>
                📋 <strong>TEMA ACTUAL:</strong> {tema_actual}
            </div>
        """, unsafe_allow_html=True)

        df_maestro = obtener_datos()

        with st.form("form_cedula"):
            cedula_input = st.text_input(
                "Por favor, ingresa tu Cédula:",
                placeholder="Escribe tu número de cédula y presiona Buscar"
            ).strip()
            buscar = st.form_submit_button("🔍 Buscar", use_container_width=True)

        if buscar and cedula_input:
            st.session_state.cedula_buscada = cedula_input

        # Trabajar con la cédula guardada en session_state
        cedula = st.session_state.get("cedula_buscada", "")

        if cedula:
            res = (
                df_maestro[df_maestro["ID"].astype(str) == cedula]
                if df_maestro is not None else pd.DataFrame()
            )

            if not res.empty:
                st.session_state.persona = res.iloc[0].to_dict()
                st.session_state.cedula  = cedula
                st.success(f"✅ Hola, **{st.session_state.persona['Apellidos y Nombres']}**. ¡Bienvenido!")
                if st.button("Continuar al registro ➡️", use_container_width=True):
                    st.session_state.cedula_buscada = None
                    st.session_state.paso = 2
                    st.rerun()

            else:
                st.warning("⚠️ Cédula no encontrada. Si eres contratista o personal nuevo, regístrate:")
                with st.form("registro_nuevo_empleado"):
                    nombre_nuevo         = st.text_input("Nombres y Apellidos Completos:")
                    empresa_seleccionada = st.selectbox(
                        "Empresa:", ["CAMPOFERT", "CAMPOLAB", "TEMPORAL / CONTRATISTA"]
                    )
                    empresa_externa = ""
                    if empresa_seleccionada == "TEMPORAL / CONTRATISTA":
                        empresa_externa = st.text_input("¿A qué empresa perteneces?")
                    cargo_nuevo = st.text_input("Tu Cargo:")

                    if st.form_submit_button("Registrarme y Continuar ➡️", use_container_width=True):
                        if nombre_nuevo and cargo_nuevo:
                            nom_emp = (
                                empresa_externa.upper()
                                if empresa_seleccionada == "TEMPORAL / CONTRATISTA" and empresa_externa
                                else empresa_seleccionada
                            )
                            st.session_state.persona = {
                                "Apellidos y Nombres": nombre_nuevo.upper(),
                                "Empresa": nom_emp,
                                "Cargo":   cargo_nuevo.upper(),
                            }
                            st.session_state.cedula = cedula
                            st.session_state.cedula_buscada = None
                            st.session_state.paso   = 2
                            st.rerun()
                        else:
                            st.error("Completa todos los campos.")

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 2 → FOTO
    # ─────────────────────────────────────────────────────────────────────────
    elif st.session_state.paso == 2:
        st.markdown("### Captura de Identidad")
        st.markdown("<p style='color:#555;'>Tómate una foto para validar tu identidad.</p>",
                    unsafe_allow_html=True)
        foto = st.camera_input("Foto de validación")
        if foto:
            st.session_state.foto_data = foto
            if st.button("Ir a la firma"):
                st.session_state.paso = 3
                st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 3 → FIRMA
    # ─────────────────────────────────────────────────────────────────────────
    elif st.session_state.paso == 3:
    
        st.markdown("### Firma Digital")
        st.markdown(
            "<p style='color:#555;'>Dibuja tu firma en el recuadro blanco.</p>",
            unsafe_allow_html=True
        )
    
        canvas_res = st_canvas(
            stroke_width=3,
            stroke_color="#1B5E20",
            background_color="#ffffff",
            height=180,
            width=350,
            key="firma_final"
        )
    
        if st.button("ENVIAR ✅"):
    
            if canvas_res.image_data is None:
                st.warning("Debe firmar antes de continuar.")
                st.stop()
    
            alpha = canvas_res.image_data[:, :, 3]
    
            if int(alpha.sum()) < 3000:
                st.warning("Debe firmar antes de continuar.")
                st.stop()
    
            datos_asistencia = {
                "Fecha": datetime.now(
                    pytz.timezone("America/Bogota")
                ).strftime("%d/%m/%Y %H:%M:%S"),
                "ID": st.session_state.cedula,
                "Nombre": st.session_state.persona["Apellidos y Nombres"],
                "Empresa": st.session_state.persona.get("Empresa", "NO REGISTRA"),
                "Cargo": st.session_state.persona.get("Cargo", "NO REGISTRA"),
                "Tema": tema_actual,
            }
    
            with st.spinner("Guardando registro..."):
                guardado = guardar_en_google_sheets(datos_asistencia)
    
            if guardado:
    
                with st.spinner("Generando certificado..."):
    
                    # FOTO OPTIMIZADA
                    foto_comprimida = None
    
                    if st.session_state.get("foto_data"):
                        try:
                            img_raw = Image.open(
                                st.session_state.get("foto_data")
                            ).convert("RGB")
    
                            img_raw.thumbnail((160, 160))
    
                            buf_foto = BytesIO()
    
                            img_raw.save(
                                buf_foto,
                                format="JPEG",
                                quality=75,
                                optimize=True
                            )
    
                            buf_foto.seek(0)
    
                            foto_comprimida = buf_foto
    
                        except Exception as ex:
                            print(f"[FOTO ERROR] {ex}")
    
                    # FIRMA PREPARADA
                    firma_img = None
    
                    try:
                        firma_rgba = Image.fromarray(
                            canvas_res.image_data.astype("uint8"),
                            "RGBA"
                        )
                        
                        firma_img = Image.new("RGB", firma_rgba.size, "white")
                        firma_img.paste(firma_rgba, mask=firma_rgba.split()[3])
    
                    except Exception as ex:
                        print(f"[FIRMA ERROR] {ex}")
    
                    # PDF
                    pdf = generar_pdf(
                        datos_asistencia,
                        firma_img,
                        foto_comprimida
                    )
    
                # 👇 AQUÍ VA EL ENVÍO
                enviar_respaldo_async(datos_asistencia, pdf)
    
                pdf.seek(0)
                st.session_state.pdf_doc = pdf
                st.session_state.paso = 4
                st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 4 → RESULTADO
    # ─────────────────────────────────────────────────────────────────────────
    elif st.session_state.paso == 4:
        #st.balloons()
        st.markdown("""
            <div style='background-color:#E8F5E9; border:2px solid #2E7D32;
                        padding:20px; border-radius:10px; text-align:center;'>
                <h2 style='color:#1B5E20;'>¡Gracias por participar!</h2>
                <p>La respuesta se ha enviado.</p>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state.get("pdf_doc"):
            st.download_button(
                "Descargar mi Certificado (PDF)",
                st.session_state.pdf_doc.getvalue(),
                f"Certificado_{st.session_state.cedula}.pdf",
                "application/pdf"
            )

        if st.button("Realizar otro registro", use_container_width=True):
            for key in ["cedula", "persona", "pdf_doc", "foto_data",
                        "cedula_input", "firma_final", "correo_enviado"]:
                st.session_state.pop(key, None)
            st.session_state.paso   = 0
            st.session_state.modulo = "registro_asistencia"
            st.rerun()
