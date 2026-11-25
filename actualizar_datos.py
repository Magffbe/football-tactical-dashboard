import ScraperFC as sfc
import pandas as pd
from sqlalchemy import text
from database.connection import engine

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

    # Eliminar filas repetidas que FBref inserta como encabezado intermedio
    if "Player" in df.columns:
        df = df[df["Player"] != "Player"].copy()

    # Descartar columnas residuales tipo 'Unnamed: 25'
    df = df.loc[:, ~df.columns.str.contains("^Unnamed", case=False, na=False)]

    # Misma normalización usada en migrate_csv.py
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("%", "pct", regex=False)
        .str.replace("/", "_per_", regex=False)
    )

    # Eliminar columnas duplicadas si llegaran a existir tras limpiar nombres
    df = df.loc[:, ~df.columns.duplicated()]
    return df

def preparar_tipos(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte columnas clave a numéricas para mantener consistencia en PostgreSQL."""
    # FBref entrega 'age' como 'años-días' (ej. '19-133'); tomamos solo los años
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


def actualizar_supabase():
    print("Iniciando actualizar_supabase...")
    try:
        scraper = sfc.FBref()
    except Exception as e:
        print(f"Error al crear sfc.FBref(): {e}")
        return

    for temp in temporadas:
        lista_dfs = []
        print(f"\n================ TEMPORADA {temp} ================")

        for liga in ligas:
            try:
                print(f"⏳ Descargando {liga} ({temp}) desde FBref...")
                datos_dict = scraper.scrape_stats(temp, liga, "standard")
                df = datos_dict["player"].copy()

                df = limpiar_columnas_sql(df)
                df["liga"] = liga
                df["temporada"] = temp
                df = preparar_tipos(df)

                lista_dfs.append(df)
                print(f"✅ {liga} lista ({len(df)} filas)")
            except Exception as e:
                print(f"⚠️ Error en {liga} ({temp}): {e}")

        if lista_dfs:
            df_temp = pd.concat(lista_dfs, ignore_index=True)

            # Alinear columnas con las que ya existen en 'estadisticas_fbref' en Supabase
            with engine.connect() as conn:
                cols_db = pd.read_sql(
                    text("SELECT * FROM estadisticas_fbref LIMIT 1"), conn
                ).columns.tolist()

            # Agregar cualquier columna faltante y conservar el orden de la tabla
            for c in cols_db:
                if c not in df_temp.columns:
                    df_temp[c] = None
            df_temp = df_temp[cols_db]

            print(f"🔄 Actualizando temporada '{temp}' en Supabase ({len(df_temp)} filas)...")
            df_limpio_db = df_temp.astype(object).where(pd.notna(df_temp), None)
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
                    text("DELETE FROM estadisticas_fbref WHERE temporada = :temp"),
                    {"temp": temp},
                )
                tamano_lote = 50
                for i in range(0, len(registros), tamano_lote):
                    lote = registros[i : i + tamano_lote]
                    conn.execute(
                        text(f"INSERT INTO estadisticas_fbref ({cols_sql}) VALUES ({vals_sql})"),
                        lote,
                    )
                conn.commit()

            print(f"🎉 ¡Temporada '{temp}' cargada/actualizada en Supabase con éxito!")
        else:
            print(f"❌ No se pudieron obtener datos para la temporada {temp}.")


if __name__ == "__main__":
    actualizar_supabase()