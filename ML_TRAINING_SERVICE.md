# Servicio de Entrenamiento Automático ML

## Descripción
Este servicio ejecuta el entrenamiento automático del modelo ML de manera continua en segundo plano.

## Instalación como Servicio de Windows

### 1. Crear archivo de servicio (.bat)

```batch
@echo off
cd /d "C:\Users\edgar\roboquant\roboquant"
uv run python auto_ml_trainer.py
pause
```

### 2. Usar NSSM (Non-Sucking Service Manager)

1. Descargar NSSM: https://nssm.cc/download
2. Extraer nssm.exe a una carpeta del PATH
3. Abrir CMD como administrador:

```cmd
nssm install RoboQuantMLTrainer
nssm set RoboQuantMLTrainer Application "C:\Users\edgar\roboquant\roboquant\run_ml_trainer.bat"
nssm set RoboQuantMLTrainer AppDirectory "C:\Users\edgar\roboquant\roboquant"
nssm set RoboQuantMLTrainer DisplayName "RoboQuant ML Trainer"
nssm set RoboQuantMLTrainer Description "Entrenamiento automático del modelo ML para RoboQuant"
nssm set RoboQuantMLTrainer Start SERVICE_AUTO_START
```

### 3. Comandos del servicio

```cmd
# Iniciar servicio
net start RoboQuantMLTrainer

# Detener servicio  
net stop RoboQuantMLTrainer

# Eliminar servicio
nssm remove RoboQuantMLTrainer confirm
```

## Alternativas

### Opción 1: Task Scheduler de Windows
- Abre Task Scheduler
- Crea tarea básica
- Programa ejecución periódica (ej: cada 7 días)
- Acción: Ejecutar `uv run python train_ml_validator.py --days 60`

### Opción 2: Cron en Linux/Mac
```bash
# Entrenar cada domingo a las 2 AM
0 2 * * 0 cd /ruta/a/roboquant && uv run python train_ml_validator.py --days 60
```

## Monitorización

Los logs se guardan en:
- `logs/ml_training.log` - Logs detallados
- `logs/training_metrics.csv` - Métricas históricas

## Configuración

Editar `auto_ml_trainer.py` para cambiar:
- `training_interval_days`: Intervalo de entrenamiento
- `data_days`: Cantidad de datos históricos
- Símbolos de trading