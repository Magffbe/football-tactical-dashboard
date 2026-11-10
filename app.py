import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from mplsoccer import Pitch, PyPizza
from statsbombpy import sb

# ---------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL Y ESTILOS DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Football Data Analytics | Dashboard Táctico",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Dashboard Táctico de Fútbol Avanzado")
st.markdown("Plataforma integral de análisis de rendimiento individual, radares comparativos y redes tácticas.")
st.divider()

# ---------------------------------------------------------
# DICCIONARIOS Y CARGA DE DATOS
# ---------------------------------------------------------
@st.cache_data
def obtener_partidos_mundial():
    try:
        df_m = sb.matches(competition_id=43, season_id=106)
        partidos = {}
        for _, r in df_m.iterrows():
            label = f"{r['home_team']} {r['home_score']} - {r['away_score']} {r['away_team']} ({r['match_date']})"
            partidos[label] = r['match_id']
        return partidos
    except Exception:
        # Fallback con partidos verificados si falla el índice global
        return {
            "Japón 2 - 1 España (2022-12-01)": 3857255,
            "Argentina 3 - 3 Francia (2022-12-18)": 3869685,
            "Argentina 3 - 0 Croacia (2022-12-13)": 3869519,
            "Francia 2 - 0 Marruecos (2022-12-14)": 3869552,
            "Costa Rica 2 - 4 Alemania (2022-12-01)": 3857289
        }

dict_partidos = obtener_partidos_mundial()

@st.cache_data
def cargar_eventos_json(match_id):
    url = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/events/{match_id}.json"
    df = pd.read_json(url)
    df['type_name'] = df['type'].apply(lambda x: x['name'] if isinstance(x, dict) else '')
    df['team_name'] = df['team'].apply(lambda x: x['name'] if isinstance(x, dict) else '')
    df['player_name'] = df['player'].apply(lambda x: x['name'] if isinstance(x, dict) else '')
    df['x'] = df['location'].apply(lambda loc: loc[0] if isinstance(loc, list) else None)
    df['y'] = df['location'].apply(lambda loc: loc[1] if isinstance(loc, list) else None)
    return df

# Estrutura principal en Pestañas limpias
tab1, tab2, tab3 = st.tabs([
    "📊 Rendimiento Individual", 
    "⚔️ Comparativa Cara a Cara (Radar)", 
    "🕸️ Redes de Pases (Passing Networks)"
])

# =========================================================
# PESTAÑA 1: ANÁLISIS POR JUGADOR Y PARTIDO (CÓDIGO ORIGINAL)
# =========================================================
with tab1:
    st.header("📊 Rendimiento Individual y Mapas de Acción")
    
    col_sel1, col_sel2 = st.columns(2)
    with col_sel1:
        partido_label1 = st.selectbox("Selecciona un Partido:", list(dict_partidos.keys()), key="p1_match")
        match_id1 = dict_partidos[partido_label1]
        
    try:
        df_ev1 = cargar_eventos_json(match_id1)
        equipos1 = sorted([t for t in df_ev1['team_name'].unique() if t])
        
        with col_sel2:
            equipo_sel1 = st.selectbox("Selecciona un Equipo:", equipos1, key="p1_team")
            
        df_eq1 = df_ev1[df_ev1['team_name'] == equipo_sel1]
        jugadores1 = sorted([j for j in df_eq1['player_name'].unique() if j])
        jugador_sel1 = st.selectbox("Selecciona un Jugador:", jugadores1, key="p1_player")
        
        df_j1 = df_eq1[df_eq1['player_name'] == jugador_sel1]
        pases_j1 = df_j1[df_j1['type_name'] == 'Pass'].copy()
        
        def es_comp(row):
            p_dict = row.get('pass', {})
            return 'outcome' not in p_dict if isinstance(p_dict, dict) else False
            
        pases_j1['es_completado'] = pases_j1.apply(es_comp, axis=1)
        
        # Métricas individuales (KPIs)
        total_p = len(pases_j1)
        comp_p = len(pases_j1[pases_j1['es_completado']])
        fall_p = total_p - comp_p
        prec_p = (comp_p / total_p * 100) if total_p > 0 else 0
        
        tiros_j1 = df_j1[df_j1['type_name'] == 'Shot']
        total_tiros = len(tiros_j1)
        xg_total = sum([t.get('shot', {}).get('statsbomb_xg', 0) for _, t in tiros_j1.iterrows() if isinstance(t.get('shot'), dict)])
        
        pases_prog = 0
        for _, p in pases_j1.iterrows():
            pass_dict = p.get('pass', {})
            if isinstance(pass_dict, dict) and 'end_location' in pass_dict:
                if (pass_dict['end_location'][0] - p['x']) >= 10:
                    pases_prog += 1

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Pases Intentados", total_p)
        c2.metric("Completados", comp_p)
        c3.metric("Fallados", fall_p)
        c4.metric("Precisión", f"{prec_p:.1f}%")
        c5.metric("Pases Progresivos", pases_prog)
        
        st.divider()
        
        # Gráficos Individuales
        col_g1, col_g2 = st.columns(2)
        pitch = Pitch(pitch_type='statsbomb', pitch_color='#19232d', line_color='#c7d5cc')
        
        with col_g1:
            st.markdown(f"#### 🗺️ Mapa de Pases: **{jugador_sel1}**")
            fig1, ax1 = plt.subplots(figsize=(6, 4.2), facecolor='#19232d')
            pitch.draw(ax=ax1)
            for _, pase in pases_j1.iterrows():
                pass_dict = pase.get('pass', {})
                if isinstance(pass_dict, dict) and 'end_location' in pass_dict:
                    x_fin, y_fin = pass_dict['end_location'][0], pass_dict['end_location'][1]
                    color = '#2ecc71' if pase['es_completado'] else '#e74c3c'
                    pitch.arrows(pase['x'], pase['y'], x_fin, y_fin, ax=ax1, color=color, alpha=0.7, width=1.5)
            st.pyplot(fig1)
            
        with col_g2:
            st.markdown(f"#### 🔥 Zona de Influencia (Heatmap)")
            fig2, ax2 = plt.subplots(figsize=(6, 4.2), facecolor='#19232d')
            pitch.draw(ax=ax2)
            if len(df_j1.dropna(subset=['x', 'y'])) > 2:
                sns.kdeplot(x=df_j1['x'], y=df_j1['y'], fill=True, thresh=0.05, levels=50, cmap='hot', alpha=0.6, ax=ax2)
            st.pyplot(fig2)
            
    except Exception:
        st.error("No se pudieron obtener datos completos para este partido. Selecciona otro encuentro del listado.")

