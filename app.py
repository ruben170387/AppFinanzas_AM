import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Economía Familiar", page_icon="💰", layout="centered")

# --- CONEXIÓN INFALIBLE A GOOGLE SHEETS ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # 1. Cargamos la info de los secretos
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # 2. LIMPIEZA AGRESIVA DE LA CLAVE (Para evitar el error de Padding/PEM)
        pk = creds_info["private_key"]
        if "\\n" in pk:
            pk = pk.replace("\\n", "\n")
        
        pk = pk.strip()
        creds_info["private_key"] = pk
        
        # 3. Autorización
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        
        # 4. Abrir Excel
        return client.open("App_Finanzas")
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

# Intentamos obtener la conexión
sh = conectar_excel()

if sh is None:
    st.warning("⚠️ La aplicación no pudo conectar con Google Sheets.")
    st.info("Revisa que en los Secrets de Streamlit la 'private_key' empiece por '-----BEGIN PRIVATE KEY-----' y termine correctamente.")
    st.stop()

st.title("🛡️ Mi Guardián Financiero")

# --- CARGA DE DATOS ---
try:
    ws_config = sh.worksheet("Config")
    df_ingresos = pd.DataFrame(ws_config.get_all_records())

    ws_fijos = sh.worksheet("Gastos_Fijos")
    df_fijos = pd.DataFrame(ws_fijos.get_all_records())

    ws_movimientos = sh.worksheet("Movimientos")
    df_movimientos = pd.DataFrame(ws_movimientos.get_all_records())
except Exception as e:
    st.error(f"Error al leer las pestañas del Excel: {e}")
    st.stop()

# --- BLOQUE 1: CALCULADORA Y PREDICCIÓN ---
# Extraemos sueldos y % de ahorro por su posición en la pestaña Config
sueldo_1 = pd.to_numeric(df_ingresos.iloc[0, 1], errors='coerce')
sueldo_2 = pd.to_numeric(df_ingresos.iloc[1, 1], errors='coerce')
porcentaje_ahorro = pd.to_numeric(df_ingresos.iloc[2, 1], errors='coerce')

total_ingresos = sueldo_1 + sueldo_2
total_fijos = pd.to_numeric(df_fijos['Importe'], errors='coerce').sum()

# Calculamos el objetivo de ahorro usando el porcentaje del Excel
ahorro_objetivo = total_ingresos * (porcentaje_ahorro / 100) 

if not df_movimientos.empty:
    # Aseguramos que 'Importe' sea numérico para sumar
    df_movimientos['Importe'] = pd.to_numeric(df_movimientos['Importe'], errors='coerce')
    gastos_variables_totales = df_movimientos['Importe'].sum()
else:
    gastos_variables_totales = 0

disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables_totales

hoy = datetime.now()
import calendar
_, ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)
dias_restantes = ultimo_dia_mes - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

st.subheader("Estado de tu Bolsillo")
col1, col2 = st.columns(2)
with col1:
    st.metric("Total disponible restante este mes", f"{disponible_mes:.2f} €")
with col2:
    st.metric("Tope recomendado para HOY", f"{diario_hoy:.2f} €", delta=f"Quedan {dias_restantes} días", delta_color="off")

# --- BLOQUE 2: REGISTRO DE GASTO RÁPIDO ---
st.divider()
st.header("💸 Registrar Nuevo Gasto")
with st.form("nuevo_gasto", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        concepto = st.text_input("¿Qué has comprado?")
        categoria = st.selectbox("Categoría", ["Comida", "Ocio", "Transporte", "Ropa", "Otros"])
    with c2:
        monto = st.number_input("Importe (€)", min_value=0.0, step=0.5)
        fecha_gasto = st.date_input("Fecha", value=hoy)
    
    if st.form_submit_button("Guardar en Excel"):
        if concepto and monto > 0:
            ws_movimientos.append_row([fecha_gasto.strftime("%Y-%m-%d"), concepto, categoria, monto])
            st.success("✅ Gasto anotado.")
            st.rerun()
        else:
            st.error("Por favor, rellena el concepto e importe.")

# --- BLOQUE 3: CONFIGURACIÓN ---
with st.expander("⚙️ Editar Sueldos, Ahorro y Gastos Fijos"):
    st.subheader("Sueldos y % Ahorro")
    edit_ingresos = st.data_editor(df_ingresos, use_container_width=True, key="ed_ing", hide_index=True)
    if st.button("Actualizar Sueldos y % Ahorro"):
        ws_config.update([edit_ingresos.columns.values.tolist()] + edit_ingresos.values.tolist())
        st.success("Sueldos y % de ahorro actualizados.")
        st.rerun()

    st.divider()
    
    st.subheader("Gastos Fijos")
    st.info("💡 Para añadir: escribe en la última fila vacía. Para borrar: marca la casilla gris a la izquierda de la fila y pulsa la tecla borrar/papelera.")
    # hide_index=False para que se vea la casilla de selección
    edit_fijos = st.data_editor(df_fijos, num_rows="dynamic", use_container_width=True, key="ed_fij", hide_index=False)
    if st.button("Actualizar Gastos Fijos"):
        ws_fijos.update([edit_fijos.columns.values.tolist()] + edit_fijos.values.tolist())
        st.success("Gastos fijos actualizados.")
        st.rerun()

# --- BLOQUE 4: HISTORIAL ---
if st.checkbox("Mostrar últimos 5 movimientos"):
    if not df_movimientos.empty:
        st.dataframe(df_movimientos.tail(5), use_container_width=True, hide_index=True)
    else:
        st.write("Aún no hay gastos registrados.")
