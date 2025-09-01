import subprocess
import time
import xmlrpc.client
import json
import os
import socket
from constantes import IP_TAREA, COMANDO_PYTHON, TIEMPO_ENTRE_MENSAJES


def buscar_puertos_disponibles(cantidad=1):
    puertos = []
    sockets = []
    try:
        for _ in range(cantidad):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("", 0))  # El sistema elige un puerto libre
            puerto = s.getsockname()[1]
            puertos.append(puerto)
            sockets.append(s)  # Mantener abierto para reservar el puerto temporalmente
    finally:
        for s in sockets:
            s.close()

    return puertos


if __name__ == "__main__":
    files = sorted([f for f in os.listdir("tests") if f.endswith(".json") and f.startswith("rpc")])
    for file in files:
        PUERTO = str(buscar_puertos_disponibles(1)[0])
        print(f"[Puerto={PUERTO}] Ejecutando pruebas desde el archivo: {file}")
        with open(os.path.join("tests", file), "r", encoding="utf-8") as f:
            datos = json.load(f)

        with open("base_de_datos.json", "w", encoding="utf-8") as f:
            json.dump(datos["initial_database"], f, indent=4, ensure_ascii=False)

        # Iniciar el servidor RPC en segundo plano y esperar 1 segundo para que se inicie
        servidor = subprocess.Popen([COMANDO_PYTHON, "rpc.py", PUERTO])
        time.sleep(1)

        total = len(datos["queries"])
        logrados = 0

        try:
            cliente_rpc = xmlrpc.client.ServerProxy(f"http://{IP_TAREA}:{PUERTO}", allow_none=True)

            for consulta in datos["queries"]:
                print(f"\tConsulta: {consulta['consulta']}")
                tipo = consulta["consulta"][0]
                parametros = consulta["consulta"][1:]
                if tipo == "calificar":
                    resultado = cliente_rpc.calificar(*parametros)
                elif tipo == "obtener":
                    resultado = cliente_rpc.obtener(*parametros)
                elif tipo == "puntaje_promedio":
                    resultado = cliente_rpc.puntaje_promedio(*parametros)
                elif tipo == "animes":
                    resultado = cliente_rpc.animes()
                print(f"\tEsperado: {consulta['esperado']} - Obtenido: {resultado}\n")

                if resultado == consulta["esperado"]:
                    logrados += 1

                time.sleep(TIEMPO_ENTRE_MENSAJES)
        except ConnectionRefusedError:
            print("\tError: No se pudo conectar al servidor RPC. Test abortado.")

        finally:
            porcentaje = f"{logrados / total * 100:.2f}"
            print(f"\n\tPruebas completadas: {logrados}/{total} exitosas = {porcentaje}%\n")
            with open("base_de_datos.json", "w", encoding="utf-8") as f:
                json.dump([], f, indent=4, ensure_ascii=False)

            # Finalizar proceso para liberar el puerto
            servidor.terminate()
            servidor.wait()
            time.sleep(0.5)

    base_original_tarea = [
        {"usuario": "Hernán V", "anime": "Lycoris Recoil", "puntaje": 10},
        {"usuario": "Hernán V", "anime": "Gintama", "puntaje": 9}
    ]
    with open("base_de_datos.json", "w", encoding="utf-8") as f:
        json.dump(base_original_tarea, f, indent=4, ensure_ascii=False)
