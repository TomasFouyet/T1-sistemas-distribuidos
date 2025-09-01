import socket
import threading
import json
import signal
import sys
import xmlrpc.client
from constantes import IP_TAREA, COMANDO_PYTHON


class Nodo(threading.Thread):
    def __init__(self, id_nodo: str, puertos: dict, puerto_rpc: int) -> None:
        super().__init__()
        self.daemon = True
        # Puede cambiar el nombre de los atributos, pero asegure que todo el código
        # funcione correctamente con los nuevos nombres.
        self.id = id_nodo
        self.main_socket = None
        self.puertos = puertos
        self.puerto_rpc = puerto_rpc

        # Completar con atributos adicionales si lo considera necesario

    def run(self):
        self.main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.main_socket.bind((IP_TAREA, self.puertos[self.id]))
        self.main_socket.listen()
        print(f"Nodo {self.id} escuchando en puerto {self.puertos[self.id]}...")

        # Completar este método para aceptar conexiones entrantes


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print(f"Uso: {COMANDO_PYTHON} servidor.py [A|B|C] [PORT_A] [PORT_B] [PORT_C] [PORT_RPC]")
        sys.exit(1)

    id_nodo = sys.argv[1]
    puertos = {
        "A": int(sys.argv[2]),
        "B": int(sys.argv[3]),
        "C": int(sys.argv[4]),
    }
    puerto_rpc = int(sys.argv[5])

    nodo = Nodo(id_nodo, puertos, puerto_rpc)

    def cleanup(signum, frame):
        print("Cerrando servidor...")
        nodo.main_socket.close()

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    nodo.start()
    nodo.join()
