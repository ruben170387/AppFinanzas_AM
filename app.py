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

# --- CONEXIÓN MAESTRA (VERSIÓN ANTIFALLOS) ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = dict(st.secrets["gcp_service_account"])
        
        # Limpieza profunda de la clave
        raw_pk = creds_dict["private_key"]
        
        # Eliminamos cualquier rastro de comillas, barras o saltos de línea mal puestos
        clean_pk = raw_pk.replace("\\n", "\n").replace('"', '').replace("'", "").strip()
        
        # Reconstruimos la clave para asegurar que Google la acepte
        if "-----BEGIN PRIVATE KEY-----" not in clean_pk:
            clean_pk = "-----BEGIN PRIVATE KEY-----\n" + clean_pk
        if "-----END PRIVATE KEY-----" not in clean_pk:
            clean_pk = clean_pk + "\n-----END PRIVATE KEY-----"
            
        creds_dict["private_key"] = clean_pk
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client.open("App_Finanzas")
    except Exception as e:
        st.error(f"❌ Error crítico de llaves: {e}")
        return None

sh = conectar_excel()
if sh is None:
    st.stop()

# --- EL RESTO DE TU APP (DATOS Y GRÁFICOS) ---
try:
    ws_config = sh.worksheet("Config")
    df_ingresos = pd.DataFrame(ws_config.get_all_records())
    ws_fijos = sh.worksheet("Gastos_Fijos")
    df_fijos = pd.DataFrame(ws_fijos.get_all_records())
    ws_movimientos = sh.worksheet("Movimientos")
    df_movimientos = pd.DataFrame(ws_movimientos.get_all_records())
except Exception as e:
    st.error(f"Error al leer pestañas: {e}")
    st.stop()

def limpiar_numeros(serie):
    return pd.to_numeric(serie.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# Cálculos
es_ahorro = df_ingresos.iloc[:, 0].astype(str).str.contains("Ahorro|%|Objetivo", case=False, na=False)
porcentaje_ahorro = limpiar_numeros(pd.Series([df_ingresos.loc[es_ahorro].iloc[0, 1]]))[0] if es_ahorro.any() else 20.0
total_ingresos = limpiar_numeros(df_ingresos.loc[~es_ahorro].iloc[:, 1]).sum()
total_fijos = limpiar_numeros(df_fijos['Importe']).sum()
ahorro_objetivo = total_ingresos * (porcentaje_ahorro / 100)
gastos_variables_totales = limpiar_numeros(df_movimientos['Importe']).sum() if not df_movimientos.empty else 0
disponible_mes = total_ingresos - total_fijos - ahorro_objetivo - gastos_variables_totales
hoy = datetime.now()
_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_restantes = u_dia - hoy.day + 1
diario_hoy = disponible_mes / dias_restantes if dias_restantes > 0 else 0

# Interfaz
st.title("💰 Economía Familiar")
c1, c2 = st.columns(2)
c1.metric("Disponible", f"{disponible_mes:.2f} €")
c2.metric("Límite Hoy", f"{diario_hoy:.2f} €")

# Gráfico
st.markdown("### 📊 Gastos vs Ingresos")
datos_barras = pd.DataFrame({
    "Concepto": ["Fijos", "Variables", "Ahorro", "Disponible"],
    "Cantidad": [total_fijos, gastos_variables_totales, ahorro_objetivo, max(0, disponible_mes)]
})
fig = px.bar(datos_barras, x="Concepto", y="Cantidad", color="Concepto", text="Cantidad")
st.plotly_chart(fig, use_container_width=True)

# Registro
st.divider()
with st.form("nuevo_gasto", clear_on_submit=True):
    con = st.text_input("Concepto")
    cat = st.selectbox("Categoría", ["Comida", "Ocio", "Transporte", "Otros"])
    mon = st.number_input("Importe (€)", min_value=0.0, step=0.5)
    if st.form_submit_button("Guardar"):
        if con and mon > 0:
            ws_movimientos.append_row([hoy.strftime("%Y-%m-%d"), con, cat, mon])
            st.success("Guardado")
            st.rerun()

# Configuración (Simplificada)
with st.expander("⚙️ Configuración"):
    st.write("Gestiona tus datos desde el Excel directamente para mayor seguridad.")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.rerun()
