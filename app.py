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
                    if str(st.secrets["passwords"][u]) == p:
                        st.session_state["autenticado"] = True
                        st.rerun()
                st.error("❌ Credenciales incorrectas")
        return False
    return True

if not check_password():
    st.stop()

# --- CONEXIÓN MAESTRA ---
@st.cache_resource
def conectar_excel():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_info = dict(st.secrets["gcp_service_account"])
        pk = creds_info["private_key"].replace("\\n", "\n").strip().strip('"').strip("'")
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
    st.error(f"Error al cargar pestañas: {e}")
    st.stop()

def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# --- CÁLCULOS CORRECTOS ---
es_ah = df_ing.iloc[:, 0].astype(str).str.contains("Ahorro|%", case=False, na=False)
i_total = num(df_ing.loc[~es_ah].iloc[:, 1]).sum()
f_total = num(df_fij['Importe']).sum()
v_total = num(df_mov['Importe']).sum() if not df_mov.empty else 0
p_ahorro = num(pd.Series([df_ing.loc[es_ah].iloc[0, 1]]))[0] if es_ah.any() else 20.0
ahorro_obj = i_total * (p_ahorro / 100)
dispo = i_total - f_total - ahorro_obj - v_total

hoy = datetime.now()
_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_r = u_dia - hoy.day + 1
diario = dispo / dias_r if dias_r > 0 else 0

# --- INTERFAZ ---
st.title("🛡️ Mi Guardián Financiero")

col1, col2 = st.columns(2)
col1.metric("Disponible Mes", f"{dispo:.2f} €")
col2.metric("Límite HOY", f"{diario:.2f} €", delta=f"{dias_r} días rest.")

# --- GRÁFICO ---
st.markdown("### 📊 Comparativa Ingresos vs Distribución")
data_chart = pd.DataFrame({
    "Columna": ["1. Ingresos", "2. Distribución", "2. Distribución", "2. Distribución", "2. Distribución"],
    "Concepto": ["Ingresos Totales", "Gastos Fijos", "Gastos Variables", "Ahorro", "Disponible"],
    "Euros": [i_total, f_total, v_total, ahorro_obj, max(0, dispo)]
})

fig = px.bar(data_chart, x="Columna", y="Euros", color="Concepto", text="Euros",
             color_discrete_map={
                 "Ingresos Totales": "#2ECC71",
                 "Gastos Fijos": "#E74C3C",
                 "Gastos Variables": "#F39C12",
                 "Ahorro": "#3498DB",
                 "Disponible": "#1ABC9C"
             })
fig.update_traces(texttemplate='%{text:.2f} €', textposition='inside', textfont_size=12)
fig.update_layout(
    xaxis_title="", yaxis_title="Euros (€)",
    legend=dict(orientation="h", yanchor="bottom", y=-0.5, xanchor="center", x=0.5, title=""),
    margin=dict(t=20, b=100, l=10, r=10), height=500
)
st.plotly_chart(fig, use_container_width=True)

# --- HISTORIAL ---
st.markdown("### 📝 Últimos 5 movimientos")
if not df_mov.empty:
    st.table(df_mov.tail(5).iloc[::-1])
else:
    st.info("Aún no hay movimientos registrados.")

# --- REGISTRAR GASTO ---
st.divider()
st.subheader("💸 Registrar Gasto")
with st.form("gasto", clear_on_submit=True):
    col_con, col_cat, col_mon = st.columns([2, 2, 1])
    with col_con:
        concepto = st.text_input("¿En qué?")
    with col_cat:
        categoria = st.selectbox("Categoría", ["Comida", "Supermercado", "Ocio", "Transporte", "Hogar", "Salud", "Ropa", "Otros"])
    with col_mon:
        monto = st.number_input("Euros", min_value=0.0, step=1.0)
    if st.form_submit_button("Guardar Gasto"):
        if concepto and monto > 0:
            ws_mov.append_row([hoy.strftime("%Y-%m-%d"), concepto, categoria, monto])
            st.success(f"✅ Anotado en {categoria}")
            time.sleep(1)
            st.rerun()

# --- GESTIÓN DE DATOS (TABLAS EDITABLES) ---
st.divider()
st.subheader("⚙️ Configuración del Sistema")

# 1. INGRESOS Y AHORRO
exp_ing = st.expander("Modificar Sueldos y % Ahorro")
with exp_ing:
    st.info("Haz clic en las celdas de la derecha para cambiar los importes:")
    # Editor de tabla para ingresos
    edited_df_ing = st.data_editor(
        df_ing,
        use_container_width=True,
        hide_index=True,
        column_config={
            df_ing.columns[1]: st.column_config.NumberColumn("Euros / %", format="%.2f")
        }
    )
    if st.button("💾 Guardar Ingresos y Ahorro"):
        ws_ing.clear()
        ws_ing.update([edited_df_ing.columns.values.tolist()] + edited_df_ing.values.tolist())
        st.success("✅ Ingresos actualizados en Excel")
        time.sleep(1)
        st.rerun()

# 2. GASTOS FIJOS (TABLA EDITABLE FUNCIONAL)
exp_fij = st.expander("Gestionar Gastos Fijos (Tabla Interactiva)")
with exp_fij:
    st.write("Edita directamente, añade filas al final o selecciona una fila para borrarla:")
    
    # Editor de tabla dinámico
    edited_df_fij = st.data_editor(
        df_fij,
        num_rows="dynamic",  # Permite añadir y borrar filas directamente
        use_container_width=True,
        hide_index=True,
        column_config={
            "Importe": st.column_config.NumberColumn("Importe (€)", format="%.2f €")
        }
    )
    
    if st.button("💾 Guardar cambios en Gastos Fijos"):
        # Limpiamos la pestaña y subimos el nuevo dataframe completo
        ws_fij.clear()
        # Preparamos los datos incluyendo los encabezados
        data_to_upload = [edited_df_fij.columns.values.tolist()] + edited_df_fij.values.tolist()
        ws_fij.update(data_to_upload)
        st.success("✅ Lista de gastos fijos actualizada")
        time.sleep(1)
        st.rerun()

# --- CIERRE DE SESIÓN ---
st.write("---")
_, col_logout, _ = st.columns([1, 1, 1])
with col_logout:
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state["autenticado"] = False
        st.rerun()