# =========================================================
# PESTAÑA 2: COMPARATIVA CARA A CARA (RADAR LIMPIO + TABLA)
# =========================================================
with tab2:
    st.header("⚔️ Comparativa Cara a Cara de Jugadores")
    
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        partido_label2 = st.selectbox("Selecciona un Partido para el Radar:", list(dict_partidos.keys()), key="p2_match")
        match_id2 = dict_partidos[partido_label2]
        
    df_ev2 = cargar_eventos_json(match_id2)
    jugadores_lista2 = sorted([j for j in df_ev2['player_name'].unique() if j])
    
    with col_r1:
        j1_radar = st.selectbox("Jugador 1 (Verde):", jugadores_lista2, index=0, key="j1_rad")
    with col_r2:
        j2_radar = st.selectbox("Jugador 2 (Azul):", jugadores_lista2, index=min(1, len(jugadores_lista2)-1), key="j2_rad")
        
    def obtener_metricas(nombre):
        df_j = df_ev2[df_ev2['player_name'] == nombre]
        pases = df_j[df_j['type_name'] == 'Pass']
        total_p = len(pases)
        comp_p = sum([1 for _, p in pases.iterrows() if 'outcome' not in p.get('pass', {})]) if isinstance(pases, pd.DataFrame) else 0
        prec_p = (comp_p / total_p * 100) if total_p > 0 else 0
        
        tiros = df_j[df_j['type_name'] == 'Shot']
        total_t = len(tiros)
        xg = sum([t.get('shot', {}).get('statsbomb_xg', 0) for _, t in tiros.iterrows() if isinstance(t.get('shot'), dict)])
        defensivas = len(df_j[df_j['type_name'].isin(['Duel', 'Interception', 'Ball Recovery'])])
        return [total_p, round(prec_p, 1), total_t, round(xg, 2), defensivas]

    m_j1 = obtener_metricas(j1_radar)
    m_j2 = obtener_metricas(j2_radar)
    params = ["Pases Intentados", "Precisión Pases %", "Tiros", "xG Acumulado", "Acciones Defensivas"]

    col_c1, col_c2, col_c3 = st.columns([1, 2, 1])
    with col_c2:
        baker = PyPizza(
            params=params,
            background_color="#19232d",
            straight_line_color="#c7d5cc",
            straight_line_lw=1,
            last_circle_lw=1,
            other_circle_lw=1,
            inner_circle_size=5
        )

        fig_radar, ax_radar = baker.make_pizza(
            m_j1,
            compare_values=m_j2,
            figsize=(6, 6),
            param_location=108,
            kwargs_slices=dict(facecolor="#2ecc71", edgecolor="#19232d", linewidth=1, alpha=0.6),
            kwargs_compare=dict(facecolor="#3498db", edgecolor="#19232d", linewidth=1, alpha=0.6),
            kwargs_params=dict(color="white", fontsize=10),
            kwargs_values=dict(alpha=0),         # Oculta números superpuestos del jugador 1
            kwargs_compare_values=dict(alpha=0)  # Oculta números superpuestos del jugador 2
        )
        st.pyplot(fig_radar)

    # Tabla comparativa con números exactos debajo del gráfico
    st.subheader("📋 Tabla Comparativa de Datos Reales")
    df_comp_tabla = pd.DataFrame({
        "Métrica": params,
        f"🟩 {j1_radar}": m_j1,
        f"🟦 {j2_radar}": m_j2
    })
    st.dataframe(df_comp_tabla, use_container_width=True, hide_index=True)

