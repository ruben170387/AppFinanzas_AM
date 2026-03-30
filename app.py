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
            u = st.text_input("Usuario").strip().lower()
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if "passwords" in st.secrets and u in st.secrets["passwords"]:
                    # Comprobamos la contraseña (asegurando que sea string)
                    if str(st.secrets["passwords"][u]) == p:
                        st.session_state["autenticado"] = True
                        st.rerun()
                st.error("❌ Credenciales incorrectas")
        return False
    return True

if not check_password():
    st.stop()

# --- CONEXIÓN MAESTRA (OPTIMIZADA PARA LÍNEA ÚNICA) ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        
        # Cargamos el diccionario de secretos
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # Limpieza de la clave privada
        pk = creds_info["private_key"]
        
        # 1. Convertimos los \n de texto en saltos de línea reales
        pk = pk.replace("\\n", "\n")
        
        # 2. Eliminamos comillas accidentales y espacios en los extremos
        pk = pk.strip().strip('"').strip("'")
        
        creds_info["private_key"] = pk
        
        # Autorización con Google
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("App_Finanzas")
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        return None

sh = conectar_excel()

# Si la conexión falla, detenemos la ejecución para evitar errores en cascada
if sh is None:
    st.warning("⚠️ Revisa los Secrets en Streamlit Cloud y asegúrate de haber hecho un 'Reboot app'.")
    st.stop()

# --- CARGA DE DATOS ---
try:
    ws_mov = sh.worksheet("Movimientos")
    df_mov = pd.DataFrame(ws_mov.get_all_records())
    ws_ing = sh.worksheet("Config")
    df_ing = pd.DataFrame(ws_ing.get_all_records())
    ws_fij = sh.worksheet("Gastos_Fijos")
    df_fij = pd.DataFrame(ws_fij.get_all_records())
except Exception as e:
    st.error(f"❌ Error al leer las pestañas del Excel: {e}")
    st.stop()

# Función para limpiar y convertir números
def num(s): 
    return pd.to_numeric(s.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# --- CÁLCULOS ---
i = num(df_ing.iloc[:, 1]).sum()
f = num(df_fij['Importe']).sum()
v = num(df_mov['Importe']).sum() if not df_mov.empty else 0

# Buscamos el porcentaje de ahorro si existe
es_ah = df_ing.iloc[:, 0].astype(str).str.contains("Ahorro|%", case=False, na=False)
p_ahorro = num(pd.Series([df_ing.loc[es_ah].iloc[0, 1]]))[0] if es_ah.any() else 20.0
ahorro_obj = i * (p_ahorro / 100)

dispo = i - f - ahorro_obj - v

# Cálculo de tope diario
hoy = datetime.now()
_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_r = u_dia - hoy.day + 1
diario = dispo / dias_r if dias_r > 0 else 0

# --- INTERFAZ ---
st.title("💰 Mi Guardián Financiero")

c1, c2 = st.columns(2)
c1.metric("Disponible Mes", f"{dispo:.2f} €")
c2.metric("Para HOY", f"{diario:.2f} €", delta=f"{dias_r} días restantes")

# Gráfico de distribución
st.markdown("### 📊 Estado de Gastos")
df_graf = pd.DataFrame({
    "Concepto": ["Fijos", "Variables", "Ahorro", "Disponible"],
    "Euros": [f, v, ahorro_obj, max(0, dispo)]
})
fig = px.bar(df_graf, x="Concepto", y="Euros", color="Concepto", text_auto=".2s")
st.plotly_chart(fig, use_container_width=True)

# Formulario de registro
st.divider()
with st.form("gasto", clear_on_submit=True):
    col_a, col_b = st.columns([2, 1])
    con = col_a.text_input("¿En qué has gastado?")
    mon = col_b.number_input("Euros", min_value=0.0, step=1.0)
    if st.form_submit_button("Guardar Gasto"):
        if con and mon > 0:
            ws_mov.append_row([hoy.strftime("%Y-%m-%d"), con, "Gasto", mon])
            st.success("✅ ¡Anotado correctamente!")
            time.sleep(1)
            st.rerun()

# Botón de cierre de sesión
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()
