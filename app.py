import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Economía Familiar", page_icon="💰", layout="centered")

# --- CONEXIÓN INFALIBLE A GOOGLE SHEETS (CORREGIDA) ---
@st.cache_resource
def conectar_excel():
    try:
        # 1. Definimos los permisos
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # 2. Extraemos los secretos y creamos una copia para no modificar el original de Streamlit
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # 3. CORRECCIÓN CLAVE: Transformamos los \n de texto en saltos de línea reales
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        # 4. Creamos las credenciales con la info corregida
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        
        # 5. Abre el Excel por su nombre exacto
        return client.open("App_Finanzas")
    except Exception as e:
        st.error(f"❌ Error crítico en la función de conexión: {e}")
        return None

# Intentamos obtener la conexión
sh = conectar_excel()

if sh is None:
    st.info("Revisa que el formato en el secrets.toml sea el correcto y que la clave privada no tenga espacios extra.")
    st.stop()

# --- A PARTIR DE AQUÍ EL RESTO DE TU CÓDIGO ---

st.title("🛡️ Mi Guardián Financiero")

# --- CARGA DE DATOS ---
# Usamos bloques try/except para las pestañas por si el Excel cambió de nombre
try:
    ws_config = sh.worksheet("Config")
    df_ingresos = pd.DataFrame(ws_config.get_all_records())

    ws_fijos = sh.worksheet("Gastos_Fijos")
    df_fijos = pd.DataFrame(ws_fijos.get_all_records())

    ws_movimientos = sh.worksheet("Movimientos")
    df_movimientos = pd.DataFrame(ws_movimientos.get_all_records())
except Exception as e:
    st.error(f"Error al leer las pestañas: {e}")
    st.stop()

# --- BLOQUE 1: CALCULADORA Y PREDICCIÓN ---
# (Tu lógica de cálculo se mantiene igual...)
total_ingresos = pd.to_numeric(df_ingresos.iloc[:, 1], errors='coerce').sum()
total_fijos = pd.to_numeric(df_fijos['Importe'], errors='coerce').sum()
ahorro_objetivo = total_ingresos * 0.20 

if not df_movimientos.empty:
    gastos_variables_totales = pd.to_numeric(df_movimientos['Importe'], errors='coerce').sum()
else:
    gastos_variables_totales = 0

disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables_totales

hoy = datetime.now()
ultimo_dia_mes = 31 if hoy.month in [1, 3, 5, 7, 8, 10, 12] else 30
if hoy.month == 2: ultimo_dia_mes = 28
dias_restantes = ultimo_dia_mes - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

st.subheader("Estado de tu Bolsillo")
col1, col2 = st.columns(2)
with col1:
    st.metric("Disponible este mes", f"{disponible_mes:.2f} €")
with col2:
    color_delta = "normal" if diario_hoy > 15 else "inverse"
    st.metric("Presupuesto diario", f"{diario_hoy:.2f} €", delta=f"{diario_hoy-20:.1f} € vs meta", delta_color=color_delta)

# --- BLOQUE 2: REGISTRO DE GASTO RÁPIDO ---
st.divider()
st.header("💸 Registrar Nuevo Gasto")
with st.form("nuevo_gasto", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        concepto = st.text_input("¿En qué has gastado?")
        categoria = st.selectbox("Categoría", ["Comida", "Ocio", "Transporte", "Ropa", "Otros"])
    with c2:
        monto = st.number_input("Importe (€)", min_value=0.0, step=0.5)
        fecha_gasto = st.date_input("Fecha", value=hoy)
    
    if st.form_submit_button("Guardar en Excel"):
        ws_movimientos.append_row([fecha_gasto.strftime("%Y-%m-%d"), concepto, categoria, monto])
        st.success("✅ Gasto anotado. ¡Recalculando!")
        st.rerun()

# --- BLOQUE 3: CONFIGURACIÓN ---
with st.expander("⚙️ Editar Sueldos y Gastos Fijos"):
    st.write("Modifica los valores abajo y dale a guardar.")
    
    edit_ingresos = st.data_editor(df_ingresos, use_container_width=True, key="editor_ingresos")
    if st.button("Guardar Cambios en Sueldos"):
        # Convertimos DataFrame a lista de listas incluyendo cabeceras
        datos_actualizar = [edit_ingresos.columns.values.tolist()] + edit_ingresos.values.tolist()
        ws_config.update(datos_actualizar)
        st.success("Sueldos actualizados.")
        st.rerun()

    st.divider()
    
    edit_fijos = st.data_editor(df_fijos, num_rows="dynamic", use_container_width=True, key="editor_fijos")
    if st.button("Guardar Cambios en Gastos Fijos"):
        datos_fijos_actualizar = [edit_fijos.columns.values.tolist()] + edit_fijos.values.tolist()
        ws_fijos.update(datos_fijos_actualizar)
        st.success("Gastos fijos actualizados.")
        st.rerun()

# --- BLOQUE 4: HISTORIAL ---
if st.checkbox("Mostrar últimos 5 movimientos"):
    if not df_movimientos.empty:
        st.table(df_movimientos.tail(5))
    else:
        st.write("Aún no hay gastos registrados.")
