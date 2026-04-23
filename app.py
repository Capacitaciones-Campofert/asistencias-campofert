import streamlit as st
import pandas as pd
import os
import io
import pytz
import qrcode
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

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Campofert - Registro de Asistencia", layout="centered", page_icon="🌱")

# --- COLORES CORPORATIVOS CAMPOFERT ---
CSS_CORPORATIVO = """
<style>
    .stApp { background-color: #F5F5F0; }

    [data-testid="stSidebar"] { background-color: #1B5E20; }
    [data-testid="stSidebar"] * { color: #FFFFFF !important; }

    .stButton > button {
        background-color: #2E7D32;
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: bold;
        padding: 0.5rem 1rem;
        transition: background-color 0.3s;
    }
    .stButton > button:hover {
        background-color: #F9A825;
        color: #1B5E20;
    }

    h1, h2, h3 { color: #1B5E20; }

    .stTextInput > div > div > input {
        border: 2px solid #2E7D32;
        border-radius: 6px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #F9A825;
        box-shadow: 0 0 0 2px rgba(249,168,37,0.3);
    }

    [data-testid="stMetricValue"] { color: #2E7D32; font-weight: bold; }

    .stTabs [data-baseweb="tab"] { color: #2E7D32; font-weight: bold; }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid #F9A825 !important;
        color: #1B5E20 !important;
    }

    footer { visibility: hidden; }

    .stDownloadButton > button {
        background-color: #F9A825;
        color: #1B5E20;
        font-weight: bold;
        border: none;
        border-radius: 8px;
    }
    .stDownloadButton > button:hover {
        background-color: #2E7D32;
        color: white;
    }
</style>
"""
st.markdown(CSS_CORPORATIVO, unsafe_allow_html=True)

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CONFIGURACIÓN DE CORREO ---
EMAIL_USER = "gestionhumanacpfert@gmail.com"
EMAIL_PASS = st.secrets.get("email_password", "bhbwshtosozexhcr")

# --- LEER TEMA DESDE EL URL ---
params = st.query_params
tema_raw = params.get("tema") or params.get("Tema") or "CAPACITACIÓN GENERAL"
tema_actual = tema_raw.replace("+", " ").upper()
rol_url = params.get("rol")

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
        except Exception as e:
            st.error(f"Error al leer empleados.xlsx: {e}")
    return None

