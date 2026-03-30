import streamlit as st
import pandas as pd
from datetime import datetime

# --- Lógica de Predicción y Control ---
def analizar_finanzas(ingresos, fijos, variables, objetivo_ahorro_porcentaje):
    # 1. Gastos Fijos Totales
    total_fijos = sum(fijos)
    
    # 2. Ahorro Comprometido
    ahorro_obligatorio = ingresos * (objetivo_ahorro_porcentaje / 100)
    
    # 3. Lo que REALMENTE queda para vivir (Ocio, Comida, Varios)
    presupuesto_total_mes = ingresos - total_fijos - ahorro_obligatorio
    
    # 4. Predicción y Gasto Diario
    dias_mes = 30 # Simplificado
    dia_actual = datetime.now().day
    dias_restantes = dias_mes - dia_actual
    
    gasto_acumulado_variable = sum(variables)
    dinero_restante_variable = presupuesto_total_mes - gasto_acumulado_variable
    
    diario_disponible = dinero_restante_variable / dias_restantes if dias_restantes > 0 else 0
    
    return {
        "disponible_hoy": diario_disponible,
        "restante_mes": dinero_restante_variable,
        "ahorro_meta": ahorro_obligatorio,
        "estado": "Saludable" if dinero_restante_variable > 0 else "Alerta: Ajustar cinturón"
    }

# --- Interfaz de Usuario ---
st.title("🛡️ Guardián Financiero")

st.metric(label="Puedes gastar HOY", value=f"{42.50} €", help="Si gastas esto cada día, cumplirás tu ahorro.")

with st.expander("➕ Añadir Gasto Rápido"):
    concepto = st.text_input("¿En qué?")
    monto = st.number_input("¿Cuánto?", min_value=0.0)
    if st.button("Registrar Gasto"):
        st.success("Registrado en Google Sheets")

# Visualización de Salud Financiera
st.subheader("Predicción de Fin de Mes")
st.write("Si sigues así, ahorrarás **450 €** adicionales a tu objetivo.")
st.progress(0.7) # Ejemplo de llenado de presupuesto
