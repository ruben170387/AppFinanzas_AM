import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar
import plotly.express as px
import time

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Economía Familiar", page_icon="💰", layout="centered")

# --- SISTEMA DE LOGIN ---
def check_password():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        st.title("🔒 Acceso Restringido")
        with st.form("login_form"):
            usuario_input = st.text_input("Usuario").strip().lower()
            clave_input = st.text_input("Contraseña", type="password")
            submit = st.form_submit_button("Entrar")
            if submit:
                if "passwords" in st.secrets:
                    # Comprobación de seguridad para usuarios y claves
                    if usuario_input in st.secrets["passwords"] and str(st.secrets["passwords"][usuario_input]) == clave_input:
                        st.session_state["autenticado"] = True
                        st.rerun()
                    else:
                        time.sleep(1)
                        st.error("❌ Usuario o contraseña incorrectos")
                else:
                    st.error("⚠️ No se encuentran los usuarios configurados en Secrets.")
        return False
    return True

if not check_password():
    st.stop()

# --- CONEXIÓN A GOOGLE SHEETS (VERSIÓN SIMPLIFICADA) ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # Cargamos el diccionario completo de los secretos
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # LIMPIEZA QUIRÚRGICA: Solo cambiamos los \n de texto por saltos reales
        # Esto soluciona el error InvalidLength(1625)
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")
        
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("App_Finanzas")
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

sh = conectar_excel()

if sh is None:
    st.warning("⚠️ La aplicación no pudo conectar con el Excel. Revisa los Secrets.")
    st.stop()

# ==========================================
# APP PRINCIPAL (DATOS Y VISUALIZACIÓN)
# ==========================================

try:
    ws_config = sh.worksheet("Config")
    df_ingresos = pd.DataFrame(ws_config.get_all_records())
    
    ws_fijos = sh.worksheet("Gastos_Fijos")
    df_fijos = pd.DataFrame(ws_fijos.get_all_records())
    
    ws_movimientos = sh.worksheet("Movimientos")
    df_movimientos = pd.DataFrame(ws_movimientos.get_all_records())
except Exception as e:
    st.error(f"❌ Error al leer las pestañas del Excel: {e}")
    st.stop()

def limpiar_numeros(serie):
    return pd.to_numeric(serie.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# --- CÁLCULOS ---
# Buscamos el porcentaje de ahorro
es_ahorro = df_ingresos.iloc[:, 0].astype(str).str.contains("Ahorro|%|Objetivo", case=False, na=False)
porcentaje_ahorro = limpiar_numeros(pd.Series([df_ingresos.loc[es_ahorro].iloc[0, 1]]))[0] if es_ahorro.any() else 20.0

total_ingresos = limpiar_numeros(df_ingresos.loc[~es_ahorro].iloc[:, 1]).sum()
total_fijos = limpiar_numeros(df_fijos['Importe']).sum()
ahorro_objetivo = total_ingresos * (porcentaje_ahorro / 100)

if not df_movimientos.empty:
    gastos_variables_totales = limpiar_numeros(df_movimientos['Importe']).sum()
else:
    gastos_variables_totales = 0

disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables_totales

# Cálculo diario
hoy = datetime.now()
_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_restantes = u_dia - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

# --- INTERFAZ ---
st.title("🛡️ Mi Guardián Financiero")

col1, col2 = st.columns(2)
col1.metric("Disponible Mes", f"{disponible_mes:.2f} €")
col2.metric("Tope para HOY", f"{diario_hoy:.2f} €", delta=f"{dias_restantes} días rest.")

# --- GRÁFICO ---
st.markdown("### 📊 Distribución del Presupuesto")
datos_barras = pd.DataFrame({
    "Concepto": ["Gastos Fijos", "Gastos Variables", "Ahorro", "Disponible"],
    "Euros": [total_fijos, gastos_variables_totales, ahorro_objetivo, max(0, disponible_mes)]
})
fig = px.bar(datos_barras, x="Concepto", y="Euros", color="Concepto", text="Euros")
fig.update_traces(texttemplate='%{text:.2f} €', textposition='inside')
st.plotly_chart(fig, use_container_width=True)

# --- FORMULARIO DE GASTO ---
st.divider()
st.subheader("💸 Registrar Gasto")
with st.form("nuevo_gasto", clear_on_submit=True):
    c_con, c_cat, c_mon = st.columns([2, 2, 1])
    with c_con:
        con = st.text_input("¿En qué?")
    with c_cat:
        cat = st.selectbox("Categoría", ["Comida", "Ocio", "Transporte", "Ropa", "Salud", "Otros"])
    with c_mon:
        mon = st.number_input("Importe", min_value=0.0, step=0.5)
    
    if st.form_submit_button("Guardar Gasto"):
        if con and mon > 0:
            ws_movimientos.append_row([hoy.strftime("%Y-%m-%d"), con, cat, mon])
            st.success("✅ Gasto registrado")
            st.rerun()

# --- CONFIGURACIÓN ---
with st.expander("⚙️ Opciones"):
    if st.button("🚪 Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.rerun()
