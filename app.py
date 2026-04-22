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

# --- CONEXIÓN A GOOGLE SHEETS ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CONFIGURACIÓN DE CORREO (SECRETS) ---
# Configura esto en el panel de Streamlit Cloud (Settings > Secrets)
EMAIL_USER = "gestionhumanacpfert@gmail.com"
EMAIL_PASS = st.secrets.get("email_password", "bhbwshtosozexhcr") # Fallback para pruebas

# --- LEER TEMA DESDE EL URL ---
params = st.query_params
tema_raw = params.get("tema") or params.get("Tema") or "CAPACITACIÓN GENERAL"
tema_actual = tema_raw.replace("+", " ").upper()
rol_url = params.get("rol") # Detecta si viene del QR automático

# =============================================================================
# LÓGICA DE SEGURIDAD Y ROLES
# =============================================================================

# Si el URL ya trae rol=Empleado (desde el QR), lo asignamos automáticamente
if rol_url == "Empleado":
    st.session_state.rol = "Empleado"

if 'rol' not in st.session_state:
    st.markdown("<h2 style='text-align: center;'>Sistema de Gestión Humana</h2>", unsafe_allow_html=True)
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("👤 SOY EMPLEADO (Registro)", use_container_width=True):
            st.session_state.rol = "Empleado"
            st.rerun()
    with col_r2:
        if st.button("🛠️ SOY ADMINISTRADOR", use_container_width=True):
            st.session_state.rol = "Admin"
            st.rerun()
    st.stop()

# Estética: Ocultar menú lateral si es empleado para evitar distracciones
if st.session_state.rol == "Empleado":
    no_sidebar_style = """
        <style>
            [data-testid="stSidebar"] {display: none;}
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """
    st.markdown(no_sidebar_style, unsafe_allow_html=True)
    menu = "📋 Registro Asistencia"
else:
    st.sidebar.title("Navegación")
    menu = st.sidebar.radio("Ir a:", ["🛠️ Panel Administrador", "📋 Registro Asistencia"])
    if st.sidebar.button("Cerrar Sesión Admin"):
        st.session_state.rol = None
        st.rerun()

# =============================================================================
# FUNCIONES DE APOYO
# =============================================================================

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

