import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import calendar
import plotly.express as px
import time

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Economía Familiar", page_icon="💰", layout="centered")

# --- LOGIN ---
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

# --- CONEXIÓN ---
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
    
    if not df_mov.empty:
        df_mov.columns = [str(c).strip().capitalize() for c in df_mov.columns]

    ws_ing = sh.worksheet("Config")
    df_ing = pd.DataFrame(ws_ing.get_all_records())
    
    ws_fij = sh.worksheet("Gastos_Fijos")
    df_fij = pd.DataFrame(ws_fij.get_all_records())
    
    try:
        ws_bal = sh.worksheet("Balances")
    except:
        ws_bal = sh.add_worksheet(title="Balances", rows="100", cols="10")
        ws_bal.append_row(["Mes", "Ingresos", "Fijos", "Variables", "Ahorro_Real", "Objetivo"])
    
    df_bal = pd.DataFrame(ws_bal.get_all_records())
except Exception as e:
    st.error(f"Error al cargar pestañas: {e}")
    st.stop()

def num(s): return pd.to_numeric(s.astype(str).str.replace(',', '.'), errors='coerce').fillna(0)

# --- CÁLCULOS MES ACTUAL ---
es_ah = df_ing.iloc[:, 0].astype(str).str.contains("Ahorro|%", case=False, na=False)
i_total = num(df_ing.loc[~es_ah].iloc[:, 1]).sum()
f_total = num(df_fij['Importe']).sum()

hoy = datetime.now()
mes_actual_str = hoy.strftime("%Y-%m")
v_total = 0

if not df_mov.empty and 'Fecha' in df_mov.columns:
    df_mov['Fecha'] = pd.to_datetime(df_mov['Fecha'], errors='coerce')
    mask = (df_mov['Fecha'].dt.month == hoy.month) & (df_mov['Fecha'].dt.year == hoy.year)
    v_total = num(df_mov.loc[mask, 'Importe']).sum()

p_ahorro = num(pd.Series([df_ing.loc[es_ah].iloc[0, 1]]))[0] if es_ah.any() else 20.0
ahorro_obj = i_total * (p_ahorro / 100)
dispo = i_total - f_total - ahorro_obj - v_total
ahorro_actual = i_total - f_total - v_total

_, u_dia = calendar.monthrange(hoy.year, hoy.month)
dias_r = u_dia - hoy.day + 1
diario = dispo / dias_r if dias_r > 0 else 0

# --- INTERFAZ ---
st.title("🛡️ Mi Guardián Financiero")

c1, c2, c3 = st.columns(3)
c1.metric("Disponible Mes", f"{dispo:.2f} €")
c2.metric("Para HOY", f"{diario:.2f} €")
c3.metric("Ahorro Real", f"{ahorro_actual:.2f} €", delta=f"{ahorro_actual - ahorro_obj:.2f} meta")

# --- GRÁFICO ---
data_chart = pd.DataFrame({
    "Columna": ["1. Ingresos", "2. Distribución", "2. Distribución", "2. Distribución", "2. Distribución"],
    "Concepto": ["Ingresos Totales", "Gastos Fijos", "Gastos Variables", "Ahorro Objetivo", "Disponible"],
    "Euros": [i_total, f_total, v_total, ahorro_obj, max(0, dispo)]
})
fig = px.bar(data_chart, x="Columna", y="Euros", color="Concepto", text_auto=".2f",
             color_discrete_map={"Ingresos Totales": "#2ECC71", "Gastos Fijos": "#E74C3C", 
                                "Gastos Variables": "#F39C12", "Ahorro Objetivo": "#3498DB", "Disponible": "#1ABC9C"})
fig.update_layout(legend=dict(orientation="h", y=-0.5, x=0.5, xanchor="center"), margin=dict(b=100))
st.plotly_chart(fig, use_container_width=True)

# --- ÚLTIMOS MOVIMIENTOS ---
st.markdown("### 📝 Últimos 5 movimientos")
if not df_mov.empty:
    columnas_ver = [c for c in df_mov.columns if c in ['Fecha', 'Concepto', 'Categoría', 'Importe']]
    st.table(df_mov[columnas_ver].tail(5).iloc[::-1])
else:
    st.info("Sin gastos registrados este mes.")

