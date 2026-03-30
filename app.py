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
                    if usuario_input in st.secrets["passwords"] and str(st.secrets["passwords"][usuario_input]) == clave_input:
                        st.session_state["autenticado"] = True
                        st.rerun()
                    else:
                        time.sleep(1)
                        st.error("❌ Usuario o contraseña incorrectos")
        return False
    return True

if not check_password():
    st.stop()

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # Cargamos la sección correspondiente de los Secrets
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # IMPORTANTE: Convertimos los "\n" de texto en saltos de línea reales
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
    st.stop()

# --- CARGA DE DATOS ---
try:
    ws_config = sh.worksheet("Config")
    df_ingresos = pd.DataFrame(ws_config.get_all_records())
    ws_fijos = sh.worksheet("Gastos_Fijos")
    df_fijos = pd.DataFrame(ws_fijos.get_all_records())
    ws_movimientos = sh.worksheet("Movimientos")
    df_movimientos = pd.DataFrame(ws_movimientos.get_all_records())
except Exception as e:
    st.error(f"Error al leer el Excel: {e}")
    st.stop()

def limpiar_numeros(serie):
    return pd.to_numeric(serie.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# --- LÓGICA DE CÁLCULOS ---
es_ahorro = df_ingresos.iloc[:, 0].astype(str).str.contains("Ahorro|%|Objetivo", case=False, na=False)
porcentaje_ahorro = limpiar_numeros(pd.Series([df_ingresos.loc[es_ahorro].iloc[0, 1]]))[0] if es_ahorro.any() else 20.0

total_ingresos = limpiar_numeros(df_ingresos.loc[~es_ahorro].iloc[:, 1]).sum()
total_fijos = limpiar_numeros(df_fijos['Importe']).sum()
ahorro_objetivo = total_ingresos * (porcentaje_ahorro / 100)
gastos_variables = limpiar_numeros(df_movimientos['Importe']).sum() if not df_movimientos.empty else 0

disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables

hoy = datetime.now()
_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_restantes = u_dia - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

# --- INTERFAZ DE USUARIO ---
st.title("🛡️ Mi Guardián Financiero")

c1, c2 = st.columns(2)
c1.metric("Disponible Mes", f"{disponible_mes:.2f} €")
c2.metric("Tope para HOY", f"{diario_hoy:.2f} €", delta=f"{dias_restantes} días rest.")

# Gráfico
st.markdown("### 📊 Estado de Gastos")
df_graf = pd.DataFrame({
    "Tipo": ["Fijos", "Variables", "Ahorro", "Disponible"],
    "Euros": [total_fijos, gastos_variables, ahorro_objetivo, max(0, disponible_mes)]
})
st.plotly_chart(px.bar(df_graf, x="Tipo", y="Euros", color="Tipo", text_auto=".2s"), use_container_width=True)

# Registro rápido
st.divider()
with st.form("nuevo_gasto", clear_on_submit=True):
    con = st.text_input("Concepto")
    mon = st.number_input("Importe (€)", min_value=0.0, step=1.0)
    if st.form_submit_button("Guardar Gasto") and con and mon > 0:
        ws_movimientos.append_row([hoy.strftime("%Y-%m-%d"), con, "Otros", mon])
        st.success("✅ ¡Anotado!")
        st.rerun()

if st.button("🚪 Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()
