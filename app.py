import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import st_folium

# ==========================================
# CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="Análisis de Cobertura de Ventas", layout="wide")

# ==========================================
# FÓRMULA MATEMÁTICA PARA DISTANCIAS (HAVERSINE)
# ==========================================
def calcular_distancias_km(lat1, lon1, lat2_array, lon2_array):
    """Calcula la distancia en km desde un punto central a un array de coordenadas."""
    # Convertir a radianes
    lat1, lon1 = np.radians(lat1), np.radians(lon1)
    lat2, lon2 = np.radians(lat2_array), np.radians(lon2_array)
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Fórmula de Haversine
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    
    r_tierra = 6371 # Radio de la Tierra en km
    return c * r_tierra

# ==========================================
# CARGA Y LIMPIEZA DE DATOS (CON CACHÉ)
# ==========================================
@st.cache_data
def cargar_datos():
    df_trx = pd.read_excel("data/transacciones.xlsx")
    df_puntos = pd.read_excel("data/puntos.xlsx")
    
    # 1. Estandarizar nombres de columnas a mayúsculas y sin espacios extra
    df_trx.columns = df_trx.columns.str.strip().str.upper()
    df_puntos.columns = df_puntos.columns.str.strip().str.upper()
    
    # 2. EL TRUCO: Quitar las comillas simples de las coordenadas antes de convertir
    df_trx['LATITUDE'] = df_trx['LATITUDE'].astype(str).str.replace("'", "", regex=False)
    df_trx['LONGITUDE'] = df_trx['LONGITUDE'].astype(str).str.replace("'", "", regex=False)
    
    df_puntos['LATITUDE'] = df_puntos['LATITUDE'].astype(str).str.replace("'", "", regex=False)
    df_puntos['LONGITUDE'] = df_puntos['LONGITUDE'].astype(str).str.replace("'", "", regex=False)
    
    # 3. Forzar conversión a números para evitar el TypeError de np.radians
    df_trx['LATITUDE'] = pd.to_numeric(df_trx['LATITUDE'], errors='coerce')
    df_trx['LONGITUDE'] = pd.to_numeric(df_trx['LONGITUDE'], errors='coerce')
    
    df_puntos['LATITUDE'] = pd.to_numeric(df_puntos['LATITUDE'], errors='coerce')
    df_puntos['LONGITUDE'] = pd.to_numeric(df_puntos['LONGITUDE'], errors='coerce')
    
    # 4. Eliminar filas que se quedaron sin coordenadas
    df_trx = df_trx.dropna(subset=['LATITUDE', 'LONGITUDE'])
    df_puntos = df_puntos.dropna(subset=['LATITUDE', 'LONGITUDE'])
    
    return df_trx, df_puntos

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.title("📍 Análisis Geolocalizado de Ventas y Distribuidores")

# Intentar cargar los datos
try:
    df_trx, df_puntos = cargar_datos()
except FileNotFoundError:
    st.error("No se encontraron los archivos. Verifica que existan 'data/transacciones.xlsx' y 'data/puntos.xlsx'.")
    st.stop()
except Exception as e:
    st.error(f"Ocurrió un error al cargar los datos: {e}")
    st.stop()

# Validación preventiva del KeyError para 'NOMBRE'
if 'NOMBRE' not in df_puntos.columns:
    st.sidebar.error("Error: No se encontró la columna 'NOMBRE' en puntos.xlsx.")
    st.sidebar.warning("Columnas detectadas:")
    st.sidebar.write(df_puntos.columns.tolist())
    st.stop()

# ------------------------------------------
# MENÚ LATERAL (CONTROLES)
# ------------------------------------------
st.sidebar.header("Configuración de Análisis")

# Selector de Radio (km)
radio_km = st.sidebar.slider(
    "Selecciona el radio de análisis (Km)", 
    min_value=0.5, 
    max_value=10.0, 
    value=2.0, 
    step=0.5
)

# Selector de Punto de Interés
lista_puntos = df_puntos['NOMBRE'].dropna().unique().tolist()
punto_seleccionado = st.sidebar.selectbox("Selecciona un Punto de Interés", lista_puntos)

# Extraer coordenadas del punto seleccionado
datos_punto = df_puntos[df_puntos['NOMBRE'] == punto_seleccionado].iloc[0]
lat_punto = datos_punto['LATITUDE']
lon_punto = datos_punto['LONGITUDE']

