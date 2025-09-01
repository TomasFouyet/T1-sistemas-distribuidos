import socket
import json
import subprocess
import time
import os
from constantes import IP_TAREA, COMANDO_PYTHON, TIEMPO_ENTRE_MENSAJES, TIEMPO_CONSOLIDAR


def buscar_puertos_disponibles(cantidad=4):
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


def obtener_socket_nodos(puertos):
    sockets = {}
    for id_nodo, puerto in puertos.items():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((IP_TAREA, puerto))
            sockets[id_nodo] = s
        except Exception as e:
            text = f"\tError al crear socket para {id_nodo}: {e}"
            text += (f"Puerto: {puerto}")
            raise ValueError(text)
    return sockets


def enviar_mensaje(sockets_puertos, nodo, mensaje):
    socket_nodo = sockets_puertos[nodo]
    datos = json.dumps(mensaje).encode("UTF-8")
    tam = len(datos).to_bytes(4, byteorder="big")
    socket_nodo.sendall(tam + datos)


def cargar_datos():
    try:
        with open("base_de_datos.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def levantar_procesos(puertos, puerto_rpc):
    procesos = []
    comando = [COMANDO_PYTHON, "rpc.py", str(puerto_rpc)]
    procesos.append(subprocess.Popen(comando))
    for puerto in puertos:
        comando = [
            COMANDO_PYTHON,
            "servidor.py",
            puerto,
            str(puertos["A"]),
            str(puertos["B"]),
            str(puertos["C"]),
            str(puerto_rpc),
        ]
        proceso = subprocess.Popen(comando)
        procesos.append(proceso)

    # Esperar un momento para que los procesos se levanten
    time.sleep(1)
    return procesos


def terminar_procesos(procesos):
    for p in procesos:
        try:
            p.terminate()
            p.wait()
        except Exception as e:
            print(f"Error al terminar el proceso: {e}")
            continue
    time.sleep(0.5)


def obtener_puertos_random():
    puertos_random = buscar_puertos_disponibles(4)
    puertos = {
        "A": puertos_random[0],
        "B": puertos_random[1],
        "C": puertos_random[2],
    }
    puerto_rpc = puertos_random[3]
    time.sleep(1)  # Esperar un poco para evitar conflictos de conexión
    return puertos, puerto_rpc


def procesar_datos(datos):
    diccionario_puntajes = {}
    for dato in datos:
        diccionario_puntajes[(dato["usuario"], dato["anime"])] = dato["puntaje"]
    return diccionario_puntajes


if __name__ == "__main__":
    files = sorted([f for f in os.listdir("tests") if f.endswith(".json") and f.startswith("tcp")])

    for file in files:
        print(f"Ejecutando pruebas desde el archivo: {file}")
        with open(os.path.join("tests", file), "r", encoding="utf-8") as f:
            datos = json.load(f)

        with open("base_de_datos.json", "w", encoding="utf-8") as f:
            json.dump(datos["initial_database"], f)

        puertos, puerto_rpc = obtener_puertos_random()
        print(f"\t{datos['title']}")

        try:
            procesos = levantar_procesos(puertos, puerto_rpc)
            sockets_puertos = obtener_socket_nodos(puertos)
            total = len(datos["consultas"])
            for i, (nodo, mensaje) in enumerate(datos["consultas"]):
                print(f"\r\tConsulta {i + 1}/{total}", end="")
                enviar_mensaje(sockets_puertos, nodo, mensaje)
                if mensaje["tipo"] != "CONSOLIDAR":
                    time.sleep(TIEMPO_ENTRE_MENSAJES)
                else:
                    time.sleep(TIEMPO_CONSOLIDAR)
            print("")

        except Exception as e:
            print(f"\tError durante el ejemplo: {e}")
        finally:
            terminar_procesos(procesos)

            datos_finales_ejecucion = procesar_datos(cargar_datos())
            datos_finales_esperados = procesar_datos(datos["final_database"])

            total = len(datos_finales_esperados)
            logrados = 0
            for key in datos_finales_esperados:
                # key es una tupla (usuario, anime)

                # Si no existe el key en los datos finales de ejecución, no se cuenta como logrado
                if key not in datos_finales_ejecucion:
                    continue

                # Si el puntaje es igual, se cuenta como logrado
                if datos_finales_ejecucion[key] == datos_finales_esperados[key]:
                    logrados += 1

            porcentaje = f"{logrados / total * 100:.2f}"
            print(f"\n\tPruebas completadas: {logrados}/{total} exitosas = {porcentaje}%\n")

    base_original_tarea = [
        {"usuario": "Hernán V", "anime": "Lycoris Recoil", "puntaje": 10},
        {"usuario": "Hernán V", "anime": "Gintama", "puntaje": 9}
    ]
    with open("base_de_datos.json", "w", encoding="utf-8") as f:
        json.dump(base_original_tarea, f, indent=4, ensure_ascii=False)
