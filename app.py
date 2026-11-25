import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import text
from database.connection import engine


# ---------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL Y ESTILOS DE LA PÁGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Football Scouting Analytics | Ligas Europeas",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Plataforma de Scouting — Ligas Europeas")
st.markdown("Análisis de rendimiento en ligas europeas recientes: equilibrio entre volumen (`_total`), eficiencia (`_p90`), minutos y edad.")
st.divider()


@st.cache_data(ttl=600, show_spinner=False)
def cargar_datos_fbref(temporada, liga):
    query = text("""
        SELECT *
        FROM estadisticas_fbref
        WHERE temporada = :temporada
          AND liga = :liga
    """)
    with engine.connect() as conn:
        df_limpio = pd.read_sql(query, conn, params={"temporada": temporada, "liga": liga})

    cols_numericas = [
        "age", "mp", "starts", "min",
        "gls_total", "ast_total", "g+a_total",
        "gls_p90", "ast_p90", "g+a_p90"
    ]
    for c in cols_numericas:
        if c in df_limpio.columns:
            df_limpio[c] = pd.to_numeric(df_limpio[c], errors="coerce").fillna(0)

    return df_limpio


# ---------------------------------------------------------
# 2. FILTROS PRINCIPALES DE SCOUTING
# ---------------------------------------------------------
col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
with col_f1:
    liga_sel = st.selectbox(
        "Selecciona la Competición:",
        [
            "Spain La Liga",
            "England Premier League",
            "UEFA Champions League",
            "Italy Serie A",
            "Germany Bundesliga",
            "France Ligue 1",
        ],
        key="p4_liga"
    )
with col_f2:
    temporada_sel = st.selectbox(
        "Temporada:",
        ["2026-2027", "2025-2026"],
        index=0,
        key="p4_temp"
    )
with col_f3:
    min_minutos = st.number_input(
        "Mín. Minutos:",
        min_value=0,
        max_value=3500,
        value=450,
        step=90,
        key="p4_mins"
    )

try:
    with st.spinner(f"⏳ Consultando datos de {liga_sel} ({temporada_sel}) en Supabase..."):
        df_liga = cargar_datos_fbref(temporada_sel, liga_sel)

    col_sub1, col_sub2 = st.columns(2)
    with col_sub1:
        equipos_disp = ["Todos los equipos"] + sorted(df_liga["squad"].dropna().unique().tolist())
        equipo_filtro = st.selectbox("Filtrar por Club:", equipos_disp, key="p4_club")
    with col_sub2:
        posiciones_disp = ["Todas las posiciones"] + sorted(df_liga["pos"].dropna().unique().tolist())
        pos_filtro = st.selectbox("Filtrar por Posición:", posiciones_disp, key="p4_pos")

    df_filtrado = df_liga[df_liga["min"] >= min_minutos].copy()
    if equipo_filtro != "Todos los equipos":
        df_filtrado = df_filtrado[df_filtrado["squad"] == equipo_filtro]
    if pos_filtro != "Todas las posiciones":
        df_filtrado = df_filtrado[df_filtrado["pos"] == pos_filtro]

    if len(df_filtrado) > 0:
        top_gol = df_filtrado.sort_values(by="gls_total", ascending=False).iloc[0]
        top_ast = df_filtrado.sort_values(by="ast_total", ascending=False).iloc[0]
        top_p90 = df_filtrado.sort_values(by="gls_p90", ascending=False).iloc[0]

        k1, k2, k3 = st.columns(3)
        k1.metric("⚽ Máximo Goleador", f"{top_gol['player']} ({int(top_gol['gls_total'])} goles)", top_gol["squad"])
        k2.metric("🎯 Máximo Asistidor", f"{top_ast['player']} ({int(top_ast['ast_total'])} asist.)", top_ast["squad"])
        k3.metric("⚡ Mejor Promedio Goles/90", f"{top_p90['player']} ({top_p90['gls_p90']:.2f})", top_p90["squad"])

        st.divider()

        st.subheader("📈 Mapa de Impacto Ofensivo (Goles vs. Asistencias)")
        fig_scat, ax_scat = plt.subplots(figsize=(10, 4.5), facecolor="#19232d")
        ax_scat.set_facecolor("#19232d")

        ax_scat.scatter(
            df_filtrado["gls_total"], df_filtrado["ast_total"],
            s=df_filtrado["min"] / 15, color="#2ecc71", alpha=0.75, edgecolors="white", linewidth=1
        )

        top_etiquetas = df_filtrado.sort_values(by="g+a_total", ascending=False).head(8)
        for _, r_et in top_etiquetas.iterrows():
            ax_scat.annotate(
                r_et["player"].split()[-1],
                (r_et["gls_total"] + 0.3, r_et["ast_total"] + 0.2),
                color="white", fontsize=8.5, weight="bold"
            )

        ax_scat.set_xlabel("Goles Totales", color="white")
        ax_scat.set_ylabel("Asistencias Totales", color="white")
        ax_scat.tick_params(colors="white")
        for spine in ax_scat.spines.values():
            spine.set_color("#4a5568")
        ax_scat.grid(True, linestyle="--", alpha=0.2, color="white")
        st.pyplot(fig_scat)

        st.subheader("📋 Ranking de Jugadores (Ordenado por Goles Totales)")
        cols_mostrar = ["player", "squad", "pos", "age", "mp", "min", "gls_total", "ast_total", "g+a_total", "gls_p90", "ast_p90"]
        cols_existentes = [c for c in cols_mostrar if c in df_filtrado.columns]
        df_tabla_final = df_filtrado.sort_values(by="gls_total", ascending=False)[cols_existentes]
        st.dataframe(df_tabla_final, width="stretch", hide_index=True)
    else:
        st.warning("No hay jugadores que cumplan con los filtros seleccionados o aún no hay datos cargados para esta temporada.")

except Exception as e:
    st.error(f"No se pudo conectar con Supabase en este momento ({e}). Verifica tu archivo .env y tu conexión a internet.")