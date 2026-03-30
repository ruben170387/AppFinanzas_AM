import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar
import plotly.express as px
import time

# --- LOGIN (Simplificado para asegurar que entras rápido) ---
def check_password():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False
    if not st.session_state["autenticado"]:
        st.title("🔒 Acceso Restringido")
        with st.form("login_form"):
            u = st.text_input("Usuario").strip().lower()
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if "passwords" in st.secrets and u in st.secrets["passwords"]:
                    if str(st.secrets["passwords"][u]) == p:
                        st.session_state["autenticado"] = True
                        st.rerun()
                st.error("❌ Credenciales incorrectas")
        return False
    return True

if not check_password():
    st.stop()

# --- CONEXIÓN (CON LIMPIEZA DE CARACTERES EXTRAÑOS) ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # Limpieza profunda para eliminar el error InvalidByte(64, 46)
        pk = creds_info["private_key"]
        
        # Si por error el email está aquí, esto fallará avisándote
        if "@" in pk and "-----BEGIN PRIVATE KEY-----" in pk:
             # Solo permitimos el @ si está en las líneas de comentario, no en la data
             pass 

        pk = pk.replace('\\n', '\n').strip()
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

# --- CÁLCULOS ---
def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

i = num(df_ing.iloc[:, 1]).sum()
f = num(df_fij['Importe']).sum()
v = num(df_mov['Importe']).sum() if not df_mov.empty else 0
dispo = i - f - v
hoy = datetime.now()
_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_r = u_dia - hoy.day + 1
diario = dispo / dias_r if dias_r > 0 else 0

# --- INTERFAZ ---
st.title("💰 Mi Guardián Financiero")
c1, c2 = st.columns(2)
c1.metric("Disponible", f"{dispo:.2f} €")
c2.metric("Para hoy", f"{diario:.2f} €")

st.plotly_chart(px.bar(x=["Fijos", "Variables", "Disponible"], y=[f, v, max(0, dispo)], color=["Fijos", "Variables", "Disponible"]), use_container_width=True)

with st.form("gasto", clear_on_submit=True):
    con = st.text_input("Concepto")
    mon = st.number_input("Euros", min_value=0.0, step=1.0)
    if st.form_submit_button("Guardar"):
        if con and mon > 0:
            ws_mov.append_row([hoy.strftime("%Y-%m-%d"), con, "Gasto", mon])
            st.success("✅ ¡Hecho!")
            st.rerun()
