# create_files.py - Crea todos los archivos necesarios
import os

files = {
    'safety.py': '''# Ver seccion 14 del compendio
# Copiar codigo completo de safety.py
print("Archivo safety.py creado - REEMPLAZAR con codigo del compendio")
''',
    'mt5_utils.py': '''# Ver seccion 13 del compendio
# Copiar codigo completo de mt5_utils.py
print("Archivo mt5_utils.py creado - REEMPLAZAR con codigo del compendio")
''',
    'post_mortem.py': '''# Ver seccion 15 del compendio
# Copiar codigo completo de post_mortem.py
print("Archivo post_mortem.py creado - REEMPLAZAR con codigo del compendio")
''',
    'alerts.py': '''# Ver seccion 16 del compendio
# Copiar codigo completo de alerts.py
print("Archivo alerts.py creado - REEMPLAZAR con codigo del compendio")
''',
    'donchian_strategy.py': '''# Estrategia Donchian Breakout
# Copiar codigo completo de donchian_strategy.py
print("Archivo donchian_strategy.py creado - REEMPLAZAR con codigo del compendio")
''',
    'webhook_receiver.py': '''# Webhook receiver for trading signals
# Copiar codigo completo de webhook_receiver.py
print("Archivo webhook_receiver.py creado - REEMPLAZAR con codigo del compendio")
''',
    'export_mt5_data.py': '''# Export historical data from MT5
# Copiar codigo completo de export_mt5_data.py
print("Archivo export_mt5_data.py creado - REEMPLAZAR con codigo del compendio")
''',
    'backtest_apex_vectorbt.py': '''# Backtest using vectorbt
# Copiar codigo completo de backtest_apex_vectorbt.py
print("Archivo backtest_apex_vectorbt.py creado - REEMPLAZAR con codigo del compendio")
'''
}

for filename, content in files.items():
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Creado {filename}")
    else:
        print(f"⚠️  {filename} ya existe")

print("\n⚠️  IMPORTANTE: Reemplazar el contenido de cada archivo con el codigo completo del compendio")