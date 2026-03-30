import streamlit as st
from gspread_pandas import Spread
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Economía Familiar", page_icon="💰")

# Función para conectar con Google Sheets
@st.cache_resource
def conectar_excel():
    # Asegúrate de que tus "Secrets" en Streamlit coincidan con este nombre
    return Spread('App_Finanzas', config=st.secrets["gcp_service_account"])

try:
    spread = conectar_excel()
except Exception as e:
    st.error("Error de conexión. Revisa los 'Secrets' y el permiso del Excel.")
    st.stop()

st.title("🛡️ Mi Guardián Financiero")

# --- BLOQUE 1: CALCULADORA DE DISPONIBILIDAD (EL "SEMÁFORO") ---
df_ingresos = spread.sheet_to_df(sheet='Config')
df_fijos = spread.sheet_to_df(sheet='Gastos_Fijos')
df_movimientos = spread.sheet_to_df(sheet='Movimientos')

# Cálculos base
total_ingresos = pd.to_numeric(df_ingresos.iloc[:, 1]).sum()
total_fijos = pd.to_numeric(df_fijos['Importe']).sum()
ahorro_objetivo = total_ingresos * 0.20 # 20% ahorro

# Suma de gastos variables ya realizados este mes
# (Asumimos que solo anotas los del mes actual)
gastos_variables_totales = pd.to_numeric(df_movimientos['Importe']).sum()

disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables_totales

# Predicción diaria
hoy = datetime.now()
dias_mes = 31 # Simplificado
dias_restantes = dias_mes - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

# Visualización principal
st.subheader("Estado Actual")
col1, col2 = st.columns(2)
with col1:
    st.metric("Disponible para el mes", f"{disponible_mes:.2f} €")
with col2:
    color = "normal" if diario_hoy > 15 else "inverse"
    st.metric("Puedes gastar HOY", f"{diario_hoy:.2f} €", delta_color=color)

# --- BLOQUE 2: REGISTRO DE GASTO RÁPIDO ---
st.divider()
st.header("💸 Registrar Gasto")
with st.form("nuevo_gasto", clear_on_submit=True):
    col_a, col_b = st.columns(2)
    with col_a:
        concepto = st.text_input("¿Qué has comprado?")
        categoria = st.selectbox("Categoría", ["Comida", "Ocio", "Transporte", "Ropa", "Otros"])
    with col_b:
        monto = st.number_input("Importe (€)", min_value=0.0, step=0.1)
        fecha = st.date_input("Fecha", value=hoy)
    
    if st.form_submit_button("Guardar Gasto"):
        nuevo_dato = pd.DataFrame([[fecha.strftime("%Y-%m-%d"), concepto, categoria, monto]], 
                                 columns=['Fecha', 'Concepto', 'Categoría', 'Importe'])
        # Añadimos al final de la hoja Movimientos
        spread.df_to_sheet(nuevo_dato, sheet='Movimientos', index=False, append=True)
        st.success("¡Gasto registrado! Actualizando cálculos...")
        st.rerun()

# --- BLOQUE 3: GESTIÓN DE INGRESOS Y FIJOS ---
with st.expander("⚙️ Configuración de Ingresos y Gastos Fijos"):
    st.subheader("Editar Ingresos")
    # Editor para los sueldos
    nuevo_df_ingresos = st.data_editor(df_ingresos)
    if st.button("Actualizar Sueldos"):
        spread.df_to_sheet(nuevo_df_ingresos, sheet='Config', index=False)
        st.success("Ingresos actualizados.")

    st.subheader("Editar Gastos Fijos")
    # Editor para alquiler, luz, etc.
    nuevo_df_fijos = st.data_editor(df_fijos, num_rows="dynamic")
    if st.button("Actualizar Gastos Fijos"):
        spread.df_to_sheet(nuevo_df_fijos, sheet='Gastos_Fijos', index=False)
        st.success("Gastos fijos actualizados.")

# --- BLOQUE 4: HISTORIAL ---
if st.checkbox("Ver últimos movimientos"):
    st.table(df_movimientos.tail(10))
