import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar
import plotly.express as px
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
        
        # 2. LIMPIEZA AGRESIVA DE LA CLAVE
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

# --- FUNCIÓN ANTIMA-COMAS ---
def limpiar_numeros(serie):
    return pd.to_numeric(serie.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# --- BLOQUE 1: CALCULADORA Y PREDICCIÓN (Lógica Dinámica) ---
# 1. Buscamos automáticamente la fila del ahorro (busca "Ahorro", "%" o "Objetivo")
# Al llamarse "objetivo ahorro", este radar lo encontrará sin problemas en la fila 4.
es_ahorro = df_ingresos.iloc[:, 0].astype(str).str.contains("Ahorro|%|Objetivo", case=False, na=False)

if es_ahorro.any():
    porcentaje_ahorro = limpiar_numeros(pd.Series([df_ingresos.loc[es_ahorro].iloc[0, 1]]))[0]
else:
    porcentaje_ahorro = 20.0  # Valor por defecto si no lo encuentra

# 2. Sumamos todos los ingresos (filas que NO son la del ahorro)
total_ingresos = limpiar_numeros(df_ingresos.loc[~es_ahorro].iloc[:, 1]).sum()

# 3. Sumamos los gastos fijos
total_fijos = limpiar_numeros(df_fijos['Importe']).sum()

# Calculamos el objetivo de ahorro
ahorro_objetivo = total_ingresos * (porcentaje_ahorro / 100) 

# 4. Calculamos los gastos variables
if not df_movimientos.empty:
    df_movimientos['Importe'] = limpiar_numeros(df_movimientos['Importe'])
    gastos_variables_totales = df_movimientos['Importe'].sum()
else:
    gastos_variables_totales = 0

disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables_totales

hoy = datetime.now()
_, ultimo_dia_mes = calendar.monthrange(hoy.year, hoy.month)
dias_restantes = ultimo_dia_mes - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

st.subheader("Estado de tu Bolsillo")
col1, col2 = st.columns(2)
with col1:
    st.metric("Total disponible restante", f"{disponible_mes:.2f} €")
with col2:
    st.metric("Tope para HOY", f"{diario_hoy:.2f} €", delta=f"Quedan {dias_restantes} días", delta_color="off")

# --- BLOQUE DE GRÁFICA OPTIMIZADA PARA MÓVIL ---
st.markdown("### 📊 Reparto de Ingresos vs Gastos")

datos_barras = pd.DataFrame({
    "Grupo": ["1. Ingresos", "2. Distribución", "2. Distribución", "2. Distribución", "2. Distribución"],
    "Concepto": ["Ingresos Totales", "Gastos Fijos", "Gastos Variables", "Ahorro Objetivo", "Disponible (Quemable)"],
    "Cantidad": [total_ingresos, total_fijos, gastos_variables_totales, ahorro_objetivo, max(0, disponible_mes)]
})

# Creamos la gráfica
fig = px.bar(
    datos_barras, 
    x="Grupo", 
    y="Cantidad", 
    color="Concepto",
    text="Cantidad",
    color_discrete_map={
        "Ingresos Totales": "#2ECC71",             
        "Gastos Fijos": "#E74C3C",                 
        "Gastos Variables": "#F39C12",             
        "Ahorro Objetivo": "#3498DB",             
        "Disponible (Quemable)": "#1ABC9C" 
    }
)

# --- AJUSTES ESPECÍFICOS PARA MÓVIL (Mover leyenda abajo y ampliar márgenes) ---
fig.update_traces(texttemplate='%{text:.1f} €', textposition='inside')

fig.update_layout(
    xaxis_title="", 
    yaxis_title="Euros (€)",
    # 1. MOVER LEYENDA ABAJO (Configuración horizontal centrada)
    legend=dict(
        orientation="h",       # Horizontal
        yanchor="bottom",      # Ancla en la parte inferior
        y=-0.2,                # Posición por debajo del eje X
        xanchor="center",      # Centrada horizontalmente
        x=0.5,
        title=""               # Quitamos el título de la leyenda para ahorrar espacio
    ),
    # 2. OPTIMIZAR MÁRGENES (Reducimos espacios vacíos alrededor)
    margin=dict(t=10, b=10, l=10, r=10),
    # Fijamos una altura mínima para que no se vea aplastada
    height=450,
    # Hacemos que los textos de las barras sean legibles
    uniformtext=dict(mode="hide", minsize=10)
)

# Mostramos la gráfica forzando que ocupe todo el ancho disponible
st.plotly_chart(fig, use_container_width=True)


# --- BLOQUE 2: REGISTRO DE GASTO RÁPIDO ---
st.divider()
st.header("💸 Registrar Nuevo Gasto")
with st.form("nuevo_gasto", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        concepto = st.text_input("¿En qué has gastado?")
        categoria = st.selectbox("Categoría", ["Comida", "Ocio", "Transporte", "Ropa", "Otros"])
    with c2:
        monto = st.number_input("Importe (€)", min_value=0.0, step=0.5, format="%.2f")
        fecha_gasto = st.date_input("Fecha", value=hoy)
    
    if st.form_submit_button("Guardar Gasto"):
        if concepto and monto > 0:
            ws_movimientos.append_row([fecha_gasto.strftime("%Y-%m-%d"), concepto, categoria, monto])
            st.success("✅ Gasto anotado.")
            st.rerun()
        else:
            st.error("Rellena concepto e importe.")

# --- BLOQUE 3: CONFIGURACIÓN ---
with st.expander("⚙️ Editar Sueldos, Ahorro y Gastos Fijos"):
    st.subheader("Sueldos y % Ahorro")
    st.info("💡 Tu Excel busca las palabras 'Objetivo', 'Ahorro' o '%' para encontrar el porcentaje.")
    edit_ingresos = st.data_editor(df_ingresos, use_container_width=True, key="ed_ing", hide_index=True)
    if st.button("Actualizar Sueldos y % Ahorro"):
        ws_config.update([edit_ingresos.columns.values.tolist()] + edit_ingresos.values.tolist())
        st.success("Configuración actualizada.")
        st.rerun()

    st.divider()
    
    st.subheader("Gastos Fijos")
    st.info("💡 Para añadir: escribe en la última fila vacía. Para borrar: marca la casilla gris a la izquierda y pulsa borrar.")
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
