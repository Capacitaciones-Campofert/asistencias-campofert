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
# LÓGICA DE SEGURIDAD Y ROLES
# =============================================================================

if rol_url == "Empleado":
    st.session_state.rol = "Empleado"

if 'rol' not in st.session_state:

    st.markdown("""
    <style>
    .hero-box{
        background: linear-gradient(135deg,#1B5E20,#2E7D32);
        padding: 2rem;
        border-radius: 18px;
        color: white;
        text-align:center;
        margin-bottom: -55px;
        box-shadow:0 10px 30px rgba(0,0,0,0.15);
    }

    .card-login{
        background:white;
        padding:2rem;
        border-radius:22px;
        box-shadow:0 10px 35px rgba(0,0,0,0.10);
        border:1px solid #efefef;
        margin-left:40px;
        margin-right:40px;
    }

    .titulo-login{
        font-size:2rem;
        font-weight:700;
        color:#1B5E20;
        text-align:center;
        margin-top:0.5rem;
    }

    .sub-login{
        text-align:center;
        color:#666;
        margin-bottom:1rem;
    }

    .mini{
        text-align:center;
        color:#888;
        font-size:0.85rem;
        margin-top:1rem;
    }

    .stButton > button{
        height:58px;
        font-size:16px;
        font-weight:700;
        border-radius:14px;
        border:none;
    }
    </style>
    """, unsafe_allow_html=True)

    # HERO SUPERIOR
    st.markdown("""
        <div class="hero-box">
            <h2>🌱 Bienvenido a Campofert People</h2>
            <p>Gestión Humana Digital • Asistencia • Certificados • Control Interno</p>
        </div>
    """, unsafe_allow_html=True)

    # TARJETA CENTRAL
    st.markdown('<div class="card-login">', unsafe_allow_html=True)

    c1,c2,c3 = st.columns([1,2,1])

    with c1:
        if os.path.exists("logo_campofert.png"):
            img = Image.open("logo_campofert.png")
            img.thumbnail((260,140))
            st.image(img)

    with c3:
        if os.path.exists("logo_campolab.png"):
            img2 = Image.open("logo_campolab.png")
            img.thumbnail((260,140))
            st.image(img2)

    st.markdown('<div class="titulo-login">Acceso Corporativo</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-login">Sistema Corporativo Campofert S.A.S</div>', unsafe_allow_html=True)

    col1,col2 = st.columns(2)

    with col1:
        if st.button("👷 COLABORADOR\nRegistro de asistencia", use_container_width=True):
            st.session_state.rol = "Empleado"
            st.rerun()

    with col2:
        if st.button("🛡️ ADMINISTRADOR\nPanel de gestión", use_container_width=True):
            st.session_state.rol = "Admin"
            st.rerun()

    st.markdown('<div class="mini">Campofert • Campolab • 2026</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

if st.session_state.rol == "Empleado":
    st.markdown("""
        <style>
            [data-testid="stSidebar"] {display: none;}
            #MainMenu {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)
    menu = "📋 Registro Asistencia"
else:
    st.sidebar.markdown("## 🌱 Campofert")
    st.sidebar.markdown("---")
    menu = st.sidebar.radio("Ir a:", ["🛠️ Panel Administrador", "📋 Registro Asistencia"])
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión"):
        del st.session_state["rol"]
        st.rerun()

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

# =============================================================================
# OPCIÓN 2: PANEL ADMINISTRADOR
# =============================================================================
elif menu == "🛠️ Panel Administrador":
    st.markdown("<h2 style='color:#1B5E20;'>🛠️ Panel de Gestión Humana</h2>", unsafe_allow_html=True)
    password = st.text_input("Introduce la clave de acceso:", type="password")

    if password == "campofert2026":
        tab1, tab2, tab3, tab4 = st.tabs([
            "🚀 Generador QR",
            "📊 Reportes en Vivo",
            "👥 Gestión de Personal",
            "📜 Histórico"
        ])

        with tab1:
            st.subheader("Generador de Capacitaciones")
            st.write("Escribe el tema para generar el link y QR de acceso directo para empleados.")
            nombre_cap = st.text_input("Nombre del Tema (Ej: Manejo de Extintores):")
            if nombre_cap:
                base_url = "https://asistencia-campofert.streamlit.app/"
                link_final = f"{base_url}?tema={nombre_cap.replace(' ', '+')}&rol=Empleado"
                col_a, col_b = st.columns(2)
                with col_a:
                    st.info("🔗 Link para compartir:")
                    st.code(link_final)
                with col_b:
                    st.write("📱 Código QR para proyectar:")
                    qr = qrcode.make(link_final)
                    buf = BytesIO()
                    qr.save(buf, format="PNG")
                    st.image(buf.getvalue(), caption="Escanear con el celular", width=220)

        with tab2:
            st.subheader("Monitor de Asistencias en Tiempo Real")
            try:
                df_asistencia = conn.read(worksheet="Hoja", ttl=0)
                temas_disponibles = df_asistencia['Tema'].unique().tolist()
                filtro_tema = st.selectbox("Filtrar por Tema:", ["TODOS"] + temas_disponibles)
                df_mostrar = df_asistencia.copy()
                if filtro_tema != "TODOS":
                    df_mostrar = df_asistencia[df_asistencia['Tema'] == filtro_tema]
                st.metric("Total Registrados", len(df_mostrar))
                st.dataframe(df_mostrar, use_container_width=True)
                csv = df_mostrar.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar Reporte (CSV)", csv, "reporte_asistencia.csv", "text/csv")
            except:
                st.error("Aún no hay registros en la base de datos.")

        with tab3:
            st.subheader("Gestión de Base de Datos de Personal")
            st.write("Sube el archivo Excel actualizado con los empleados autorizados.")
            archivo_subido = st.file_uploader("Subir nueva base de datos (Excel)", type=["xlsx"])
            if archivo_subido:
                with open("empleados.xlsx", "wb") as f:
                    f.write(archivo_subido.getbuffer())
                st.success("✅ Base de datos actualizada correctamente.")
            if os.path.exists("empleados.xlsx"):
                df_temp = pd.read_excel("empleados.xlsx")
                st.write("Personal actual en el sistema:")
                st.dataframe(df_temp.head(10))

        with tab4:
            st.subheader("Buscador de Certificados por Cédula")
            cedula_busqueda = st.text_input("Ingrese Cédula del trabajador:")
            if cedula_busqueda:
                df_asistencia = conn.read(worksheet="Hoja", ttl=0)
                registros = df_asistencia[df_asistencia['ID'].astype(str) == cedula_busqueda]
                if not registros.empty:
                    st.success(f"Se encontraron **{len(registros)}** capacitaciones para esta cédula:")
                    st.table(registros[['Fecha', 'Nombre', 'Tema']])
                    st.info("Para regenerar el PDF, el trabajador debe realizar el registro nuevamente o descargarlo desde el correo de respaldo.")
                else:
                    st.warning("No se encontraron registros para esa identificación.")

    elif password != "":
        st.error("🔑 Clave incorrecta. Acceso denegado.")