# ------------------------------------------
# PROCESAMIENTO GEOLOCALIZADO (CÁLCULO)
# ------------------------------------------
# Calcular distancia desde el punto central hacia todas las transacciones
df_trx['DISTANCIA_KM'] = calcular_distancias_km(lat_punto, lon_punto, df_trx['LATITUDE'], df_trx['LONGITUDE'])

# Filtrar las transacciones que caen dentro del radio especificado
df_filtrado = df_trx[df_trx['DISTANCIA_KM'] <= radio_km].copy()

# ==========================================
# DISEÑO DE PANTALLA: MAPA (IZQ) Y DATOS (DER)
# ==========================================
col1, col2 = st.columns([3, 2])

# --- COLUMNA 1: EL MAPA ---
with col1:
    st.subheader(f"Mapa del área ({radio_km} km)")
    
    # Crear el objeto mapa centrado en el punto seleccionado
    m = folium.Map(location=[lat_punto, lon_punto], zoom_start=14)
    
    # Dibujar el marcador del punto central
    folium.Marker(
        [lat_punto, lon_punto], 
        popup=f"Punto: {punto_seleccionado}",
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
    
    # Dibujar el círculo que representa el radio (en metros)
    folium.Circle(
        location=[lat_punto, lon_punto],
        radius=radio_km * 1000, 
        color="blue",
        fill=True,
        fill_opacity=0.1
    ).add_to(m)
    
    # Dibujar las ventas como pequeños puntos verdes
    # (Limitado a 1500 visualmente para que el navegador no se congele)
    for idx, row in df_filtrado.head(1500).iterrows():
        folium.CircleMarker(
            location=[row['LATITUDE'], row['LONGITUDE']],
            radius=4,
            color="green",
            fill=True,
            fill_opacity=0.7,
            popup=f"Partner: {row.get('PARTNER', 'N/A')}<br>Tipo: {row.get('USERTYPE', 'N/A')}"
        ).add_to(m)
        
    # Renderizar mapa
    st_folium(m, width=700, height=550)

# --- COLUMNA 2: LOS DATOS ---
with col2:
    st.subheader("Resumen de Ventas en el Área")
    
    if df_filtrado.empty:
        st.warning(f"No hay ventas registradas a menos de {radio_km} km de {punto_seleccionado}.")
    else:
        # Métrica principal
        st.metric(label="Total de Ventas en el radio", value=len(df_filtrado))
        
        # Análisis 1: Por Partner
        st.markdown("#### Ventas por Partner")
        if 'PARTNER' in df_filtrado.columns:
            resumen_partner = df_filtrado['PARTNER'].value_counts().reset_index()
            resumen_partner.columns = ['PARTNER', 'CANTIDAD']
            st.dataframe(resumen_partner, use_container_width=True, hide_index=True)
        else:
            st.info("La columna 'PARTNER' no está presente en el archivo.")
        
        # Análisis 2: Por UserType y Departamento (Ajustado a DEPARTMENT)
        st.markdown("#### Detalle por Tipo y Depto.")
        if 'DEPARTMENT' in df_filtrado.columns and 'USERTYPE' in df_filtrado.columns:
            resumen_tipo = df_filtrado.groupby(['DEPARTMENT', 'USERTYPE']).size().reset_index(name='CANTIDAD')
            st.dataframe(resumen_tipo, use_container_width=True, hide_index=True)
        else:
            st.info("Faltan las columnas 'DEPARTMENT' o 'USERTYPE'.")
        
        # Análisis 3: Por Días (Ajustado a REQUESTDATE)
        columna_fecha = 'REQUESTDATE'
        
        if columna_fecha in df_filtrado.columns and 'PARTNER' in df_filtrado.columns:
            st.markdown("#### Ventas por Día y Partner")
            ventas_diarias = df_filtrado.groupby([columna_fecha, 'PARTNER']).size().reset_index(name='CANTIDAD')
            # Ordenar por fecha para mejor visualización
            ventas_diarias = ventas_diarias.sort_values(by=columna_fecha)
            st.dataframe(ventas_diarias, use_container_width=True, hide_index=True)
        else:
            st.info(f"Falta la columna '{columna_fecha}' o 'PARTNER' para el análisis temporal.")