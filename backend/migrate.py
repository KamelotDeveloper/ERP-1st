"""
Script de migración para agregar columnas faltantes a la base de datos SQLite.
Ejecutar: python migrate.py
"""

import sqlite3
import os

def run_migration():
    db_path = os.path.join(os.path.dirname(__file__), "utils", "carpinteria.db")
    
    if not os.path.exists(db_path):
        print(f"Error: No se encontró la base de datos en {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("=== Iniciando migración ===\n")
    
    # Migraciones para tabla products
    print("1. Verificando tabla 'products'...")
    try:
        # Verificar si la columna stock_minimo existe
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'stock_minimo' not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN stock_minimo INTEGER DEFAULT 0")
            print("   [OK] Agregada columna 'stock_minimo' a products")
        else:
            print("   [-] La columna 'stock_minimo' ya existe en products")
    except Exception as e:
        print(f"   [ERROR] Error en products: {e}")
    
    # Migraciones para tabla materials
    print("\n2. Verificando tabla 'materials'...")
    try:
        # Verificar si la columna stock_minimo existe
        cursor.execute("PRAGMA table_info(materials)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'stock_minimo' not in columns:
            cursor.execute("ALTER TABLE materials ADD COLUMN stock_minimo INTEGER DEFAULT 0")
            print("   [OK] Agregada columna 'stock_minimo' a materials")
        else:
            print("   [-] La columna 'stock_minimo' ya existe en materials")
    except Exception as e:
        print(f"   [ERROR] Error en materials: {e}")
    
    # Migración para tabla license_trials
    print("\n3. Verificando tabla 'license_trials'...")
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='license_trials'")
        if cursor.fetchone() is None:
            cursor.execute("""
                CREATE TABLE license_trials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL UNIQUE,
                    fecha_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
                    activo BOOLEAN DEFAULT 1
                )
            """)
            print("   [OK] Tabla 'license_trials' creada")
        else:
            print("   [-] La tabla 'license_trials' ya existe")
    except Exception as e:
        print(f"   [ERROR] Error en license_trials: {e}")
    
    # Guardar cambios
    conn.commit()
    conn.close()
    
    print("\n=== Migración completada ===")

if __name__ == "__main__":
    run_migration()
