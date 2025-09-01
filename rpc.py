from xmlrpc.server import SimpleXMLRPCServer
from sys import argv
import json
from constantes import IP_TAREA, COMANDO_PYTHON


class GestorCalificaciones:
    def __init__(self, archivo_db: str) -> None:
        pass

    def calificar(self, usuario: str, anime: str, puntaje: int) -> int:
        pass

    def obtener(self, usuario: str, anime: str) -> int:
        pass

    def puntaje_promedio(self, anime: str) -> float:
        pass

    def animes(self) -> dict:
        pass


if __name__ == "__main__":
    if len(argv) != 2 or not argv[1].isdigit():
        print(f"Uso: {COMANDO_PYTHON} rpc.py <XXXX> donde <XXXX> es el puerto a utilizar")
        exit(1)

    PUERTO = int(argv[1])
    DB_FILE = "base_de_datos.json"
    gestor = GestorCalificaciones(DB_FILE)

    # Completar para levantar el RPC en el puerto indicado en PUERTO