def enviar_respaldo_gestion_humana(datos, pdf_buffer):
    mi_correo = "gestionhumanacpfert@gmail.com"
    password = "bhbwshtosozexhcr" # Recuerda usar "Contraseña de aplicación"

    msg = MIMEMultipart()
    msg['From'] = mi_correo
    msg['To'] = mi_correo # Se lo envía a sí mismo como respaldo
    msg['Subject'] = f"✅ Nueva Asistencia: {datos['Nombre']} - {datos['Tema']}"

    # Cuerpo del mensaje
    cuerpo_html = f"""
    <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="border: 1px solid #2e7d32; padding: 20px; border-radius: 10px;">
                <h2 style="color: #2e7d32;">Respaldo de Capacitación</h2>
                <p><strong>Empleado:</strong> {datos['Nombre']}</p>
                <p><strong>Cédula:</strong> {datos['ID']}</p>
                <p><strong>Tema:</strong> {datos['Tema']}</p>
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(cuerpo_html, 'html'))

    # ADJUNTO DEL PDF
    pdf_buffer.seek(0) # IMPORTANTE: Regresa al inicio del archivo
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
        print(f"Error: {e}")
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
# GENERACIÓN DE PDF (DISEÑO FINAL CORREGIDO)
# =============================================================================

def generar_pdf(datos, imagen_firma, imagen_foto):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # 1. LOGOS (Posición Y=620 para visibilidad total y ancho de 135)
    try:
        if os.path.exists("logo_campofert.png"):
            img_cf = Image.open("logo_campofert.png")
            p.drawImage(ImageReader(img_cf), 50, 620, width=135, preserveAspectRatio=True, mask='auto')
        
        if os.path.exists("logo_campolab.png"):
            img_cl = Image.open("logo_campolab.png")
            p.drawImage(ImageReader(img_cl), 430, 620, width=135, preserveAspectRatio=True, mask='auto')
    except:
        pass

    # 2. TÍTULOS (Ajustados proporcionalmente hacia abajo)
    p.setFont("Helvetica-Bold", 16)
    p.drawCentredString(width / 2, 620, "CERTIFICADO DE ASISTENCIA Y AUDITORÍA")
    p.setFont("Helvetica", 12)
    p.drawCentredString(width / 2, 600, "CAMPOFERT S.A.S / CAMPOLAB")

    # 3. INFORMACIÓN DEL PARTICIPANTE
    p.setFont("Helvetica", 11)
    y_info = 520
    p.drawString(100, y_info,      f"Participante: {datos['Nombre']}")
    p.drawString(100, y_info - 20, f"Identificación: {datos['ID']}")
    p.drawString(100, y_info - 40, f"Empresa: {datos['Empresa']}")
    p.drawString(100, y_info - 60, f"Cargo: {datos.get('Cargo', 'NO REGISTRA')}")
    
    # --- TEMA EN NEGRILLA ---
    p.setFont("Helvetica-Bold", 11)
    p.drawString(100, y_info - 80, f"Tema: {datos['Tema']}")
    
    p.setFont("Helvetica", 11) # Volver a fuente normal
    p.drawString(100, y_info - 100, f"Fecha/Hora: {datos['Fecha']}")
    p.line(100, y_info - 110, 510, y_info - 110)

    # 4. FOTO Y FIRMA (Centradas en columna)
    if imagen_foto is not None:
        img_foto = Image.open(imagen_foto)
        p.drawImage(ImageReader(img_foto), (width/2)-90, 240, width=180, height=135, preserveAspectRatio=True)

    if imagen_firma is not None:
        try:
            img_f = Image.fromarray(imagen_firma.astype('uint8'), 'RGBA')
            p.drawImage(ImageReader(img_f), (width/2)-75, 150, width=150, height=70, mask='auto')
        except:
            pass
    
    p.line((width/2)-80, 150, (width/2)+80, 150)
    p.setFont("Helvetica-Oblique", 10)
    p.drawCentredString(width/2, 135, "Firma Digital Autenticada")

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer

# =============================================================================
# INTERFAZ DE STREAMLIT (LOGO FIJO Y ALINEADO)
# =============================================================================

# CSS para asegurar que las columnas de logos se alineen por el centro verticalmente
st.markdown(
    """
    <style>
    [data-testid="stHorizontalBlock"] {
        align-items: center;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# BANNER SUPERIOR (Fuera de los pasos para que no desaparezca)
col_logo1, col_logo2, col_logo3 = st.columns([1, 1, 1])
with col_logo1:
    if os.path.exists("logo_campofert.png"):
        st.image(Image.open("logo_campofert.png"), width=160)
with col_logo3:
    if os.path.exists("logo_campolab.png"):
        st.image(Image.open("logo_campolab.png"), width=160)

st.markdown("<h1 style='text-align: center;'>Registro de Capacitación</h1>", unsafe_allow_html=True)
st.markdown("---")

# --- MENÚ LATERAL ---
st.sidebar.title("Navegación")
menu = st.sidebar.radio("Ir a:", ["📋 Registro Asistencia", "🛠️ Panel Administrador"])

# =============================================================================
# OPCIÓN 1: REGISTRO DE ASISTENCIA
# =============================================================================
if menu == "📋 Registro Asistencia":
    st.info(f"📋 **TEMA ACTUAL:** {tema_actual}")

    if 'paso' not in st.session_state:
        st.session_state.paso = 1

    df_maestro = obtener_datos()

    # PASO 1: Ingreso de Cédula o Registro Manual
    if st.session_state.paso == 1:
        cedula = st.text_input("Por favor, ingresa tu Cédula:").strip()
        if cedula:
            res = df_maestro[df_maestro['ID'].astype(str) == cedula] if df_maestro is not None else pd.DataFrame()
            
            if not res.empty:
                st.session_state.persona = res.iloc[0].to_dict()
                st.session_state.cedula = cedula
                st.success(f"Hola, {st.session_state.persona['Apellidos y Nombres']}. ¡Bienvenido!")
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
                            st.session_state.persona = {'Apellidos y Nombres': nombre_nuevo.upper(), 'Empresa': nom_emp, 'Cargo': cargo_nuevo.upper()}
                            st.session_state.cedula = cedula
                            st.session_state.paso = 2
                            st.rerun()
                        else:
                            st.error("Completa todos los campos.")

    # PASO 2: Foto
    elif st.session_state.paso == 2:
        st.subheader("📸 Captura de Identidad")
        foto = st.camera_input("Foto de validación")
        if foto:
            st.session_state.foto_data = foto
            if st.button("Ir a la firma ✍️"):
                st.session_state.paso = 3
                st.rerun()

    # PASO 3: Firma y Guardado
    elif st.session_state.paso == 3:
        st.subheader("✍️ Firma Digital")
        canvas_res = st_canvas(stroke_width=3, stroke_color="#000000", background_color="#ffffff", height=180, width=350, key="firma_final")
        
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

    # PASO 4: Descarga y Reinicio
    elif st.session_state.paso == 4:
        st.balloons()
        st.success("¡Tu asistencia ha sido registrada!")
        if st.session_state.get('pdf_doc'):
            st.download_button("📥 Descargar mi Certificado (PDF)", st.session_state.pdf_doc.getvalue(), f"Certificado_{st.session_state.cedula}.pdf", "application/pdf")
        
        if st.button("Realizar otro registro"):
            for key in ['cedula', 'persona', 'pdf_doc', 'foto_data']:
                if key in st.session_state: del st.session_state[key]
            st.session_state.paso = 1
            st.rerun()

# =============================================================================
# OPCIÓN 2: PANEL ADMINISTRADOR (CONECTADO Y FUNCIONAL)
# =============================================================================
elif menu == "🛠️ Panel Administrador":
    st.title("🛠️ Panel de Gestión Humana")
    
    # Sistema de seguridad simple
    password = st.text_input("Introduce la clave de acceso:", type="password")
    
    if password == "campofert2026": 
        # Creamos las pestañas para organizar las herramientas que mencionaste
        tab1, tab2, tab3, tab4 = st.tabs([
            "🚀 Generador QR", 
            "📊 Reportes en Vivo", 
            "👥 Gestión de Personal",
            "📜 Histórico PDF"
        ])
        
        # --- PESTAÑA 1: GENERADOR DE ENLACES Y QR ---
        with tab1:
            st.subheader("Generador de Capacitaciones")
            st.write("Escribe el tema para generar el link de acceso directo.")
            
            nombre_cap = st.text_input("Nombre del Tema (Ej: Manejo de Extintores):")
            
            if nombre_cap:
                # Generamos el link con el parámetro tema
                # Reemplaza con la URL real de tu app cuando la publiques
                base_url = "https://asistencia-campofert.streamlit.app/"
                link_final = f"{base_url}?tema={nombre_cap.replace(' ', '+')}"
                
                col_a, col_b = st.columns(2)
                with col_a:
                    st.info("Link para compartir:")
                    st.code(link_final)
                    if st.button("Copiar Link"):
                        st.write("¡Link copiado! (Usa Ctrl+C)")
                
                with col_b:
                    st.write("Código QR listo para proyectar:")    
                    qr = qrcode.make(link_final)
                    buf = BytesIO()
                    qr.save(buf, format="PNG")
                    st.image(buf.getvalue(), caption="Escanea con el celular", width=220)
                    st.caption("Los trabajadores pueden escanear esto con su celular.")

        # --- PESTAÑA 2: REPORTES EN VIVO ---
        with tab2:
            st.subheader("Monitor de Asistencias en Tiempo Real")
            try:
                # Leemos la base de datos de asistencia de Google Sheets
                df_asistencia = conn.read(worksheet="Hoja", ttl=0)
                
                # Filtros rápidos
                temas_disponibles = df_asistencia['Tema'].unique().tolist()
                filtro_tema = st.selectbox("Filtrar por Tema:", ["TODOS"] + temas_disponibles)
                
                df_mostrar = df_asistencia.copy()
                if filtro_tema != "TODOS":
                    df_mostrar = df_asistencia[df_asistencia['Tema'] == filtro_tema]
                
                st.metric("Total Registrados", len(df_mostrar))
                st.dataframe(df_mostrar, use_container_width=True)
                
                # Botón para descargar reporte en Excel
                csv = df_mostrar.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Descargar Reporte (CSV)", csv, "reporte_asistencia.csv", "text/csv")
            except:
                st.error("Aún no hay registros en la base de datos.")

        # --- PESTAÑA 3: GESTIÓN DE PERSONAL ---
        with tab3:
            st.subheader("Gestión de Base de Datos (empleados.xlsx)")
            st.write("Aquí puedes actualizar la lista de empleados autorizados.")
            
            archivo_subido = st.file_uploader("Subir nueva base de datos (Excel)", type=["xlsx"])
            
            if archivo_subido:
                with open("empleados.xlsx", "wb") as f:
                    f.write(archivo_subido.getbuffer())
                st.success("✅ Base de datos 'empleados.xlsx' actualizada correctamente.")
            
            if os.path.exists("empleados.xlsx"):
                df_temp = pd.read_excel("empleados.xlsx")
                st.write("Personal actual en el sistema:")
                st.dataframe(df_temp.head(10)) # Mostramos solo los primeros 10

        # --- PESTAÑA 4: HISTÓRICO DE CERTIFICADOS ---
        with tab4:
            st.subheader("Buscador de Certificados")
            st.write("Si un trabajador perdió su PDF, puedes buscarlo aquí por cédula.")
            
            cedula_busqueda = st.text_input("Ingrese Cédula del trabajador:")
            
            if cedula_busqueda:
                df_asistencia = conn.read(worksheet="Hoja", ttl=0)
                registros = df_asistencia[df_asistencia['ID'].astype(str) == cedula_busqueda]
                
                if not registros.empty:
                    st.write(f"Se encontraron {len(registros)} capacitaciones para esta cédula:")
                    st.table(registros[['Fecha', 'Nombre', 'Tema']])
                    st.info("Nota: Para volver a generar el PDF exacto, el trabajador debe realizar el registro nuevamente o puedes descargarlo desde el correo de respaldo que configuramos.")
                else:
                    st.warning("No se encontraron registros para esa identificación.")

    elif password != "":
        st.error("🔑 Clave incorrecta. Acceso denegado.")
