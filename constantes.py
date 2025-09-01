# Puedes (y debes) cambiar el comando de "python3" al que corresponda a tu sistema
# operativo. Por ejemplo, "python", "py", "python3.12".
COMANDO_PYTHON = "python3"

# Se recomienda FUERTEMENTE dejar IP_TAREA como "127.0.0.1"
# porque como "localhost" es un poco más lenta la comunicación
# para los que tienen sistema Windows
# Link de interés: https://superuser.com/a/595324
IP_TAREA = "127.0.0.1"

# Tiempo de espera entre cada mensaje. 
# Para la corrección final será de 0.2 segundos como tope máximo.
TIEMPO_ENTRE_MENSAJES = 0.2

# Tiempo de espera posterior a realizar un consolidar
# Para la corrección final será de 5 segundos como tope máximo.
# Pero aquí se dejó más bajo para facilitar los tests públicos.
TIEMPO_CONSOLIDAR = 0.2
