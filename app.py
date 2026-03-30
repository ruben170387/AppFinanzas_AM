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
            user = st.text_input("Usuario").strip().lower()
            pw = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if "passwords" in st.secrets and user in st.secrets["passwords"]:
                    if str(st.secrets["passwords"][user]) == pw:
                        st.session_state["autenticado"] = True
                        st.rerun()
                st.error("❌ Credenciales incorrectas")
        return False
    return True

if not check_password():
    st.stop()

# --- CONEXIÓN (CON REPARACIÓN DE LLAVE) ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # REPARACIÓN MECÁNICA:
        pk = creds_info["private_key"]
        # 1. Quitamos los \r (retorno de carro de Windows) que rompen el Padding
        pk = pk.replace('\r', '')
        # 2. Aseguramos que los \n de texto se conviertan en saltos reales
        pk = pk.replace('\\n', '\n')
        # 3. Limpiamos espacios al final de cada línea
        pk = "\n".join([line.strip() for line in pk.split("\n") if line.strip()])
        
        creds_info["private_key"] = pk
        
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("App_Finanzas")
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

sh = conectar_excel()
if sh is None: st.stop()

# --- CARGA DE DATOS ---
try:
    ws_mov = sh.worksheet("Movimientos")
    df_mov = pd.DataFrame(ws_mov.get_all_records())
    ws_ing = sh.worksheet("Config")
    df_ing = pd.DataFrame(ws_ing.get_all_records())
    ws_fij = sh.worksheet("Gastos_Fijos")
    df_fij = pd.DataFrame(ws_fij.get_all_records())
except Exception as e:
    st.error(f"Error en pestañas: {e}")
    st.stop()

def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Cálculos
ingresos = num(df_ing.iloc[:, 1]).sum()
fijos = num(df_fij['Importe']).sum()
variables = num(df_mov['Importe']).sum() if not df_mov.empty else 0
es_ah = df_ing.iloc[:, 0].astype(str).str.contains("Ahorro|%", case=False, na=False)
p_ahorro = num(pd.Series([df_ing.loc[es_ah].iloc[0, 1]]))[0] if es_ah.any() else 20.0
ahorro_obj = ingresos * (p_ahorro / 100)
disponible = ingresos - fijos - ahorro_obj - variables
hoy = datetime.now()
_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_restantes = u_dia - hoy.day + 1
diario = disponible / dias_restantes if dias_restantes > 0 else 0

# --- INTERFAZ ---
st.title("💰 Economía Familiar")
c1, c2 = st.columns(2)
c1.metric("Disponible Mes", f"{disponible:.2f} €")
c2.metric("Límite Hoy", f"{diario:.2f} €")

# Gráfico
df_graf = pd.DataFrame({"Tipo": ["Fijos", "Variables", "Ahorro", "Disponible"], 
                        "Euros": [fijos, variables, ahorro_obj, max(0, disponible)]})
st.plotly_chart(px.bar(df_graf, x="Tipo", y="Euros", color="Tipo", text_auto=".2s"), use_container_width=True)

# Registro
st.divider()
with st.form("gasto", clear_on_submit=True):
    con = st.text_input("¿En qué?")
    mon = st.number_input("Euros", min_value=0.0, step=1.0)
    if st.form_submit_button("Guardar Gasto") and con and mon > 0:
        ws_mov.append_row([hoy.strftime("%Y-%m-%d"), con, "Otros", mon])
        st.success("✅ ¡Anotado!")
        st.rerun()

if st.button("🚪 Salir"):
    st.session_state["autenticado"] = False
    st.rerun()