# =========================================================
# PESTAÑA 3: REDES DE PASES (PASSING NETWORKS LIMPIA)
# =========================================================
with tab3:
    st.header("🕸️ Redes Tácticas de Pases (Passing Networks)")
    st.markdown("Estructura de circulación de balón, posiciones promedio y sociedades tácticas.")
    
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        partido_net_str = st.selectbox("Selecciona un Partido para la Red:", list(dict_partidos.keys()), key="p3_match")
        match_id_net = dict_partidos[partido_net_str]
        
    df_net = cargar_eventos_json(match_id_net)
    equipos_net = sorted([t for t in df_net['team_name'].unique() if t])
    
    with col_n2:
        equipo_net_sel = st.selectbox("Selecciona un Equipo:", equipos_net, key="p3_team")
        
    pases_eq = df_net[(df_net['type_name'] == 'Pass') & (df_net['team_name'] == equipo_net_sel)].copy()
    
    def es_comp_net(row):
        p_dict = row.get('pass', {})
        return 'outcome' not in p_dict if isinstance(p_dict, dict) else False
        
    pases_eq['es_completado'] = pases_eq.apply(es_comp_net, axis=1)
    pases_comp = pases_eq[pases_eq['es_completado']].copy()
    
    pases_comp['recipient_name'] = pases_comp['pass'].apply(
        lambda x: x.get('recipient', {}).get('name', '') if isinstance(x, dict) and isinstance(x.get('recipient'), dict) else ''
    )
    
    # 1. Posiciones Promedio
    pos_prom = pases_comp.groupby('player_name').agg(
        x_mean=('x', 'mean'), y_mean=('y', 'mean'), total_pases=('x', 'count')
    ).reset_index().sort_values(by='total_pases', ascending=False)
    
    # 2. Conexiones (Mínimo 2 pases)
    conex = pases_comp.groupby(['player_name', 'recipient_name']).size().reset_index(name='pass_count')
    conex = conex.merge(pos_prom[['player_name', 'x_mean', 'y_mean']], on='player_name').rename(columns={'x_mean': 'x_start', 'y_mean': 'y_start'})
    conex = conex.merge(pos_prom[['player_name', 'x_mean', 'y_mean']], left_on='recipient_name', right_on='player_name', suffixes=('', '_end')).rename(columns={'x_mean': 'x_end', 'y_mean': 'y_end'})
    conex = conex[conex['pass_count'] >= 2]
    
    st.divider()
    
    # 3. Gráfica de la Cancha en Matplotlib
    fig_net, ax_net = plt.subplots(figsize=(10, 6.5), facecolor='#19232d')
    pitch_net = Pitch(pitch_type='statsbomb', pitch_color='#19232d', line_color='#c7d5cc')
    pitch_net.draw(ax=ax_net)
    
    # Dibujar líneas de pase con grosor proporcional y transparencia
    max_pases_pareja = conex['pass_count'].max() if len(conex) > 0 else 1
    for _, row in conex.iterrows():
        grosor = (row['pass_count'] / max_pases_pareja) * 5 + 0.5  # Grosor controlado max 5.5px
        alpha_v = min(row['pass_count'] / max_pases_pareja, 0.9)
        pitch_net.lines(row['x_start'], row['y_start'], row['x_end'], row['y_end'], ax=ax_net, color='#2ecc71', lw=grosor, alpha=alpha_v, zorder=1)
        
    # Dibujar nodos de jugadores con escala contenida (evita círculos gigantes)
    tamanos_nodos = pos_prom['total_pases'] * 12 + 120
    pitch_net.scatter(pos_prom['x_mean'], pos_prom['y_mean'], s=tamanos_nodos, color='#e74c3c', edgecolors='white', linewidth=1.5, alpha=0.9, ax=ax_net, zorder=2)
    
    # Nombres de jugadores con tipografía clara
    for _, row in pos_prom.iterrows():
        apellido = row['player_name'].split()[-1] if row['player_name'] else ''
        pitch_net.annotate(
            apellido, 
            xy=(row['x_mean'], row['y_mean']), 
            c='white', 
            va='center', 
            ha='center', 
            size=8.5, 
            weight='bold', 
            ax=ax_net, 
            zorder=3
        )
        
    ax_net.set_title(f"Estructura Táctica: {equipo_net_sel} ({partido_net_str})", color='white', fontsize=12, pad=12)
    st.pyplot(fig_net)