def enviar_respaldo_gestion_humana(datos, pdf_buffer):
    mi_correo = "gestionhumanacpfert@gmail.com"
    password = "bhbwshtosozexhcr"

    msg = MIMEMultipart()
    msg['From'] = mi_correo
    msg['To'] = mi_correo
    msg['Subject'] = f"✅ Nueva Asistencia: {datos['Nombre']} - {datos['Tema']}"

    cuerpo_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="border: 1px solid #2e7d32; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2e7d32;">Respaldo de Capacitación - Campofert</h2>
                <p><strong>Empleado:</strong> {datos['Nombre']}</p>
                <p><strong>Cédula:</strong> {datos['ID']}</p>
                <p><strong>Empresa:</strong> {datos['Empresa']}</p>
                <p><strong>Cargo:</strong> {datos.get('Cargo', 'NO REGISTRA')}</p>
                <p><strong>Tema:</strong> {datos['Tema']}</p>
                <p><strong>Fecha:</strong> {datos['Fecha']}</p>
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(cuerpo_html, 'html'))

    pdf_buffer.seek(0)
    adjunto = MIMEBase('application', 'octet-stream')
    adjunto.set_payload(pdf_buffer.read())
    encoders.encode_base64(adjunto)
    adjunto.add_header('Content-Disposition', f"attachment; filename=Asistencia_{datos['ID']}.pdf")
    msg.attach(adjunto)

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(mi_correo, password)
        server.sendmail(mi_correo, mi_correo, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Error correo: {e}")
        return False

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
# LÓGICA DE SEGURIDAD Y ROLES - LOGIN MULTINACIONAL CAMPOFERT
# =============================================================================

if rol_url == "Empleado":
    st.session_state.rol = "Empleado"

if 'rol' not in st.session_state:

    st.markdown("""
    <style>

    .stApp{
        background: linear-gradient(180deg,#f4f6f2,#eef3ef);
    }

    .hero-gerencia{
        background: linear-gradient(135deg,#0f4d1c,#1b5e20,#2e7d32);
        padding: 38px 25px;
        border-radius: 26px;
        text-align:center;
        color:white;
        box-shadow:0 18px 40px rgba(0,0,0,.16);
        margin-bottom:18px;
    }

    .hero-gerencia h1{
        margin:0;
        font-size:44px;
        font-weight:800;
    }

    .hero-gerencia p{
        margin-top:10px;
        font-size:19px;
    }

    .hero-mini{
        margin-top:8px;
        font-size:15px;
        opacity:.92;
    }

    .titulo-acceso{
        text-align:center;
        color:#1B5E20;
        font-size:36px;
        font-weight:800;
        margin-top:8px;
    }

    .sub-acceso{
        text-align:center;
        color:#6b7280;
        font-size:16px;
        margin-bottom:18px;
    }

    .stButton > button{
        height:70px !important;
        border-radius:18px !important;
        font-size:22px !important;
        font-weight:800 !important;
        border:none !important;
        background:linear-gradient(135deg,#1b5e20,#2e7d32) !important;
        color:white !important;
        box-shadow:0 10px 22px rgba(27,94,32,.20);
    }

    .stButton > button:hover{
        transform:translateY(-2px);
    }

    .footer-premium{
        text-align:center;
        color:#7b7b7b;
        margin-top:18px;
        font-size:15px;
    }

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

        l1,l2,l3 = st.columns([1,2,1])

        with l1:
            if os.path.exists("logo_campofert.png"):
                st.image("logo_campofert.png", width=150)

        with l3:
            if os.path.exists("logo_campolab.png"):
                st.image("logo_campolab.png", width=150)

        st.markdown('<div class="titulo-acceso">Acceso Corporativo</div>', unsafe_allow_html=True)
        st.markdown('<div class="sub-acceso">Seleccione el perfil para ingresar</div>', unsafe_allow_html=True)

        c1,c2 = st.columns(2)

        with c1:
            if st.button("👷 COLABORADOR", use_container_width=True):
                st.session_state.rol = "Empleado"
                st.rerun()

        with c2:
            if st.button("🛡️ ADMINISTRADOR", use_container_width=True):
                st.session_state.rol = "Admin"
                st.rerun()

        st.markdown('<div class="footer-premium">Campofert S.A.S • Campolab • Versión Ejecutiva 2026</div>', unsafe_allow_html=True)

    st.stop()
# =============================================================================
# MENÚ SEGÚN ROL + PANEL ADMIN V3.0 FINAL (SIN CONFLICTOS)
# Reemplaza TODO tu bloque actual desde "MENÚ SEGÚN ROL"
# hasta antes de las funciones.
# =============================================================================

if st.session_state.rol == "Empleado":

    # Oculta menú lateral para empleados
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {display:none;}
        #MainMenu {visibility:hidden;}
        header {visibility:hidden;}
    </style>
    """, unsafe_allow_html=True)

    menu = "📋 Registro Asistencia"

else:

    # ===============================
    # SIDEBAR ADMINISTRADOR
    # ===============================
    with st.sidebar:

        if os.path.exists("logo_campofert.png"):
            st.image("logo_campofert.png", width=180)

        st.markdown("## 🛡️ Panel Administrativo")
        st.markdown("Gestión Humana • Campofert")
        st.markdown("---")

        menu = st.radio(
            "Seleccione módulo",
            [
                "📋 Registro Asistencia",
                "👥 Empleados",
                "📤 Cargar Archivo",
                "📊 Dashboard",
                "📄 Historial",
                "📁 Reportes"
            ]
        )

        st.markdown("---")

        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            del st.session_state["rol"]
            st.rerun()


# =============================================================================
# BLOQUES ADMINISTRATIVOS V3.0
# =============================================================================

if st.session_state.rol == "Admin":

    # -------------------------------------------------
    # MÓDULO EMPLEADOS
    # -------------------------------------------------
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

            st.download_button(
                "📥 Descargar Excel",
                excel.getvalue(),
                "empleados.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        else:
            st.warning("No existe archivo empleados.xlsx")

    # -------------------------------------------------
    # CARGAR ARCHIVO
    # -------------------------------------------------
    elif menu == "📤 Cargar Archivo":

        st.markdown("## 📤 Actualizar Base de Personal")

        archivo = st.file_uploader(
            "Subir archivo Excel actualizado",
            type=["xlsx"]
        )

        if archivo is not None:

            with open("empleados.xlsx", "wb") as f:
                f.write(archivo.getbuffer())

            st.success("✅ Archivo actualizado correctamente.")
            st.balloons()

    # -------------------------------------------------
    # DASHBOARD
    # -------------------------------------------------
    elif menu == "📊 Dashboard":

        st.markdown("## 📊 Dashboard Ejecutivo")

        try:
            df = conn.read(worksheet="Hoja", ttl=0)

            total = len(df)
            personas = df["ID"].nunique()
            temas = df["Tema"].nunique()

            c1, c2, c3 = st.columns(3)

            c1.metric("Registros", total)
            c2.metric("Personas", personas)
            c3.metric("Capacitaciones", temas)

            st.markdown("### Últimos registros")
            st.dataframe(df.tail(20), use_container_width=True)

        except:
            st.warning("Sin datos disponibles.")

    # -------------------------------------------------
    # HISTORIAL
    # -------------------------------------------------
    elif menu == "📄 Historial":

        st.markdown("## 📄 Historial de Asistencias")

        try:
            df = conn.read(worksheet="Hoja", ttl=0)

            ced = st.text_input("Buscar por cédula")

            if ced:
                df = df[df["ID"].astype(str) == ced]

            st.dataframe(df, use_container_width=True)

        except:
            st.warning("Sin historial disponible.")

    # -------------------------------------------------
    # REPORTES
    # -------------------------------------------------
    elif menu == "📁 Reportes":

        st.markdown("## 📁 Reportes")

        try:
            df = conn.read(worksheet="Hoja", ttl=0)

            csv = df.to_csv(index=False).encode("utf-8")

            st.download_button(
                "📥 Descargar Reporte CSV",
                csv,
                "reporte_asistencia.csv",
                "text/csv"
            )

            excel = BytesIO()
            with pd.ExcelWriter(excel, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Reporte")

            st.download_button(
                "📥 Descargar Reporte Excel",
                excel.getvalue(),
                "reporte_asistencia.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except:
            st.warning("No hay información para exportar.")

# =============================================================================
# PDF MULTINACIONAL CAMPOFERT 2026 - AJUSTADO
# Cambios solicitados:
# ✅ Logo normal con fondo blanco
# ✅ Sin marca de agua
# ✅ Nombre de capacitación en negrilla
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    import io
    import os
    import random
    from PIL import Image, ImageDraw
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter

    # -------------------------------------------------------------------------
    # COLORES
    # -------------------------------------------------------------------------
    verde = (0.10, 0.36, 0.16)
    verde2 = (0.18, 0.52, 0.24)
    dorado = (0.95, 0.74, 0.12)
    gris = (0.96, 0.96, 0.96)

    codigo = f"CPF-2026-{random.randint(100000,999999)}"

    # -------------------------------------------------------------------------
    # FONDO
    # -------------------------------------------------------------------------
    p.setFillColorRGB(1,1,1)
    p.rect(0,0,width,height,fill=1,stroke=0)

    # -------------------------------------------------------------------------
    # MARCO
    # -------------------------------------------------------------------------
    p.setStrokeColorRGB(*verde)
    p.setLineWidth(1.4)
    p.roundRect(20,20,width-40,height-40,14)

    # -------------------------------------------------------------------------
    # ENCABEZADO
    # -------------------------------------------------------------------------
    p.setFillColorRGB(*verde)
    p.roundRect(20,height-125,width-40,105,14,fill=1,stroke=0)

    p.setFillColorRGB(*dorado)
    p.rect(20,height-125,width-40,5,fill=1,stroke=0)

    # -------------------------------------------------------------------------
    # LOGO NORMAL (SIN TRANSPARENCIA)
    # -------------------------------------------------------------------------
    try:
        if os.path.exists("logo_campofert.png"):
            img = Image.open("logo_campofert.png")
            p.drawImage(
                ImageReader(img),
                35,            # posición izquierda
                height-112,    # altura dentro franja
                width=95,
                height=72,
                preserveAspectRatio=True
            )
    except:
        pass
    
    # LOGO CAMPOLAB
    try:
        if os.path.exists("logo_campolab.png"):
            img2 = Image.open("logo_campolab.png")
            p.drawImage(
                ImageReader(img2),
                width - 130,        # posición derecha
                height - 112,       # misma altura
                width=95,
                height=72,
                preserveAspectRatio=True
        )
    except:
        pass
    
    # -------------------------------------------------------------------------
    # TITULOS
    # -------------------------------------------------------------------------
    p.setFillColorRGB(1,1,1)
    p.setFont("Helvetica-Bold",18)
    p.drawCentredString(width/2,height-63,"CERTIFICADO DE ASISTENCIA")

    p.setFont("Helvetica",10)
    p.drawCentredString(width/2,height-84,
        "Sistema de Gestión Humana y Seguridad en el Trabajo")

    p.setFont("Helvetica-Bold",8)
    p.drawRightString(width-35,height-38,codigo)

    # -------------------------------------------------------------------------
    # TEXTO CENTRAL
    # -------------------------------------------------------------------------
    p.setFillColorRGB(0,0,0)
    p.setFont("Helvetica",12)
    p.drawCentredString(width/2,610,
        "Por medio del presente documento se certifica que:")

    p.setFillColorRGB(*verde)
    p.setFont("Helvetica-Bold",24)
    p.drawCentredString(width/2,570,datos["Nombre"].upper())

    p.setFillColorRGB(0,0,0)
    p.setFont("Helvetica",12)
    p.drawCentredString(width/2,545,
        f"Identificado(a) con documento No. {datos['ID']}")

    # -------------------------------------------------------------------------
    # BLOQUE CAPACITACION
    # -------------------------------------------------------------------------
    p.setFillColorRGB(*gris)
    p.roundRect(60,445,width-120,75,10,fill=1,stroke=0)

    p.setFillColorRGB(*verde)
    p.setFont("Helvetica-Bold",11)
    p.drawString(80,495,"CAPACITACIÓN / ACTIVIDAD:")

    # NEGRILLA SOLICITADA
    p.setFillColorRGB(0,0,0)
    p.setFont("Helvetica-Bold",12)
    p.drawString(80,472,datos["Tema"])

    # -------------------------------------------------------------------------
    # DATOS
    # -------------------------------------------------------------------------
    p.setFont("Helvetica",11)
    p.drawString(80,420,f"Empresa: {datos['Empresa']}")
    p.drawString(80,400,f"Cargo: {datos.get('Cargo','NO REGISTRA')}")
    p.drawString(80,380,f"Fecha Registro: {datos['Fecha']}")

    # -------------------------------------------------------------------------
    # FOTO REDONDA
    # -------------------------------------------------------------------------

    base_y = 185   # altura base común
    
    if imagen_foto is not None:
        try:
            img = Image.open(imagen_foto).convert("RGB").resize((180,180))

            mask = Image.new("L",(180,180),0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0,0,180,180),fill=255)

            circular = Image.new("RGBA",(180,180))
            circular.paste(img,(0,0))
            circular.putalpha(mask)

            p.drawImage(
                ImageReader(circular),
                75,
                base_y,
                width=110,
                height=110,
                mask='auto'
            )

            p.setFont("Helvetica",8)
            p.drawCentredString(130, base_y - 12, "Validación Biométrica")

        except:
            pass

    # -------------------------------------------------------------------------
    # FIRMA
    # -------------------------------------------------------------------------
    if imagen_firma is not None:
        try:
            img_f = Image.fromarray(imagen_firma.astype("uint8"),"RGBA")

            p.drawImage(
                ImageReader(img_f),
                width-255,
                base_y + 28,
                width=145,
                height=55,
                mask='auto'
            )
        except:
            pass

    p.setStrokeColorRGB(*verde)
    p.line(width-275, base_y + 18, width-95, base_y + 18)

    p.setFont("Helvetica-Bold",10)
    p.drawCentredString(width-185, base_y + 3, "Firma del Trabajador")

    # -------------------------------------------------------------------------
    # QR
    # -------------------------------------------------------------------------
    try:
        import qrcode

        qr_data = f"""
        CERTIFICADO CAMPOFERT
        CODIGO: {codigo}
        NOMBRE: {datos['Nombre']}
        ID: {datos['ID']}
        TEMA: {datos['Tema']}
        FECHA: {datos['Fecha']}
        """

        qr = qrcode.make(qr_data)
        qr_buffer = io.BytesIO()
        qr.save(qr_buffer, format="PNG")
        qr_buffer.seek(0)

        p.drawImage(
            ImageReader(qr_buffer),
            width-130,
            55,
            width=65,
            height=65
        )
    except:
        pass

    # -------------------------------------------------------------------------
    # PIE
    # -------------------------------------------------------------------------
    p.setFillColorRGB(*verde2)
    p.roundRect(20,20,width-40,25,0,fill=1,stroke=0)

    p.setFillColorRGB(1,1,1)
    p.setFont("Helvetica",8)
    p.drawCentredString(
        width/2,
        30,
        "Documento digital oficial emitido por Campofert S.A.S."
    )

    p.showPage()
    p.save()
    buffer.seek(0)

    return buffer
# =============================================================================
# INTERFAZ
# =============================================================================

col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
with col_logo1:
    if os.path.exists("logo_campofert.png"):
        img = Image.open("logo_campofert.png")
        img.thumbnail((260, 120), Image.LANCZOS)
        st.image(img)
with col_logo3:
    if os.path.exists("logo_campolab.png"):
        img2 = Image.open("logo_campolab.png")
        img2.thumbnail((260, 120), Image.LANCZOS)
        st.image(img2)

st.markdown("<h1 style='text-align:center; color:#1B5E20;'>Registro de Capacitación</h1>", unsafe_allow_html=True)
st.markdown("---")

# =============================================================================
# OPCIÓN 1: REGISTRO DE ASISTENCIA
# =============================================================================
if menu == "📋 Registro Asistencia":
    st.markdown(f"""
        <div style='background-color:#E8F5E9; border-left:5px solid #2E7D32;
                    padding:12px 16px; border-radius:6px; margin-bottom:1rem;'>
            📋 <strong>TEMA ACTUAL:</strong> {tema_actual}
        </div>
    """, unsafe_allow_html=True)

    if 'paso' not in st.session_state:
        st.session_state.paso = 1

    df_maestro = obtener_datos()

    if st.session_state.paso == 1:
        cedula = st.text_input("Por favor, ingresa tu Cédula:").strip()
        if cedula:
            res = df_maestro[df_maestro['ID'].astype(str) == cedula] if df_maestro is not None else pd.DataFrame()

            if not res.empty:
                st.session_state.persona = res.iloc[0].to_dict()
                st.session_state.cedula = cedula
                st.success(f"✅ Hola, **{st.session_state.persona['Apellidos y Nombres']}**. ¡Bienvenido!")
                if st.button("Continuar al registro ➡️"):
                    st.session_state.paso = 2
                    st.rerun()
            else:
                st.warning("⚠️ Cédula no encontrada. Si eres contratista o personal nuevo, regístrate:")
                with st.form("registro_nuevo_empleado"):
                    nombre_nuevo = st.text_input("Nombres y Apellidos Completos:")
                    empresa_seleccionada = st.selectbox("Empresa:", ["CAMPOFERT", "CAMPOLAB", "TEMPORAL / CONTRATISTA"])
                    empresa_externa = ""
                    if empresa_seleccionada == "TEMPORAL / CONTRATISTA":
                        empresa_externa = st.text_input("¿A qué empresa perteneces?")
                    cargo_nuevo = st.text_input("Tu Cargo:")
                    if st.form_submit_button("Registrarme y Continuar ➡️"):
                        if nombre_nuevo and cargo_nuevo:
                            nom_emp = empresa_externa.upper() if empresa_seleccionada == "TEMPORAL / CONTRATISTA" else empresa_seleccionada
                            st.session_state.persona = {
                                'Apellidos y Nombres': nombre_nuevo.upper(),
                                'Empresa': nom_emp,
                                'Cargo': cargo_nuevo.upper()
                            }
                            st.session_state.cedula = cedula
                            st.session_state.paso = 2
                            st.rerun()
                        else:
                            st.error("Completa todos los campos.")

    elif st.session_state.paso == 2:
        st.markdown("### 📸 Captura de Identidad")
        st.markdown("<p style='color:#555;'>Tómate una foto para validar tu identidad.</p>", unsafe_allow_html=True)
        foto = st.camera_input("Foto de validación")
        if foto:
            st.session_state.foto_data = foto
            if st.button("Ir a la firma ✍️"):
                st.session_state.paso = 3
                st.rerun()

    elif st.session_state.paso == 3:
        st.markdown("### ✍️ Firma Digital")
        st.markdown("<p style='color:#555;'>Dibuja tu firma en el recuadro blanco.</p>", unsafe_allow_html=True)
        canvas_res = st_canvas(
            stroke_width=3,
            stroke_color="#1B5E20",
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
                if guardar_en_google_sheets(datos_asistencia):
                    pdf = generar_pdf(datos_asistencia, canvas_res.image_data, st.session_state.get('foto_data'))
                    enviar_respaldo_gestion_humana(datos_asistencia, pdf)
                    pdf.seek(0)
                    st.session_state.pdf_doc = pdf
                    st.session_state.paso = 4
                    st.rerun()

    elif st.session_state.paso == 4:
        st.balloons()
        st.markdown("""
            <div style='background-color:#E8F5E9; border:2px solid #2E7D32;
                        padding:20px; border-radius:10px; text-align:center;'>
                <h2 style='color:#1B5E20;'>🎉 ¡Registro Exitoso!</h2>
                <p>Tu asistencia ha sido guardada correctamente.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.session_state.get('pdf_doc'):
            st.download_button(
                "📥 Descargar mi Certificado (PDF)",
                st.session_state.pdf_doc.getvalue(),
                f"Certificado_{st.session_state.cedula}.pdf",
                "application/pdf"
            )
        if st.button("Realizar otro registro"):
            for key in ['cedula', 'persona', 'pdf_doc', 'foto_data']:
                if key in st.session_state:
                    del st.session_state[key]
            st.session_state.paso = 1
            st.rerun()
