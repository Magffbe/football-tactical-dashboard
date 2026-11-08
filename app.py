import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from mplsoccer import Pitch, VerticalPitch
from statsbombpy import sb

# Configuración de la página web
st.set_page_config(page_title="Dashboard de Análisis Táctico", page_icon="⚽", layout="wide")

st.title("⚽ Dashboard Táctico de Fútbol - Inteligencia Deportiva")

# 1. Cargar partidos disponibles en StatsBomb (Mundial 2022)
@st.cache_data
def cargar_partidos():
    return sb.matches(competition_id=43, season_id=106)

df_partidos = cargar_partidos()

# Selector de partidos en el sidebar
partidos_dict = {
    f"{row['home_team']} {row['home_score']} - {row['away_score']} {row['away_team']} ({row['match_date']})": row['match_id']
    for _, row in df_partidos.iterrows()
}

st.sidebar.header("⚙️ Filtros de Selección")
partido_seleccionado_str = st.sidebar.selectbox("Selecciona un Partido:", list(partidos_dict.keys()))
match_id = partidos_dict[partido_seleccionado_str]

# 2. Cargar eventos del partido seleccionado
@st.cache_data
def cargar_eventos(m_id):
    return sb.events(match_id=m_id)

df_eventos = cargar_eventos(match_id)

st.markdown(f"### 🏟️ Partido Seleccionado: **{partido_seleccionado_str}**")
st.divider()

# CREAMOS DOS PESTAÑAS INTERACTIVAS (Tabs) EN STREAMLIT
tab1, tab2 = st.tabs(["👤 Análisis Individual de Jugador", "🥅 Mapa de Tiros y Expected Goals (xG)"])

# ==========================================
# PESTAÑA 1: ANÁLISIS DE JUGADOR (PASES Y HEATMAP)
# ==========================================
with tab1:
    pases_df = df_eventos[df_eventos['type'] == 'Pass'].copy()
    lista_jugadores = sorted(pases_df['player'].dropna().unique())
    jugador_seleccionado = st.sidebar.selectbox("Selecciona un Jugador:", lista_jugadores)

    pases_jugador = pases_df[pases_df['player'] == jugador_seleccionado]

    # KPIs de jugador
    st.subheader(f"📊 Rendimiento de {jugador_seleccionado}")
    total_pases = len(pases_jugador)
    completados = len(pases_jugador[pases_jugador['pass_outcome'].isna()])
    fallados = total_pases - completados
    precision = (completados / total_pases * 100) if total_pases > 0 else 0

    pases_progresivos = 0
    for _, pase in pases_jugador.iterrows():
        if (pase['pass_end_location'][0] - pase['location'][0]) >= 10:
            pases_progresivos += 1

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Pases Intentados", total_pases)
    col2.metric("Completados", completados)
    col3.metric("Fallados", fallados)
    col4.metric("Precisión", f"{precision:.1f}%")
    col5.metric("Pases Progresivos", pases_progresivos)

    st.divider()

    col_graf1, col_graf2 = st.columns(2)

    with col_graf1:
        st.subheader("🗺️ Mapa de Pases")
        cancha1 = Pitch(pitch_type='statsbomb', pitch_color='#19232d', line_color='#c7d5cc')
        fig1, ax1 = cancha1.draw(figsize=(8, 6))
        for _, pase in pases_jugador.iterrows():
            x_ini, y_ini = pase['location'][0], pase['location'][1]
            x_fin, y_fin = pase['pass_end_location'][0], pase['pass_end_location'][1]
            color = '#e74c3c' if isinstance(pase['pass_outcome'], str) else '#2ecc71'
            cancha1.arrows(x_ini, y_ini, x_fin, y_fin, ax=ax1, color=color, alpha=0.7, width=2)
        st.pyplot(fig1)

    with col_graf2:
        st.subheader("🔥 Zona de Influencia (Heatmap)")
        eventos_jugador = df_eventos[df_eventos['player'] == jugador_seleccionado].dropna(subset=['location'])
        x_coords = [loc[0] for loc in eventos_jugador['location']]
        y_coords = [loc[1] for loc in eventos_jugador['location']]
        
        cancha2 = Pitch(pitch_type='statsbomb', pitch_color='#19232d', line_color='#c7d5cc')
        fig2, ax2 = cancha2.draw(figsize=(8, 6))
        if len(x_coords) > 0:
            sns.kdeplot(x=x_coords, y=y_coords, fill=True, thresh=0.05, levels=100, cmap='hot', alpha=0.6, ax=ax2)
        st.pyplot(fig2)

# ==========================================
# PESTAÑA 2: MAPA DE TIROS Y xG DEL PARTIDO
# ==========================================
with tab2:
    st.subheader("🎯 Comparativa de Remates y Expected Goals (xG)")
    
    # Filtrar eventos de tipo Shot
    tiros = df_eventos[df_eventos['type'] == 'Shot'].copy()
    equipos = tiros['team'].unique()
    
    if len(equipos) >= 2:
        eq1, eq2 = equipos[0], equipos[1]
        
        # Obtener xG acumulado por equipo
        xg_eq1 = tiros[tiros['team'] == eq1]['shot_statsbomb_xg'].sum()
        xg_eq2 = tiros[tiros['team'] == eq2]['shot_statsbomb_xg'].sum()
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric(f"xG Acumulado - {eq1}", f"{xg_eq1:.2f}")
        col_m2.metric(f"xG Acumulado - {eq2}", f"{xg_eq2:.2f}")
        
        st.divider()
        
        # Dibujar Canchas Verticales Lado a Lado
        cancha_media = VerticalPitch(pitch_type='statsbomb', half=True, pitch_color='#19232d', line_color='#c7d5cc')
        fig_shots, (ax_e1, ax_e2) = plt.subplots(1, 2, figsize=(10, 5), facecolor='#19232d')
        
        def render_tiros(df_tiros, equipo, ax_target):
            cancha_media.draw(ax=ax_target)
            tiros_e = df_tiros[df_tiros['team'] == equipo]
            
            for _, tiro in tiros_e.iterrows():
                x_t, y_t = tiro['location'][0], tiro['location'][1]
                es_gol = tiro['shot_outcome'] == 'Goal'
                color = '#2ecc71' if es_gol else '#e74c3c'
                alpha = 0.9 if es_gol else 0.4
                tamano = tiro['shot_statsbomb_xg'] * 700 + 40
                cancha_media.scatter(x_t, y_t, s=tamano, color=color, alpha=alpha, edgecolors='white', ax=ax_target)
                
            ax_target.set_title(f"{equipo}\nxG Total: {tiros_e['shot_statsbomb_xg'].sum():.2f}", color='white', fontsize=11)

        render_tiros(tiros, eq1, ax_e1)
        render_tiros(tiros, eq2, ax_e2)
        
        st.pyplot(fig_shots)