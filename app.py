import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Economía Familiar", page_icon="💰", layout="centered")

# --- CONEXIÓN INFALIBLE A GOOGLE SHEETS ---
@st.cache_resource
def conectar_excel():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    # Accedemos directamente a los secretos de Streamlit
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    # Abre el Excel por su nombre exacto
    return client.open("App_Finanzas")

try:
    sh = conectar_excel()
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.info("Asegúrate de haber compartido el Excel con el email del 'client_email' que está en tu JSON.")
    st.stop()

st.title("🛡️ Mi Guardián Financiero")

# --- CARGA DE DATOS ---
# Leemos las pestañas y las convertimos en DataFrames de Pandas
ws_config = sh.worksheet("Config")
df_ingresos = pd.DataFrame(ws_config.get_all_records())

ws_fijos = sh.worksheet("Gastos_Fijos")
df_fijos = pd.DataFrame(ws_fijos.get_all_records())

ws_movimientos = sh.worksheet("Movimientos")
df_movimientos = pd.DataFrame(ws_movimientos.get_all_records())

# --- BLOQUE 1: CALCULADORA Y PREDICCIÓN ---
# Convertimos a número por si acaso hay textos en el Excel
total_ingresos = pd.to_numeric(df_ingresos.iloc[:, 1]).sum()
total_fijos = pd.to_numeric(df_fijos['Importe']).sum()
ahorro_objetivo = total_ingresos * 0.20 

# Suma de gastos variables del mes
if not df_movimientos.empty:
    gastos_variables_totales = pd.to_numeric(df_movimientos['Importe']).sum()
else:
    gastos_variables_totales = 0

disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables_totales

# Lógica de días restantes
hoy = datetime.now()
# Calculamos días restantes reales del mes actual
ultimo_dia_mes = 31 if hoy.month in [1, 3, 5, 7, 8, 10, 12] else 30
if hoy.month == 2: ultimo_dia_mes = 28
dias_restantes = ultimo_dia_mes - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

# Visualización principal
st.subheader("Estado de tu Bolsillo")
col1, col2 = st.columns(2)
with col1:
    st.metric("Disponible este mes", f"{disponible_mes:.2f} €")
with col2:
    # Si puedes gastar más de 15€ al día sale en verde, si no en rojo
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
        # Añadimos fila al final de la pestaña Movimientos
        ws_movimientos.append_row([fecha_gasto.strftime("%Y-%m-%d"), concepto, categoria, monto])
        st.success("✅ Gasto anotado. ¡Recalculando!")
        st.rerun()

# --- BLOQUE 3: CONFIGURACIÓN ---
with st.expander("⚙️ Editar Sueldos y Gastos Fijos"):
    st.write("Modifica los valores abajo y dale a guardar.")
    
    # Editor para Ingresos
    edit_ingresos = st.data_editor(df_ingresos, use_container_width=True)
    if st.button("Guardar Cambios en Sueldos"):
        # Sobreescribimos la hoja entera con los nuevos datos
        ws_config.update([edit_ingresos.columns.values.tolist()] + edit_ingresos.values.tolist())
        st.success("Sueldos actualizados.")

    st.divider()
    
    # Editor para Gastos Fijos
    edit_fijos = st.data_editor(df_fijos, num_rows="dynamic", use_container_width=True)
    if st.button("Guardar Cambios en Gastos Fijos"):
        ws_fijos.update([edit_fijos.columns.values.tolist()] + edit_fijos.values.tolist())
        st.success("Gastos fijos actualizados.")

# --- BLOQUE 4: HISTORIAL ---
if st.checkbox("Mostrar últimos 5 movimientos"):
    if not df_movimientos.empty:
        st.table(df_movimientos.tail(5))
    else:
        st.write("Aún no hay gastos registrados.")
