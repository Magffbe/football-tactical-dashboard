import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from sqlalchemy import text
from database.connection import engine


# ---------------------------------------------------------
# 1. CONFIGURACIÓN GENERAL Y ESTILOS RESPONSIVE
# ---------------------------------------------------------
st.set_page_config(
    page_title="Football Scouting Analytics | Ligas Europeas",
    page_icon="⚽",
    layout="wide",
)

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1400px;
        }
        div[data-testid="stMetric"] {
            background-color: rgba(25, 35, 45, 0.55);
            border: 1px solid rgba(148, 163, 184, 0.2);
            padding: 0.75rem 0.9rem;
            border-radius: 0.6rem;
        }
        @media (max-width: 768px) {
            .block-container {
                padding-left: 0.85rem;
                padding-right: 0.85rem;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("⚽ Plataforma de Scouting — Ligas Europeas")
st.caption(
    "Evaluación de perfiles en ligas europeas: cruce entre volumen (_total), eficiencia (_p90), minutos y edad."
)


@st.cache_data(ttl=600, show_spinner=False)
def cargar_datos_fbref(temporada: str, liga: str) -> pd.DataFrame:
    query = text(
        """
        SELECT *
        FROM estadisticas_fbref
        WHERE temporada = :temporada
          AND liga = :liga
        """
    )
    with engine.connect() as conn:
        df_limpio = pd.read_sql(query, conn, params={"temporada": temporada, "liga": liga})

    cols_numericas = [
        "age", "mp", "starts", "min", "90s",
        "gls_total", "ast_total", "g+a_total", "g_pk_total", "pk_total",
        "gls_p90", "ast_p90", "g+a_p90", "g_pk_p90",
    ]
    for c in cols_numericas:
        if c in df_limpio.columns:
            df_limpio[c] = pd.to_numeric(df_limpio[c], errors="coerce").fillna(0)

    if "g+a_total" not in df_limpio.columns and {"gls_total", "ast_total"}.issubset(df_limpio.columns):
        df_limpio["g+a_total"] = df_limpio["gls_total"] + df_limpio["ast_total"]

    if "g+a_p90" not in df_limpio.columns and {"gls_p90", "ast_p90"}.issubset(df_limpio.columns):
        df_limpio["g+a_p90"] = df_limpio["gls_p90"] + df_limpio["ast_p90"]

    return df_limpio


def clasificar_perfil(row, prom_vol: float, prom_efi: float) -> str:
    vol = row.get("g+a_total", 0)
    efi = row.get("g+a_p90", 0)
    if vol >= prom_vol and efi >= prom_efi:
        return "Alto Volumen + Alta Eficiencia"
    if vol < prom_vol and efi >= prom_efi:
        return "Eficiencia en Muestra Menor"
    if vol >= prom_vol and efi < prom_efi:
        return "Volumen / Acumulación"
    return "Base / Desarrollo"


# ---------------------------------------------------------
# 2. FILTROS PRINCIPALES DE SCOUTING
# ---------------------------------------------------------
col_f1, col_f2, col_f3 = st.columns([2.2, 1.5, 1.3])
with col_f1:
    liga_sel = st.selectbox(
        "Competición",
        [
            "Spain La Liga",
            "England Premier League",
            "UEFA Champions League",
            "Italy Serie A",
            "Germany Bundesliga",
            "France Ligue 1",
        ],
        key="p4_liga",
    )
with col_f2:
    temporada_sel = st.selectbox(
        "Temporada",
        ["2026-2027", "2025-2026"],
        index=0,
        key="p4_temp",
    )
with col_f3:
    min_minutos = st.number_input(
        "Mín. Minutos",
        min_value=0,
        max_value=3600,
        value=450,
        step=90,
        key="p4_mins",
    )

try:
    with st.spinner(f"Consultando {liga_sel} ({temporada_sel})..."):
        df_liga = cargar_datos_fbref(temporada_sel, liga_sel)

    if df_liga.empty:
        st.warning("No hay registros en la base para esta combinación de competición y temporada.")
        st.stop()

    col_sub1, col_sub2, col_sub3, col_sub4 = st.columns([1.6, 1.4, 1.5, 1.5])
    with col_sub1:
        equipos_disp = ["Todos los equipos"] + sorted(df_liga["squad"].dropna().unique().tolist())
        equipo_filtro = st.selectbox("Club", equipos_disp, key="p4_club")
    with col_sub2:
        posiciones_disp = ["Todas las posiciones"] + sorted(df_liga["pos"].dropna().unique().tolist())
        pos_filtro = st.selectbox("Posición", posiciones_disp, key="p4_pos")
    with col_sub3:
        edades_validas = df_liga.loc[df_liga["age"] > 0, "age"]
        edad_min_abs = int(edades_validas.min()) if not edades_validas.empty else 16
        edad_max_abs = int(edades_validas.max()) if not edades_validas.empty else 40
        if edad_min_abs < edad_max_abs:
            rango_edad = st.slider(
                "Rango de Edad",
                min_value=edad_min_abs,
                max_value=edad_max_abs,
                value=(edad_min_abs, edad_max_abs),
                key="p4_edad",
            )
        else:
            rango_edad = (edad_min_abs, edad_max_abs)
            st.caption(f"Edad disponible: {edad_min_abs}")
    with col_sub4:
        buscar_jugador = st.text_input("Buscar Jugador", placeholder="Ej. Yamal, Raphinha...", key="p4_buscar").strip()

    df_filtrado = df_liga[df_liga["min"] >= min_minutos].copy()
    if equipo_filtro != "Todos los equipos":
        df_filtrado = df_filtrado[df_filtrado["squad"] == equipo_filtro]
    if pos_filtro != "Todas las posiciones":
        df_filtrado = df_filtrado[df_filtrado["pos"] == pos_filtro]
    if "age" in df_filtrado.columns and not df_filtrado.empty:
        df_filtrado = df_filtrado[
            ((df_filtrado["age"] >= rango_edad[0]) & (df_filtrado["age"] <= rango_edad[1]))
            | (df_filtrado["age"] == 0)
        ]
    if buscar_jugador and "player" in df_filtrado.columns:
        df_filtrado = df_filtrado[df_filtrado["player"].str.contains(buscar_jugador, case=False, na=False)]

    if df_filtrado.empty:
        st.warning("Ningún jugador cumple con todos los filtros actuales. Prueba bajar el mínimo de minutos o ampliar edad/posición.")
        st.stop()

    prom_vol = float(df_filtrado["g+a_total"].mean()) if "g+a_total" in df_filtrado.columns else 0.0
    prom_efi = float(df_filtrado["g+a_p90"].mean()) if "g+a_p90" in df_filtrado.columns else 0.0
    df_filtrado["perfil_scouting"] = df_filtrado.apply(
        lambda r: clasificar_perfil(r, prom_vol, prom_efi), axis=1
    )

    # ---------------------------------------------------------
    # 3. KPIs CLAVE DEL FILTRO ACTIVO
    # ---------------------------------------------------------
    top_vol = df_filtrado.sort_values(by="g+a_total", ascending=False).iloc[0]
    top_efi = df_filtrado.sort_values(by="g+a_p90", ascending=False).iloc[0]
    top_gol = df_filtrado.sort_values(by="gls_total", ascending=False).iloc[0]

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("👥 Jugadores en Muestra", f"{len(df_filtrado)}", f"Mín. {min_minutos} min")
    k2.metric("🔥 Líder en Volumen (G+A)", f"{top_vol['player']} ({int(top_vol['g+a_total'])})", top_vol.get("squad", ""))
    k3.metric("⚡ Mayor Eficiencia G+A/90", f"{top_efi['player']} ({top_efi['g+a_p90']:.2f})", top_efi.get("squad", ""))
    k4.metric("⚽ Máximo Goleador", f"{top_gol['player']} ({int(top_gol['gls_total'])})", top_gol.get("squad", ""))

    st.divider()

    # ---------------------------------------------------------
    # 4. PESTAÑAS ANALÍTICAS PARA SCOUTING Y ANÁLISIS
    # ---------------------------------------------------------
    tab_mapa, tab_comp, tab_notas = st.tabs(
        ["📈 Volumen vs. Eficiencia", "⚔️ Ranking y Comparador", "📝 Nota de Scouting"]
    )

    with tab_mapa:
        col_m1, col_m2 = st.columns([1.6, 1.4])
        with col_m1:
            metrica_efi_x = st.selectbox(
                "Métrica de Eficiencia (Eje X):",
                [c for c in ["g+a_p90", "gls_p90", "ast_p90", "g_pk_p90"] if c in df_filtrado.columns],
                key="p4_efi_x",
            )
        with col_m2:
            metrica_vol_y = st.selectbox(
                "Métrica de Volumen (Eje Y):",
                [c for c in ["g+a_total", "gls_total", "ast_total", "min"] if c in df_filtrado.columns],
                key="p4_vol_y",
            )

        med_x = float(df_filtrado[metrica_efi_x].median())
        med_y = float(df_filtrado[metrica_vol_y].median())

        fig_scat, ax_scat = plt.subplots(figsize=(9.5, 4.6), facecolor="#111827")
        ax_scat.set_facecolor("#111827")

        tamanos = (df_filtrado["min"].clip(lower=90) / 18).tolist()
        ax_scat.scatter(
            df_filtrado[metrica_efi_x],
            df_filtrado[metrica_vol_y],
            s=tamanos,
            color="#22c55e",
            alpha=0.78,
            edgecolors="#f8fafc",
            linewidth=0.9,
        )

        ax_scat.axvline(med_x, color="#94a3b8", linestyle="--", linewidth=1, alpha=0.75)
        ax_scat.axhline(med_y, color="#94a3b8", linestyle="--", linewidth=1, alpha=0.75)

        destacados = df_filtrado.sort_values(by=metrica_vol_y, ascending=False).head(8)
        for _, r_et in destacados.iterrows():
            nombre_corto = str(r_et.get("player", "")).split()[-1]
            ax_scat.annotate(
                nombre_corto,
                (r_et[metrica_efi_x], r_et[metrica_vol_y]),
                xytext=(5, 4),
                textcoords="offset points",
                color="#f8fafc",
                fontsize=8.5,
                fontweight="bold",
            )

        ax_scat.set_xlabel(f"Eficiencia: {metrica_efi_x} (línea punteada = mediana: {med_x:.2f})", color="#e2e8f0")
        ax_scat.set_ylabel(f"Volumen: {metrica_vol_y} (línea punteada = mediana: {med_y:.1f})", color="#e2e8f0")
        ax_scat.tick_params(colors="#cbd5e1")
        for spine in ax_scat.spines.values():
            spine.set_color("#334155")
        ax_scat.grid(True, linestyle=":", alpha=0.2, color="#94a3b8")
        st.pyplot(fig_scat, width="stretch")

    with tab_comp:
        cols_mostrar = [
            "player", "squad", "pos", "age", "min",
            "gls_total", "ast_total", "g+a_total",
            "gls_p90", "ast_p90", "g+a_p90", "perfil_scouting",
        ]
        cols_existentes = [c for c in cols_mostrar if c in df_filtrado.columns]
        orden_col = st.selectbox(
            "Ordenar tabla por:",
            [c for c in ["g+a_total", "g+a_p90", "gls_total", "gls_p90", "ast_total", "min", "age"] if c in df_filtrado.columns],
            key="p4_orden",
        )
        df_tabla = df_filtrado.sort_values(by=orden_col, ascending=False)[cols_existentes]
        st.dataframe(df_tabla, width="stretch", hide_index=True)

        st.markdown("#### Comparación Directa (2 a 4 jugadores)")
        jugadores_disp = df_filtrado["player"].dropna().unique().tolist()
        seleccion_comp = st.multiselect(
            "Elige jugadores para comparar:",
            jugadores_disp,
            default=jugadores_disp[: min(3, len(jugadores_disp))],
            max_selections=4,
            key="p4_comp_sel",
        )
        if seleccion_comp:
            cols_comp = [c for c in ["player", "squad", "pos", "age", "min", "g+a_total", "gls_total", "ast_total", "g+a_p90", "gls_p90", "ast_p90"] if c in df_filtrado.columns]
            df_comp = df_filtrado[df_filtrado["player"].isin(seleccion_comp)][cols_comp]
            st.dataframe(df_comp, width="stretch", hide_index=True)

    with tab_notas:
        st.markdown("#### Borrador de Mini Análisis desde el Filtro Actual")
        jugadores_nota = df_filtrado["player"].dropna().unique().tolist()
        jugador_foco = st.selectbox("Jugador principal del análisis:", jugadores_nota, key="p4_nota_jug")
        fila_jug = df_filtrado[df_filtrado["player"] == jugador_foco].iloc[0]

        c_n1, c_n2, c_n3 = st.columns(3)
        c_n1.metric("Edad / Minutos", f"{int(fila_jug.get('age', 0))} años", f"{int(fila_jug.get('min', 0))} min")
        c_n2.metric("Volumen G+A", f"{int(fila_jug.get('g+a_total', 0))}", f"{int(fila_jug.get('gls_total', 0))}G / {int(fila_jug.get('ast_total', 0))}A")
        c_n3.metric("Eficiencia G+A/90", f"{fila_jug.get('g+a_p90', 0):.2f}", fila_jug.get("perfil_scouting", ""))

        nota_texto = st.text_area(
            "Tu lectura de scouting (contexto, muestra, vigencia y rol):",
            height=130,
            placeholder=f"Ej. {jugador_foco} ({fila_jug.get('squad', '')}) acumula {int(fila_jug.get('min', 0))} min en {temporada_sel} con {fila_jug.get('g+a_p90', 0):.2f} G+A/90...",
            key="p4_nota_texto",
        )
        if nota_texto.strip():
            st.markdown("---")
            st.markdown("**Vista previa de tu análisis:**")
            st.write(nota_texto)

except Exception as e:
    st.error(f"No se pudo conectar o procesar los datos en este momento ({e}). Verifica `.env` y la conexión con Supabase.")