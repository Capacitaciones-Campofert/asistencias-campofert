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
    page_title="Campofert - Registro de Asistencia",
    layout="centered",
    page_icon="🌱"
)

# =============================================================================
# SESSION STATE
# =============================================================================
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
    .stApp { background-color: #F5F5F0; }
    [data-testid="stSidebar"] { background-color: #1B5E20; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }
    .stButton > button {
        background-color: #2E7D32; color: white; border: none;
        border-radius: 8px; font-weight: bold; padding: 0.5rem 1rem;
        transition: background-color 0.3s;
    }
    .stButton > button:hover { background-color: #F9A825; color: #1B5E20; }
    h1, h2, h3 { color: #1B5E20; }
    .stTextInput > div > div > input {
        border: 2px solid #2E7D32; border-radius: 6px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #F9A825; box-shadow: 0 0 0 2px rgba(249,168,37,0.3);
    }
    [data-testid="stMetricValue"] { color: #2E7D32; font-weight: bold; }
    .stTabs [data-baseweb="tab"] { color: #2E7D32; font-weight: bold; }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid #F9A825 !important; color: #1B5E20 !important;
    }
    footer { visibility: hidden; }
    .stDownloadButton > button {
        background-color: #F9A825; color: #1B5E20;
        font-weight: bold; border: none; border-radius: 8px;
    }
    .stDownloadButton > button:hover { background-color: #2E7D32; color: white; }
</style>
"""
st.markdown(CSS_CORPORATIVO, unsafe_allow_html=True)

# =============================================================================
# CONEXIÓN A DATOS
# =============================================================================
conn = st.connection("gsheets", type=GSheetsConnection)

# =============================================================================
# CREDENCIALES DESDE SECRETS
# Asegúrate de tener en .streamlit/secrets.toml:
#   email_user     = "gestionhumanacpfert@gmail.com"
#   email_password = "eliwdxcfoseragcn"
#   admin_password = "campofert2026"
# =============================================================================
EMAIL_USER = st.secrets.get("email_user", "gestionhumanacpfert@gmail.com")
EMAIL_PASS = st.secrets.get("email_password", "")
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
@st.cache_data(ttl=3600, show_spinner=False)
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
        nueva_fila = pd.DataFrame([{
            "Fecha":   datos["Fecha"],
            "ID":      str(datos["ID"]),
            "Nombre":  datos["Nombre"],
            "Empresa": datos["Empresa"],
            "Cargo":   datos.get("Cargo", "NO REGISTRA"),
            "Tema":    datos["Tema"],
        }])
        actual = conn.read(worksheet="Hoja")
        df_final = nueva_fila if (actual is None or actual.empty) \
                   else pd.concat([actual, nueva_fila], ignore_index=True)
        conn.update(worksheet="Hoja", data=df_final)
        leer_asistencias.clear()
        return True
    except Exception as e:
        st.error(f"Error guardando en Google Sheets: {e}")
        return False

# =============================================================================
# CORREO DIAGNÓSTICO
# =============================================================================
def enviar_respaldo_async(datos, pdf_buffer):
    st.write("🔵 Intentando enviar correo...")
    try:
        srv = smtplib.SMTP("smtp.gmail.com", 587)
        srv.starttls()
        st.write(f"🔵 Conectado. Usuario: {EMAIL_USER} | Pass: {EMAIL_PASS[:4]}****")
        srv.login(EMAIL_USER, EMAIL_PASS)
        st.write("✅ Login exitoso")
        srv.quit()
    except Exception as e:
        st.error(f"❌ ERROR: {e}")
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
if rol_url and rol_url.lower() == "empleado":
    st.session_state.rol = "Empleado"

if st.session_state.rol is None:

    st.markdown("""
    <style>
    .stApp { background: linear-gradient(180deg,#f4f6f2,#eef3ef); }
    .hero-gerencia {
        background: linear-gradient(135deg,#0f4d1c,#1b5e20,#2e7d32);
        padding: 38px 25px; border-radius: 26px; text-align:center;
        color:white; box-shadow:0 18px 40px rgba(0,0,0,.16); margin-bottom:18px;
    }
    .hero-gerencia h1 { margin:0; font-size:44px; font-weight:800; }
    .hero-gerencia p  { margin-top:10px; font-size:19px; }
    .hero-mini        { margin-top:8px; font-size:15px; opacity:.92; }
    .titulo-acceso    { text-align:center; color:#1B5E20; font-size:36px; font-weight:800; margin-top:8px; }
    .sub-acceso       { text-align:center; color:#6b7280; font-size:16px; margin-bottom:18px; }
    .stButton > button {
        height:70px !important; border-radius:18px !important; font-size:22px !important;
        font-weight:800 !important; border:none !important;
        background:linear-gradient(135deg,#1b5e20,#2e7d32) !important;
        color:white !important; box-shadow:0 10px 22px rgba(27,94,32,.20);
    }
    .stButton > button:hover { transform:translateY(-2px); }
    .footer-premium { text-align:center; color:#7b7b7b; margin-top:18px; font-size:15px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="hero-gerencia">
        <h1>🌱 Campofert People</h1>
        <p>Plataforma Oficial de Gestión Humana</p>
        <div class="hero-mini">
            Asistencia • Certificados • Administración • Indicadores • Control Interno
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        l1, l2, l3 = st.columns([1, 2, 1])
        with l1:
            if "campofert" in LOGOS:
                st.image(LOGOS["campofert"], width=150)
        with l3:
            if "campolab" in LOGOS:
                st.image(LOGOS["campolab"], width=150)

        st.markdown('<div class="titulo-acceso">Acceso Corporativo</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-acceso">Seleccione el perfil para ingresar</div>', unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            # Al hacer clic en COLABORADOR → va a la pantalla de autorización (paso 0)
            if st.button("👷 COLABORADOR", use_container_width=True):
                st.session_state.rol  = "Empleado"
                st.session_state.paso = 0          # Empezar en autorización
                st.rerun()
        with c2:
            if st.button("🛡️ ADMINISTRADOR", use_container_width=True):
                st.session_state.esperando_clave = True
                st.rerun()

        # ── LOGIN ADMIN CON ENTER ──────────────────────────────────────────────
        # Usamos st.form para que al presionar Enter se envíe automáticamente
        if st.session_state.get("esperando_clave"):
            st.markdown("---")
            with st.form("login_admin", clear_on_submit=False):
                clave = st.text_input(
                    "🔑 Ingrese Clave de Administrador:",
                    type="password",
                    placeholder="Presione Enter o haga clic en Entrar"
                )
                col_bt1, col_bt2 = st.columns(2)
                with col_bt1:
                    entrar = st.form_submit_button("✅ Entrar")
                with col_bt2:
                    cancelar = st.form_submit_button("❌ Cancelar")

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
            '<div class="footer-premium">Campofert S.A.S • Campolab • Versión Ejecutiva 2026</div>',
            unsafe_allow_html=True
        )

    st.stop()

# =============================================================================
# BARRA SUPERIOR (botón volver + logos + título)
# =============================================================================
col_volver, col_vacia = st.columns([1, 4])
with col_volver:
    if st.button("⬅️ Inicio", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

st.write("")

col_logo1, _, col_logo3 = st.columns([1, 1, 1])
with col_logo1:
    if "campofert" in LOGOS:
        st.image(LOGOS["campofert"], width=200)
with col_logo3:
    if "campolab" in LOGOS:
        st.image(LOGOS["campolab"], width=200)

st.markdown("<h1 style='text-align:center; color:#1B5E20;'>Registro de Capacitación</h1>",
            unsafe_allow_html=True)
st.markdown("---")

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
        st.markdown("## 🛡️ Panel Administrativo")
        st.markdown("Gestión Humana • Campofert")
        st.markdown("---")
        menu = st.radio("Seleccione módulo", [
            "⚙️ Configurar Tema",
            "📋 Registro Asistencia",
            "👥 Empleados",
            "📤 Cargar Archivo",
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

    if menu == "👥 Empleados":
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

    elif menu == "📤 Cargar Archivo":
        st.markdown("## 📤 Actualizar Base de Personal")
        archivo = st.file_uploader("Subir archivo Excel actualizado", type=["xlsx"])
        if archivo is not None:
            with open("empleados.xlsx", "wb") as f:
                f.write(archivo.getbuffer())
            obtener_datos.clear()
            st.success("✅ Archivo actualizado correctamente.")

    elif menu == "📊 Dashboard":
        st.markdown("## 📊 Dashboard Ejecutivo")
    
        try:
            df = leer_asistencias()
    
            if df.empty:
                st.warning("No hay registros.")
            else:
                # -----------------------------
                # LIMPIEZA
                # -----------------------------
                df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce", dayfirst=True)
                df = df.dropna(subset=["Fecha"])
    
                # -----------------------------
                # FILTROS
                # -----------------------------
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
                            value=(df["Fecha"].min(), df["Fecha"].max())
                        )
    
                # -----------------------------
                # FILTRADO
                # -----------------------------
                df_filtrado = df[
                    (df["Empresa"].isin(empresa_sel)) &
                    (df["Tema"].isin(tema_sel))
                ].copy()
    
                if len(fecha_sel) == 2:
                    inicio, fin = fecha_sel
                    df_filtrado = df_filtrado[
                        (df_filtrado["Fecha"].dt.date >= inicio) &
                        (df_filtrado["Fecha"].dt.date <= fin)
                    ]
    
                if df_filtrado.empty:
                    st.warning("⚠️ No hay datos con los filtros seleccionados.")
                    st.stop()
    
                # -----------------------------
                # KPIs
                # -----------------------------
                total = len(df_filtrado)
                personas = df_filtrado["ID"].nunique()
                temas = df_filtrado["Tema"].nunique()
                empresas = df_filtrado["Empresa"].nunique()
    
                # -----------------------------
                # PERIODO ANTERIOR
                # -----------------------------
                if len(fecha_sel) == 2:
                    dias = (fin - inicio).days + 1
                    inicio_ant = inicio - pd.Timedelta(days=dias)
                    fin_ant = inicio - pd.Timedelta(days=1)
    
                    df_anterior = df[
                        (df["Fecha"].dt.date >= inicio_ant) &
                        (df["Fecha"].dt.date <= fin_ant)
                    ]
    
                    total_ant = len(df_anterior)
                else:
                    total_ant = 0
    
                delta_total = total - total_ant
    
                # -----------------------------
                # 🎨 CSS TARJETAS
                # -----------------------------
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
                .card h3 {
                    margin: 0;
                    font-size: 14px;
                    color: #6B7280;
                }
                .card h1 {
                    margin: 5px 0;
                    font-size: 30px;
                    color: #1B5E20;
                }
                .up { color:#2E7D32; font-weight:bold; }
                .down { color:#C62828; font-weight:bold; }
                </style>
                """, unsafe_allow_html=True)
    
                def delta_html(valor):
                    if valor > 0:
                        return f"<span class='up'>▲ {valor}</span>"
                    elif valor < 0:
                        return f"<span class='down'>▼ {valor}</span>"
                    else:
                        return "<span>0</span>"
    
                # -----------------------------
                # KPI VISUAL PRO
                # -----------------------------
                k1, k2, k3, k4 = st.columns(4)
    
                with k1:
                    st.markdown(f"""
                    <div class="card">
                        <h3>📋 Registros</h3>
                        <h1>{total}</h1>
                        {delta_html(delta_total)}
                    </div>
                    """, unsafe_allow_html=True)
    
                with k2:
                    st.markdown(f"""
                    <div class="card">
                        <h3>👥 Personas</h3>
                        <h1>{personas}</h1>
                    </div>
                    """, unsafe_allow_html=True)
    
                with k3:
                    st.markdown(f"""
                    <div class="card">
                        <h3>📚 Capacitaciones</h3>
                        <h1>{temas}</h1>
                    </div>
                    """, unsafe_allow_html=True)
    
                with k4:
                    st.markdown(f"""
                    <div class="card">
                        <h3>🏢 Empresas</h3>
                        <h1>{empresas}</h1>
                    </div>
                    """, unsafe_allow_html=True)
    
                st.markdown("<br>", unsafe_allow_html=True)
    
                # -----------------------------
                # 📈 TENDENCIA
                # -----------------------------
                df_fecha = df_filtrado.copy()
                df_fecha["Fecha"] = df_fecha["Fecha"].dt.date  # elimina hora
                df_fecha = df_fecha.groupby("Fecha").size().reset_index(name="Registros")
                
                fig_line = px.line(
                    df_fecha,
                    x="Fecha",
                    y="Registros",
                    markers=True,
                    text="Registros"
                )
                
                fig_line.update_traces(
                    line=dict(color="#2E7D32", width=4, shape="spline"),  # curva suave
                    marker=dict(size=10, color="#2E7D32"),
                    textposition="top center",
                    textfont=dict(
                        size=16,
                        color="#1B5E20",
                        family="Arial Black"
                    ),
                    texttemplate="<b>%{y}</b>",  # 🔥 negrilla real en números
                    hovertemplate="<b>%{x}</b><br>Registros: %{y}<extra></extra>"
                )
                
                fig_line.update_layout(
                    title="📈 Evolución de Asistencias",
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                    margin=dict(l=10, r=10, t=50, b=10),
                
                    xaxis=dict(
                        title="",
                        showgrid=False,
                        showline=False,
                        tickformat="%d-%b"
                    ),
                
                    yaxis=dict(
                        visible=False  # elimina eje izquierdo
                    ),
                
                    font=dict(
                        family="Arial",
                        size=12,
                        color="#1B5E20"
                    )
                )
                
                st.plotly_chart(fig_line, use_container_width=True)
                
                st.markdown("---")
    
                # -----------------------------
                # 📊 DISTRIBUCIÓN
                # -----------------------------
                empresa_df = df_filtrado["Empresa"].value_counts().reset_index()
                empresa_df.columns = ["Empresa", "Cantidad"]
                
                fig_bar = px.bar(
                    empresa_df,
                    x="Empresa",
                    y="Cantidad",
                    text="Cantidad"
                )
                
                fig_bar.update_traces(
                    marker=dict(color="#F9A825"),  # amarillo corporativo
                    textposition="outside",        # número arriba
                    textfont=dict(
                        size=16,
                        color="#1B5E20",
                        family="Arial Black"       # negrilla
                    ),
                    texttemplate="<b>%{y}</b>",    # 🔥 números en negrilla real
                    hovertemplate="<b>%{x}</b><br>Registros: %{y}<extra></extra>"
                )
                
                fig_bar.update_layout(
                    title="📊 Distribución por Empresa",
                
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                
                    margin=dict(l=10, r=10, t=50, b=10),
                
                    xaxis=dict(
                        title="",
                        showgrid=False,
                        showline=False
                    ),
                
                    yaxis=dict(
                        visible=False  # 🔥 quita eje izquierdo (igual que la línea)
                    ),
                
                    font=dict(
                        family="Arial",
                        size=12,
                        color="#1B5E20"
                    )
                )
                
                st.plotly_chart(fig_bar, use_container_width=True)
                
                st.markdown("---")
    
                # -----------------------------
                # 📋 RESUMEN
                # -----------------------------
                st.subheader("📋 Resumen Ejecutivo")
    
                resumen = df_filtrado.groupby("Empresa").agg(
                    Registros=("ID", "count"),
                    Personas=("ID", "nunique")
                ).reset_index()
    
                st.dataframe(resumen, use_container_width=True)
    
        except Exception as e:
            st.error(f"Error Dashboard: {e}")
            
    elif menu == "📄 Historial":
        st.markdown("## 📄 Historial de Asistencias")
        try:
            df  = leer_asistencias()
            ced = st.text_input("Buscar por cédula")
            if ced:
                df = df[df["ID"].astype(str) == ced]
            st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning(f"Error historial: {e}")

    elif menu == "📁 Reportes":
        st.markdown("## 📁 Reportes")
        try:
            df  = leer_asistencias()
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Descargar Reporte CSV", csv,
                               "reporte_asistencia.csv", "text/csv")
            excel = BytesIO()
            with pd.ExcelWriter(excel, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Reporte")
            st.download_button("📥 Descargar Reporte Excel", excel.getvalue(),
                               "reporte_asistencia.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
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
                Autorizo a <strong>Campofert S.A.S.</strong>, en calidad de responsable del
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
            if st.button("✅ Acepto y Continuar", use_container_width=True):
                st.session_state.paso = 1
                st.rerun()
        with col_b:
            if st.button("❌ No Acepto / Salir", use_container_width=True):
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

        cedula = st.text_input(
            "Por favor, ingresa tu Cédula:",
            key="cedula_input"
        ).strip()

        if cedula:
            res = (
                df_maestro[df_maestro["ID"].astype(str) == cedula]
                if df_maestro is not None else pd.DataFrame()
            )

            if not res.empty:
                st.session_state.persona = res.iloc[0].to_dict()
                st.session_state.cedula  = cedula
                st.success(f"✅ Hola, **{st.session_state.persona['Apellidos y Nombres']}**. ¡Bienvenido!")
                if st.button("Continuar al registro ➡️"):
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

                    if st.form_submit_button("Registrarme y Continuar ➡️"):
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
                            st.session_state.paso   = 2
                            st.rerun()
                        else:
                            st.error("Completa todos los campos.")

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 2 → FOTO
    # ─────────────────────────────────────────────────────────────────────────
    elif st.session_state.paso == 2:
        st.markdown("### 📸 Captura de Identidad")
        st.markdown("<p style='color:#555;'>Tómate una foto para validar tu identidad.</p>",
                    unsafe_allow_html=True)
        foto = st.camera_input("Foto de validación")
        if foto:
            st.session_state.foto_data = foto
            if st.button("Ir a la firma ✍️"):
                st.session_state.paso = 3
                st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 3 → FIRMA
    # ─────────────────────────────────────────────────────────────────────────
    elif st.session_state.paso == 3:
    
        st.markdown("### ✍️ Firma Digital")
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
    
        if st.button("Finalizar y Generar Certificado ✅"):
    
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
    
                pass
    
                pdf.seek(0)
                st.session_state.pdf_doc = pdf
                st.session_state.paso = 4
                st.rerun()

    # ─────────────────────────────────────────────────────────────────────────
    # PASO 4 → RESULTADO
    # ─────────────────────────────────────────────────────────────────────────
    elif st.session_state.paso == 4:
        st.balloons()
        st.markdown("""
            <div style='background-color:#E8F5E9; border:2px solid #2E7D32;
                        padding:20px; border-radius:10px; text-align:center;'>
                <h2 style='color:#1B5E20;'>🎉 ¡Registro Exitoso!</h2>
                <p>Tu asistencia ha sido guardada correctamente.</p>
            </div>
        """, unsafe_allow_html=True)

        if st.session_state.get("pdf_doc"):
            st.download_button(
                "📥 Descargar mi Certificado (PDF)",
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