# --- REGISTRAR GASTO ---
st.divider()
st.subheader("💸 Registrar Gasto")
with st.form("gasto", clear_on_submit=True):
    col_con, col_cat, col_mon = st.columns([2, 2, 1])
    con = col_con.text_input("¿En qué?")
    cat = col_cat.selectbox("Categoría", ["Comida", "Super", "Ocio", "Transporte", "Hogar", "Otros"])
    mon = col_mon.number_input("Euros", min_value=0.0, step=1.0)
    if st.form_submit_button("Guardar Gasto") and con and mon > 0:
        ws_mov.append_row([hoy.strftime("%Y-%m-%d"), con, cat, mon])
        st.success("✅ ¡Anotado!")
        time.sleep(1); st.rerun()

# --- CONFIGURACIÓN ---
st.divider()
st.subheader("⚙️ Gestión y Cierre")

tab_bal, tab_ing, tab_fij, tab_cie = st.tabs(["📊 Balances", "💰 Sueldos", "🏠 Fijos", "🔒 Cerrar Mes"])

with tab_bal:
    if not df_bal.empty:
        st.dataframe(df_bal, use_container_width=True, hide_index=True)
    else:
        st.info("No hay balances cerrados.")

with tab_ing:
    with st.form("edit_ing"):
        nuevos_i = []
        for index, row in df_ing.iterrows():
            val = st.number_input(f"{row[0]}", value=float(num(pd.Series(row[1]))[0]))
            nuevos_i.append([row[0], val])
        if st.form_submit_button("💾 Guardar Cambios"):
            ws_ing.update(range_name='A2', values=nuevos_i); st.rerun()

with tab_fij:
    st.dataframe(df_fij, use_container_width=True, hide_index=True)
    st.write("---")
    
    t_mod, t_add, t_del = st.tabs(["✏️ Modificar", "➕ Añadir", "🗑️ Borrar"])
    
    with t_mod:
        # Selector FUERA del form para que sea reactivo y actualice el importe al cambiar la opcion
        opc_mod = df_fij.iloc[:, 0].tolist() if not df_fij.empty else []
        sel_mod = st.selectbox("Gasto a modificar", opc_mod, key="sel_mod_fij")
        
        p_act = 0.0
        if sel_mod:
            p_act = float(df_fij[df_fij.iloc[:,0] == sel_mod].iloc[0,1])
        
        with st.form("form_mod_fij"):
            new_p = st.number_input("Nuevo Importe (€)", value=p_act, step=1.0)
            if st.form_submit_button("Actualizar Precio"):
                cell = ws_fij.find(sel_mod)
                ws_fij.update_cell(cell.row, 2, new_p)
                st.success(f"✅ Precio de {sel_mod} actualizado"); time.sleep(1); st.rerun()

    with t_add:
        with st.form("add_f", clear_on_submit=True):
            nf = st.text_input("Nombre"); it = st.number_input("Importe (€)", min_value=0.0)
            if st.form_submit_button("Añadir"):
                if nf and it > 0: ws_fij.append_row([nf, it]); st.rerun()
                
    with t_del:
        with st.form("del_f"):
            opc_del = df_fij.iloc[:, 0].tolist() if not df_fij.empty else []
            sel_del = st.selectbox("Eliminar gasto", opc_del)
            if st.form_submit_button("Eliminar"):
                if sel_del:
                    cell = ws_fij.find(sel_del)
                    ws_fij.delete_rows(cell.row); st.rerun()

with tab_cie:
    diff = ahorro_actual - ahorro_obj
    if diff >= 0:
        st.success(f"¡Vas genial! Superas tu meta por {diff:.2f} €")
    else:
        st.warning(f"Ojo, vas {abs(diff):.2f} € por debajo del objetivo")
    
    if st.button("🚀 GUARDAR BALANCE FINAL"):
        if diff >= 0: st.balloons()
        ws_bal.append_row([mes_actual_str, i_total, f_total, v_total, ahorro_actual, ahorro_obj])
        st.success("¡Balance guardado!"); time.sleep(1); st.rerun()

# --- SALIR ---
st.write("---")
cl, cc, cr = st.columns([1, 1, 1])
with cc:
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state["autenticado"] = False
        st.rerun()
