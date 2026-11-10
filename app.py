import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from mplsoccer import Pitch

# 1. Configuración principal de la página
st.set_page_config(
    page_title="Football Data Analytics | Passing Networks",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Dashboard Táctico de Fútbol - Passing Networks")
st.markdown("Análisis avanzado de rendimiento individual y redes de pases del equipo.")
st.divider()

# 2. Cargar datos del partido seleccionado (Japón vs España por URL raw verificada)
@st.cache_data
def cargar_eventos_partido():
    match_id = 3857255
    url = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json"
    df = pd.read_json(url)
    
    # Extraer nombres de diccionarios
    df['type_name'] = df['type'].apply(lambda x: x['name'] if isinstance(x, dict) else '')
    df['team_name'] = df['team'].apply(lambda x: x['name'] if isinstance(x, dict) else '')
    df['player_name'] = df['player'].apply(lambda x: x['name'] if isinstance(x, dict) else '')
    df['x'] = df['location'].apply(lambda loc: loc[0] if isinstance(loc, list) else None)
    df['y'] = df['location'].apply(lambda loc: loc[1] if isinstance(loc, list) else None)
    return df

df_eventos = cargar_eventos_partido()

# Barra lateral de filtros
st.sidebar.header("⚙️ Configuración")
equipos_disponibles = sorted([t for t in df_eventos['team_name'].unique() if t])
equipo_seleccionado = st.sidebar.selectbox("Selecciona un Equipo:", equipos_disponibles)

# ---------------------------------------------------------
# FILTRADO DE PASES COMPLETADOS DEL EQUIPO
# ---------------------------------------------------------
def es_pase_completado(row):
    if row['type_name'] == 'Pass' and row['team_name'] == equipo_seleccionado:
        pass_dict = row.get('pass', {})
        if isinstance(pass_dict, dict):
            return 'outcome' not in pass_dict
    return False

pases_equipo = df_eventos[df_eventos.apply(es_pase_completado, axis=1)].copy()
pases_equipo['recipient_name'] = pases_equipo['pass'].apply(
    lambda x: x.get('recipient', {}).get('name', '') if isinstance(x, dict) and isinstance(x.get('recipient'), dict) else ''
)

# ---------------------------------------------------------
# SECCIÓN 1: RED DE PASES DEL EQUIPO (PASSING NETWORK)
# ---------------------------------------------------------
st.header(f"🕸️ Passing Network: {equipo_seleccionado}")

# A. Posiciones promedio
posiciones_promedio = pases_equipo.groupby('player_name').agg(
    x_mean=('x', 'mean'),
    y_mean=('y', 'mean'),
    total_pases=('x', 'count')
).reset_index().sort_values(by='total_pases', ascending=False)

# B. Conexiones entre parejas
conexiones = pases_equipo.groupby(['player_name', 'recipient_name']).size().reset_index(name='pass_count')
conexiones = conexiones.merge(
    posiciones_promedio[['player_name', 'x_mean', 'y_mean']], 
    on='player_name'
).rename(columns={'x_mean': 'x_start', 'y_mean': 'y_start'})

conexiones = conexiones.merge(
    posiciones_promedio[['player_name', 'x_mean', 'y_mean']], 
    left_on='recipient_name', 
    right_on='player_name', 
    suffixes=('', '_end')
).rename(columns={'x_mean': 'x_end', 'y_mean': 'y_end'})

# Filtrar conexiones de 2 pases o más
conexiones = conexiones[conexiones['pass_count'] >= 2]

# C. Graficar la Red de Pases
fig_network, ax_network = plt.subplots(figsize=(10, 7), facecolor='#19232d')
pitch = Pitch(pitch_type='statsbomb', pitch_color='#19232d', line_color='#c7d5cc')
pitch.draw(ax=ax_network)

# Líneas de conexión
for _, row in conexiones.iterrows():
    grosor = row['pass_count'] * 0.8
    alpha_val = min(row['pass_count'] / conexiones['pass_count'].max(), 1.0)
    pitch.lines(
        row['x_start'], row['y_start'],
        row['x_end'], row['y_end'],
        ax=ax_network, color='#2ecc71', lw=grosor, alpha=alpha_val, zorder=1
    )

# Nodos de jugadores
pitch.scatter(
    posiciones_promedio['x_mean'], posiciones_promedio['y_mean'],
    s=posiciones_promedio['total_pases'] * 25,
    color='#e74c3c', edgecolors='white', linewidth=2, alpha=0.9, ax=ax_network, zorder=2
)

# Nombres
for _, row in posiciones_promedio.iterrows():
    apellido = row['player_name'].split()[-1] if row['player_name'] else ''
    pitch.annotate(
        apellido, xy=(row['x_mean'], row['y_mean']),
        c='white', va='center', ha='center', size=9, weight='bold', ax=ax_network, zorder=3
    )

ax_network.set_title(f"Estructura Táctica y Pases entre Jugadores - {equipo_seleccionado}", color='white', fontsize=12)
st.pyplot(fig_network)

st.divider()

# ---------------------------------------------------------
# SECCIÓN 2: ANÁLISIS INDIVIDUAL DE JUGADOR
# ---------------------------------------------------------
st.header("👤 Análisis por Jugador")

jugadores_equipo = sorted([j for j in pases_equipo['player_name'].unique() if j])
jugador_sel = st.sidebar.selectbox("Selecciona un Jugador:", jugadores_equipo)

pases_jugador = pases_equipo[pases_equipo['player_name'] == jugador_sel]

col_kpi1, col_kpi2, col_kpi3 = st.columns(3)
col_kpi1.metric("Pases Completados", len(pases_jugador))
col_kpi2.metric("Posición Promedio X", f"{posiciones_promedio[posiciones_promedio['player_name'] == jugador_sel]['x_mean'].values[0]:.1f}")
col_kpi3.metric("Posición Promedio Y", f"{posiciones_promedio[posiciones_promedio['player_name'] == jugador_sel]['y_mean'].values[0]:.1f}")

col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    st.subheader(f"🗺️ Mapa de Pases: {jugador_sel}")
    fig_ind, ax_ind = plt.subplots(figsize=(6, 4.5), facecolor='#19232d')
    pitch.draw(ax=ax_ind)
    
    # Dibujar pases del jugador
    for _, pase in pases_jugador.iterrows():
        pass_dict = pase.get('pass', {})
        if isinstance(pass_dict, dict) and 'end_location' in pass_dict:
            x_end, y_end = pass_dict['end_location'][0], pass_dict['end_location'][1]
            pitch.arrows(pase['x'], pase['y'], x_end, y_end, ax=ax_ind, color='#2ecc71', alpha=0.7, width=1.5)
            
    st.pyplot(fig_ind)

with col_graf2:
    st.subheader(f"🔥 Zona de Influencia")
    fig_kde, ax_kde = plt.subplots(figsize=(6, 4.5), facecolor='#19232d')
    pitch.draw(ax=ax_kde)
    
    if len(pases_jugador) > 2:
        sns.kdeplot(
            x=pases_jugador['x'], y=pases_jugador['y'],
            fill=True, thresh=0.05, levels=50, cmap='hot', alpha=0.6, ax=ax_kde
        )
    st.pyplot(fig_kde)