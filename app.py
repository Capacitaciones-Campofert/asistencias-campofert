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
        <div style='text-align:center; padding: 2rem 0 1rem 0;'>
            <h1 style='color:#1B5E20; font-size:2rem;'>🌱 Sistema de Gestión Humana</h1>
            <p style='color:#555; font-size:1.1rem;'>Campofert S.A.S / Campolab</p>
            <hr style='border-color:#2E7D32; margin: 1rem 0;'>
            <p style='color:#777;'>¿Cómo deseas ingresar?</p>
        </div>
    """, unsafe_allow_html=True)

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("👤 SOY EMPLEADO\n(Registro de Asistencia)", use_container_width=True):
            st.session_state.rol = "Empleado"
            st.rerun()
    with col_r2:
        if st.button("🛠️ SOY ADMINISTRADOR\n(Panel de Gestión)", use_container_width=True):
            st.session_state.rol = "Admin"
            st.rerun()
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
        st.session_state.rol = None
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
# GENERACIÓN DE PDF CON DISEÑO CORPORATIVO
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Franja verde superior (más alta para logos + título)
    p.setFillColorRGB(0.18, 0.37, 0.13)
    p.rect(0, height - 130, width, 130, fill=1, stroke=0)

    # Franja amarilla delgada debajo
    p.setFillColorRGB(0.98, 0.66, 0.15)
    p.rect(0, height - 138, width, 8, fill=1, stroke=0)

    # Logos dentro de la franja (bien centrados verticalmente)
    try:
        if os.path.exists("logo_campofert.png"):
            img_cf = Image.open("logo_campofert.png")
            p.drawImage(ImageReader(img_cf), 50, height - 90, width=120, preserveAspectRatio=True, mask='auto')
        if os.path.exists("logo_campolab.png"):
            img_cl = Image.open("logo_campolab.png")
            p.drawImage(ImageReader(img_cl), 440, height - 90, width=120, preserveAspectRatio=True, mask='auto')
    except:
        pass

    # Título blanco sobre verde (centrado en la franja)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 15)
    p.drawCentredString(width / 2, height - 65, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 11)
    p.drawCentredString(width / 2, height - 85, "CAMPOFERT S.A.S / CAMPOLAB")

    # Datos del participante
    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 11)
    y_info = 520
    p.drawString(100, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(100, y_info - 22, f"Identificación: {datos['ID']}")
    p.drawString(100, y_info - 44, f"Empresa: {datos['Empresa']}")
    p.drawString(100, y_info - 66, f"Cargo: {datos.get('Cargo', 'NO REGISTRA')}")

    # Tema en verde
    p.setFillColorRGB(0.18, 0.37, 0.13)
    p.setFont("Helvetica-Bold", 11)
    p.drawString(100, y_info - 88, f"Tema: {datos['Tema']}")

    p.setFillColorRGB(0, 0, 0)
    p.setFont("Helvetica", 11)
    p.drawString(100, y_info - 110, f"Fecha/Hora: {datos['Fecha']}")

    # Línea divisoria verde
    p.setStrokeColorRGB(0.18, 0.37, 0.13)
    p.setLineWidth(1.5)
    p.line(100, y_info - 120, 510, y_info - 120)

    # Foto
    if imagen_foto is not None:
        try:
            img_foto = Image.open(imagen_foto)
            p.drawImage(ImageReader(img_foto), (width/2)-90, 240, width=180, height=135, preserveAspectRatio=True)
        except:
            pass

    # Firma
    if imagen_firma is not None:
        try:
            img_f = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
            p.drawImage(ImageReader(img_f), (width/2)-75, 155, width=150, height=70, mask='auto')
        except:
            pass

    # Línea firma amarilla
    p.setStrokeColorRGB(0.98, 0.66, 0.15)
    p.setLineWidth(2)
    p.line((width/2)-80, 155, (width/2)+80, 155)

    p.setFillColorRGB(0.18, 0.37, 0.13)
    p.setFont("Helvetica-Oblique", 10)
    p.drawCentredString(width/2, 140, "Firma Digital Autenticada")

    # Franja verde inferior
    p.setFillColorRGB(0.18, 0.37, 0.13)
    p.rect(0, 0, width, 40, fill=1, stroke=0)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica", 8)
    p.drawCentredString(width/2, 15, "Campofert S.A.S / Campolab — Documento generado digitalmente")

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
        st.image(Image.open("logo_campofert.png"), width=160)
with col_logo3:
    if os.path.exists("logo_campolab.png"):
        st.image(Image.open("logo_campolab.png"), width=160)

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
