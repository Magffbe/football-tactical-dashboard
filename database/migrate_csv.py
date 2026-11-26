import pandas as pd
from connection import engine

def migrar_datos():
    print("📂 Leyendo datos_fbref.csv...")
    df = pd.read_csv("datos_fbref.csv")

    # Descartamos columnas residuales como 'Unnamed: 25'
    df = df.loc[:, ~df.columns.str.contains("^Unnamed")]
    
    # Mostramos información básica antes de subir
    print(f"📊 Filas encontradas: {len(df)}")
    print(f"📋 Columnas originales: {list(df.columns)}")

    
    # Limpiamos los nombres de las columnas para PostgreSQL (minúsculas y sin espacios)
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("-", "_")
        .str.replace("%", "pct")
        .str.replace("/", "_per_")
    )
    
    print(f"✨ Columnas limpias para SQL: {list(df.columns)}")
    print("🚀 Subiendo datos a Supabase...")
    
    # Subimos el DataFrame a una tabla llamada 'estadisticas_fbref'
    df.to_sql(
        name="estadisticas_fbref",
        con=engine,
        if_exists="replace",  # Si ya existe la tabla, la reemplaza con los datos nuevos
        index=False           # No sube el índice numérico de pandas como columna extra
    )
    
    print("✅ ¡Migración completada! La tabla 'estadisticas_fbref' ya está en Supabase.")

if __name__ == "__main__":
    migrar_datos()