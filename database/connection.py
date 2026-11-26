import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Carga las variables secretas desde el archivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("No se encontró DATABASE_URL en el archivo .env")

# Crea el motor de conexión a PostgreSQL (Supabase)
engine = create_engine(DATABASE_URL)

def test_connection():
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version();"))
            version = result.scalar()
            print("✅ ¡Conexión exitosa a Supabase PostgreSQL!")
            print(f"Versión del servidor: {version}")
    except Exception as e:
        print("❌ Error al conectar con la base de datos:")
        print(e)

if __name__ == "__main__":
    test_connection()





    