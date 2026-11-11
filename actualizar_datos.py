import ScraperFC as sfc
import pandas as pd

ligas = [
    "Spain La Liga",
    "England Premier League",
    "UEFA Champions League",
    "Italy Serie A",
    "Germany Bundesliga",
    "France Ligue 1"
]
temporadas = ["2024-2025"]

scraper = sfc.FBref()
lista_dfs = []

for temp in temporadas:
    for liga in ligas:
        try:
            print(f"⏳ Descargando {liga} ({temp})...")
            datos_dict = scraper.scrape_stats(temp, liga, "standard")
            df = datos_dict['player'].copy()

            nuevas_cols = []
            for col in df.columns:
                if isinstance(col, tuple):
                    n0, n1 = col[0], col[1]
                    if 'Per 90' in n0:
                        nuevas_cols.append(f"{n1}_P90")
                    elif 'Performance' in n0:
                        nuevas_cols.append(f"{n1}_Total")
                    else:
                        nuevas_cols.append(n1)
                else:
                    nuevas_cols.append(col)

            df.columns = nuevas_cols
            df = df[df['Player'] != 'Player'].copy()
            df['Liga'] = liga
            df['Temporada'] = temp
            lista_dfs.append(df)
            print(f"✅ {liga} lista ({len(df)} jugadores)")
        except Exception as e:
            print(f"⚠️ Error en {liga}: {e}")

if lista_dfs:
    df_final = pd.concat(lista_dfs, ignore_index=True)
    df_final.to_csv("datos_fbref.csv", index=False)
    print("\n🎉 ¡Archivo 'datos_fbref.csv' generado con éxito!")