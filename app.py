import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from mplsoccer import Pitch, VerticalPitch, PyPizza
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

# PESTAÑAS INTERACTIVAS (Tabs)
tab1, tab2, tab3 = st.tabs([
    "👤 Análisis Individual", 
    "🥅 Mapa de Tiros y xG", 
    "⚔️ Comparador de Jugadores (Radar)"
])

# ==========================================
# PESTAÑA 1: ANÁLISIS DE JUGADOR
# ==========================================
with tab1:
    pases_df = df_eventos[df_eventos['type'] == 'Pass'].copy()
    lista_jugadores = sorted(pases_df['player'].dropna().unique())
    jugador_seleccionado = st.sidebar.selectbox("Selecciona un Jugador (Vista Individual):", lista_jugadores)

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
# PESTAÑA 2: MAPA DE TIROS Y xG
# ==========================================
with tab2:
    st.subheader("🎯 Comparativa de Remates y Expected Goals (xG)")
    
    tiros = df_eventos[df_eventos['type'] == 'Shot'].copy()
    equipos = tiros['team'].unique()
    
    if len(equipos) >= 2:
        eq1, eq2 = equipos[0], equipos[1]
        
        xg_eq1 = tiros[tiros['team'] == eq1]['shot_statsbomb_xg'].sum()
        xg_eq2 = tiros[tiros['team'] == eq2]['shot_statsbomb_xg'].sum()
        
        col_m1, col_m2 = st.columns(2)
        col_m1.metric(f"xG Acumulado - {eq1}", f"{xg_eq1:.2f}")
        col_m2.metric(f"xG Acumulado - {eq2}", f"{xg_eq2:.2f}")
        
        st.divider()
        
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

# ==========================================
# PESTAÑA 3: COMPARADOR DE JUGADORES (RADAR)
# ==========================================
with tab3:
    st.subheader("⚔️ Comparador Cara a Cara de Jugadores")
    
    todos_jugadores = sorted(df_eventos['player'].dropna().unique())
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        j1 = st.selectbox("Selecciona Jugador 1 (Verde):", todos_jugadores, index=0)
    with col_sel2:
        j2 = st.selectbox("Selecciona Jugador 2 (Azul):", todos_jugadores, index=min(1, len(todos_jugadores)-1))
        
    def obtener_metrics(nombre):
        df_j = df_eventos[df_eventos['player'] == nombre]
        pases = df_j[df_j['type'] == 'Pass']
        tot_p = len(pases)
        p_comp = len(pases[pases['pass_outcome'].isna()])
        prec_p = (p_comp / tot_p * 100) if tot_p > 0 else 0
        
        pases_prog = 0
        for _, p in pases.iterrows():
            if (p['pass_end_location'][0] - p['location'][0]) >= 10:
                pases_prog += 1
                
        tiros_j = df_j[df_j['type'] == 'Shot']
        tot_t = len(tiros_j)
        xg = tiros_j['shot_statsbomb_xg'].sum() if tot_t > 0 else 0
        defensivas = len(df_j[df_j['type'].isin(['Duel', 'Interception', 'Ball Recovery'])])
        
        return [tot_p, round(prec_p, 1), pases_prog, tot_t, round(xg, 2), defensivas]

    params = ["Pases Intentados", "Precisión Pases %", "Pases Progresivos", "Tiros", "xG Generado", "Acciones Defensivas"]
    val1 = obtener_metrics(j1)
    val2 = obtener_metrics(j2)

    col_rad, col_tab = st.columns([1.2, 1])
    
    with col_rad:
        baker = PyPizza(
            params=params,
            background_color="#19232d",
            straight_line_color="#c7d5cc",
            straight_line_lw=1,
            last_circle_lw=1,
            other_circle_lw=1,
            inner_circle_size=5
        )

        fig_pizza, ax_pizza = baker.make_pizza(
            val1,
            compare_values=val2,
            figsize=(7, 7),
            param_location=106,
            kwargs_slices=dict(facecolor="#2ecc71", edgecolor="#19232d", linewidth=1, alpha=0.6),
            kwargs_compare=dict(facecolor="#3498db", edgecolor="#19232d", linewidth=1, alpha=0.6),
            kwargs_params=dict(color="white", fontsize=10),
            kwargs_values=dict(alpha=0),
            kwargs_compare_values=dict(alpha=0)
        )
        st.pyplot(fig_pizza)

    with col_tab:
        st.markdown(f"#### 📊 Métricas Comparativas")
        df_comp = pd.DataFrame({
            'Métrica': params,
            j1: val1,
            j2: val2
        })
        st.dataframe(df_comp, use_container_width=True, hide_index=True)