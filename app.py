import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar
import plotly.express as px
import re

# --- CONFIGURACIÓN DE PÁGINA (DEBE SER EL PRIMER COMANDO) ---
st.set_page_config(page_title="Economía Familiar", page_icon="💰", layout="centered")

# --- SISTEMA DE LOGIN ---
def check_password():
    """Devuelve True si el usuario tiene la contraseña correcta."""
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.title("🔒 Acceso Restringido")
        st.write("Por favor, identifícate para ver las finanzas.")
        
        with st.form("login_form"):
            usuario = st.text_input("Usuario")
            clave = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Entrar")

            if submit:
                # Comprueba si el bloque [passwords] existe en secrets
                if "passwords" in st.secrets:
                    # Comprueba si el usuario existe y la clave es correcta
                    if usuario in st.secrets["passwords"] and st.secrets["passwords"][usuario] == clave:
                        st.session_state["autenticado"] = True
                        st.rerun()
                    else:
                        st.error("❌ Usuario o contraseña incorrectos")
                else:
                    st.error("⚠️ Faltan las contraseñas en los Secrets de Streamlit.")
        return False
    return True

# Si no está autenticado, detenemos la ejecución aquí mismo.
if not check_password():
    st.stop()

# ==========================================
# A PARTIR DE AQUÍ, LA APP SOLO CARGA SI HAY LOGIN CORRECTO
# ==========================================

# --- CONEXIÓN INFALIBLE A GOOGLE SHEETS ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_info = dict(st.secrets["gcp_service_account"])
        
        pk = creds_info["private_key"]
        if "\\n" in pk:
            pk = pk.replace("\\n", "\n")
        
        pk = pk.strip()
        creds_info["private_key"] = pk
        
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        
        return client.open("App_Finanzas")
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

sh = conectar_excel()

if sh is None:
    st.warning("⚠️ La aplicación no pudo conectar con Google Sheets.")
    st.stop()

# Botón para cerrar sesión
col_titulo, col_salir = st.columns([0.8, 0.2])
with col_titulo:
    st.title("🛡️ Mi Guardián Financiero")
with col_salir:
    if st.button("🚪 Salir"):
        st.session_state["autenticado"] = False
        st.rerun()

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
es_ahorro = df_ingresos.iloc[:, 0].astype(str).str.contains("Ahorro|%|Objetivo", case=False, na=False)

if es_ahorro.any():
    porcentaje_ahorro = limpiar_numeros(pd.Series([df_ingresos.loc[es_ahorro].iloc[0, 1]]))[0]
else:
    porcentaje_ahorro = 20.0  

total_ingresos = limpiar_numeros(df_ingresos.loc[~es_ahorro].iloc[:, 1]).sum()
total_fijos = limpiar_numeros(df_fijos['Importe']).sum()
ahorro_objetivo = total_ingresos * (porcentaje_ahorro / 100) 

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

fig.update_traces(texttemplate='%{text:.1f} €', textposition='inside')

fig.update_layout(
    xaxis_title="", 
    yaxis_title="Euros (€)",
    legend=dict(
        orientation="h",       
        yanchor="bottom",      
        y=-0.2,                
        xanchor="center",      
        x=0.5,
        title=""               
    ),
    margin=dict(t=10, b=10, l=10, r=10),
    height=450,
    uniformtext=dict(mode="hide", minsize=10)
)

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

# --- BLOQUE 3: CONFIGURACIÓN (VERSIÓN MÓVIL 100% SEGURA) ---
with st.expander("⚙️ Editar Sueldos, Ahorro y Gastos Fijos"):
    
    st.markdown("### 1️⃣ Sueldos y % Ahorro")
    sueldo_1_actual = limpiar_numeros(pd.Series([df_ingresos.iloc[0, 1]]))[0] if len(df_ingresos) > 0 else 0.0
    sueldo_2_actual = limpiar_numeros(pd.Series([df_ingresos.iloc[1, 1]]))[0] if len(df_ingresos) > 1 else 0.0
    
    with st.form("form_ingresos_ahorro"):
        nuevo_s1 = st.number_input("Sueldo 1 (€)", value=float(sueldo_1_actual), step=50.0, format="%.2f")
        nuevo_s2 = st.number_input("Sueldo 2 (€)", value=float(sueldo_2_actual), step=50.0, format="%.2f")
        nuevo_ahorro = st.number_input("Objetivo Ahorro (%)", value=float(porcentaje_ahorro), step=1.0, format="%.2f")
        
        if st.form_submit_button("💾 Guardar Sueldos y Ahorro"):
            nuevos_datos_config = [
                [df_ingresos.columns[0], df_ingresos.columns[1]], 
                [df_ingresos.iloc[0, 0] if len(df_ingresos) > 0 else "Sueldo 1", nuevo_s1],
                [df_ingresos.iloc[1, 0] if len(df_ingresos) > 1 else "Sueldo 2", nuevo_s2],
                ["Objetivo Ahorro", nuevo_ahorro]
            ]
            ws_config.clear() 
            ws_config.update(nuevos_datos_config) 
            st.success("✅ Sueldos y ahorro actualizados correctamente.")
            st.rerun()

    st.divider()

    st.markdown("### 2️⃣ Gestión de Gastos Fijos")
    if not df_fijos.empty:
        st.dataframe(df_fijos, use_container_width=True, hide_index=True)
    else:
        st.info("No tienes gastos fijos registrados.")

    col_add, col_del = st.columns(2)
    
    with col_add:
        st.markdown("**Añadir Nuevo**")
        with st.form("form_add_fijo", clear_on_submit=True):
            nuevo_concepto_fijo = st.text_input("Nombre (Ej. Luz)")
            nuevo_importe_fijo = st.number_input("Importe (€)", min_value=0.0, step=1.0, format="%.2f")
            if st.form_submit_button("➕ Añadir"):
                if nuevo_concepto_fijo and nuevo_importe_fijo > 0:
                    ws_fijos.append_row([nuevo_concepto_fijo, nuevo_importe_fijo])
                    st.success("✅ Añadido.")
                    st.rerun()
                else:
                    st.error("Faltan datos.")

    with col_del:
        st.markdown("**Borrar Existente**")
        if not df_fijos.empty:
            with st.form("form_del_fijo"):
                gasto_a_borrar = st.selectbox("Selecciona Gasto", df_fijos.iloc[:, 0].tolist())
                if st.form_submit_button("🗑️ Borrar"):
                    df_fijos_limpio = df_fijos[df_fijos.iloc[:, 0] != gasto_a_borrar]
                    ws_fijos.clear() 
                    
                    if df_fijos_limpio.empty:
                        ws_fijos.update([df_fijos.columns.values.tolist()]) 
                    else:
                        ws_fijos.update([df_fijos_limpio.columns.values.tolist()] + df_fijos_limpio.values.tolist())
                    
                    st.success("✅ Borrado.")
                    st.rerun()
        else:
            st.write("Nada que borrar.")

# --- BLOQUE 4: HISTORIAL ---
if st.checkbox("Mostrar últimos 5 movimientos"):
    if not df_movimientos.empty:
        st.dataframe(df_movimientos.tail(5), use_container_width=True, hide_index=True)
    else:
        st.write("Aún no hay gastos registrados.")
