import os
from dotenv import load_dotenv
# Try to import metatrader5, fallback to MetaTrader5 if needed
try:
    import metatrader5 as mt5
except ImportError:
    import MetaTrader5 as mt5  # type: ignore

load_dotenv()

# Mostrar lo que está cargando (sin mostrar la contraseña completa)
login = os.getenv('MT5_LOGIN')
password = os.getenv('MT5_PASSWORD')
server = os.getenv('MT5_SERVER')

print("=== Verificando credenciales ===")
print(f"Login: '{login}'")
print(f"Password length: {len(password) if password else 0} caracteres")
print(f"Server: '{server}'")
print()

# Verificar espacios
if login and (login != login.strip()):
    print("⚠️ ADVERTENCIA: Login tiene espacios!")
if password and (password != password.strip()):
    print("⚠️ ADVERTENCIA: Password tiene espacios!")
if server and (server != server.strip()):
    print("⚠️ ADVERTENCIA: Server tiene espacios!")
print()

# Inicializar MT5
print("Intentando inicializar MT5...")
if not mt5.initialize():  # type: ignore
    print("❌ Error al inicializar MT5")
    print("Error code:", mt5.last_error())  # type: ignore
    quit()

print("✓ MT5 inicializado correctamente")
print()

# Intentar login
print("Intentando login...")
if login and password and server:
    try:
        login_int = int(login)
        authorized = mt5.login(  # type: ignore
            login=login_int,
            password=password,
            server=server
        )
    except ValueError as e:
        print(f"❌ Error de formato de login: {e}")
        mt5.shutdown()  # type: ignore
        quit()
else:
    print("❌ Credenciales incompletas")
    mt5.shutdown()  # type: ignore
    quit()

if authorized:
    print("✓ ¡Login exitoso!")
    account_info = mt5.account_info()  # type: ignore
    if account_info:
        print(f"Balance: {account_info.balance}")
        print(f"Cuenta: {account_info.login}")
else:
    print("❌ Error de login")
    error = mt5.last_error()  # type: ignore
    print(f"Código de error: {error}")

mt5.shutdown()  # type: ignore