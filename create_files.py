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