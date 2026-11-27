import multiprocessing as mp
import time
import pandas as pd
from sqlalchemy import text
from database.connection import engine

TIMEOUT_POR_LIGA = 240  # segundos máximos por liga en ejecución local

ligas = [
    "Spain La Liga",
    "England Premier League",
    "UEFA Champions League",
    "Italy Serie A",
    "Germany Bundesliga",
    "France Ligue 1",
]

# Temporada objetivo a descargar y actualizar en Supabase
temporadas = ["2026-2027"]


def limpiar_columnas_sql(df: pd.DataFrame) -> pd.DataFrame:
    """Aplana columnas de FBref, quita columnas residuales y estandariza a snake_case."""
    nuevas_cols = []
    for col in df.columns:
        if isinstance(col, tuple):
            n0, n1 = col[0], col[1]
            if "Per 90" in n0:
                nuevas_cols.append(f"{n1}_P90")
            elif "Performance" in n0:
                nuevas_cols.append(f"{n1}_Total")
            else:
                nuevas_cols.append(n1)
        else:
            nuevas_cols.append(col)

    df.columns = nuevas_cols

    if "Player" in df.columns:
        df = df[df["Player"] != "Player"].copy()

    df = df.loc[:, ~df.columns.str.contains("^Unnamed", case=False, na=False)]

    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("%", "pct", regex=False)
        .str.replace("/", "_per_", regex=False)
    )

    df = df.loc[:, ~df.columns.duplicated()]
    return df


def preparar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas clave a numéricas para mantener consistencia en PostgreSQL."""
    if "age" in df.columns:
        df["age"] = df["age"].astype(str).str.split("-").str[0]

    cols_numericas = [
        "age", "born", "mp", "starts", "min", "90s",
        "gls_total", "ast_total", "g+a_total",
        "g_pk_total", "pk_total", "pkatt_total",
        "crdy_total", "crdr_total",
        "gls_p90", "ast_p90", "g+a_p90", "g_pk_p90", "g+a_pk_p90",
        "matches",
    ]
    for col in cols_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _worker_descargar_liga(temp: str, liga: str, queue: mp.Queue):
    """Ejecuta el scraping de una liga en un proceso aislado."""
    try:
        import ScraperFC as sfc

        scraper = sfc.FBref()
        datos_dict = scraper.scrape_stats(temp, liga, "standard")
        df_raw = datos_dict["player"].copy()
        queue.put(("ok", df_raw))
    except Exception as e:
        queue.put(("error", str(e)))


def descargar_liga_con_timeout(temp: str, liga: str, timeout_seg: int) -> pd.DataFrame:
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    proc = ctx.Process(target=_worker_descargar_liga, args=(temp, liga, queue))

    proc.start()
    proc.join(timeout=timeout_seg)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join()
        queue.close()
        queue.join_thread()
        raise TimeoutError(f"Timeout ({timeout_seg}s) en {liga} ({temp})")

    resultado = None
    if not queue.empty():
        resultado = queue.get()

    queue.close()
    queue.join_thread()
    proc.join()

    if resultado is None:
        raise RuntimeError(f"El proceso terminó sin devolver datos para {liga} ({temp})")

    estado, payload = resultado
    if estado == "ok":
        return payload
    raise RuntimeError(payload)


def guardar_liga_en_supabase(df_liga: pd.DataFrame, temp: str, liga: str, cols_db: list[str]):
    """Reemplaza únicamente los registros de esa temporada y esa liga."""
    df_prep = df_liga.copy()
    for c in cols_db:
        if c not in df_prep.columns:
            df_prep[c] = None
    df_prep = df_prep[cols_db]

    df_limpio_db = df_prep.astype(object).where(pd.notna(df_prep), None)
    filas_df = df_limpio_db.to_dict(orient="records")

    cols_sql = ", ".join([f'"{c}"' for c in cols_db])
    param_names = [f"p_{idx}" for idx in range(len(cols_db))]
    vals_sql = ", ".join([f":{p}" for p in param_names])

    registros = [
        {param_names[idx]: fila.get(c) for idx, c in enumerate(cols_db)}
        for fila in filas_df
    ]

    with engine.connect() as conn:
        conn.execute(
            text("DELETE FROM estadisticas_fbref WHERE temporada = :temp AND liga = :liga"),
            {"temp": temp, "liga": liga},
        )
        tamano_lote = 50
        for i in range(0, len(registros), tamano_lote):
            lote = registros[i : i + tamano_lote]
            conn.execute(
                text(f"INSERT INTO estadisticas_fbref ({cols_sql}) VALUES ({vals_sql})"),
                lote,
            )
        conn.commit()


def actualizar_supabase():
    print("Iniciando actualizar_supabase...")

    with engine.connect() as conn:
        cols_db = pd.read_sql(
            text("SELECT * FROM estadisticas_fbref LIMIT 1"), conn
        ).columns.tolist()

    for temp in temporadas:
        actualizadas = 0
        print(f"\n================ TEMPORADA {temp} ================")

        for idx, liga in enumerate(ligas):
            try:
                print(f"⏳ Descargando {liga} ({temp}) desde FBref...")
                df_raw = descargar_liga_con_timeout(temp, liga, TIMEOUT_POR_LIGA)

                df = limpiar_columnas_sql(df_raw)
                df["liga"] = liga
                df["temporada"] = temp
                df = preparar_tipos(df)

                if df.empty:
                    print(f"⚠️ {liga} ({temp}) devolvió 0 filas; se omite guardado.")
                else:
                    print(f"🔄 Actualizando {liga} ({temp}) en Supabase ({len(df)} filas)...")
                    guardar_liga_en_supabase(df, temp, liga, cols_db)
                    actualizadas += 1
                    print(f"✅ {liga} actualizada con éxito.")
            except TimeoutError as e:
                print(f"⏱️ {e}; se omite por ahora.")
            except Exception as e:
                print(f"⚠️ Error en {liga} ({temp}): {e}")

            if idx < len(ligas) - 1:
                time.sleep(5)

        if actualizadas > 0:
            print(f"\n🎉 Temporada '{temp}': {actualizadas}/{len(ligas)} ligas actualizadas en Supabase.")
        else:
            print(f"\n❌ No se pudo actualizar ninguna liga para la temporada {temp}.")


if __name__ == "__main__":
    actualizar_supabase()