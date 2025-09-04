from xmlrpc.server import SimpleXMLRPCServer
from sys import argv
import json
from constantes import IP_TAREA, COMANDO_PYTHON, DB_FILE

class GestorCalificaciones:
    def __init__(self, archivo_db: str) -> None:
        self.archivo_db = archivo_db
        try:
            with open(self.archivo_db, 'r', encoding="utf-8") as f:
                json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self._guardar([])
                       
    def _cargar(self):
        try:
            with open(self.archivo_db, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return []  

    def _guardar(self, data):
        with open(self.archivo_db, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
    def calificar(self, usuario: str, anime: str, puntaje: int) -> int:
        data = self._cargar()
        encontrado = False
        for registro in data:
            if registro["usuario"] == usuario and registro["anime"] == anime:
                registro["puntaje"] = puntaje
                encontrado = True
                break
        if not encontrado:
            data.append({"usuario": usuario, "anime": anime, "puntaje": puntaje})
        self._guardar(data)
        return int(puntaje)

    def obtener(self, usuario: str, anime: str) -> int:
        data = self._cargar()
        for registro in data:
            if registro["usuario"] == usuario and registro["anime"] == anime:
                return int(registro["puntaje"])
        return -1

    def puntaje_promedio(self, anime: str) -> float:
        data = self._cargar()
        puntajes = [row["puntaje"] for row in data if row["anime"] == anime]
        if not puntajes:
            return -1
        return round(sum(puntajes) / len(puntajes), 2)

    def animes(self) -> dict:
        data = self._cargar()
        conteos = {}
        for registro in data:
            nombre = registro["anime"]
            conteos[nombre] = conteos.get(nombre, 0) + 1
        return conteos


if __name__ == "__main__":
    if len(argv) != 2 or not argv[1].isdigit():
        print(f"Uso: {COMANDO_PYTHON} rpc.py <XXXX> donde <XXXX> es el puerto a utilizar")
        exit(1)
        
    PUERTO = int(argv[1])
    gestor = GestorCalificaciones(DB_FILE)
    
    # Esto fue generado con Copilot
    with SimpleXMLRPCServer((IP_TAREA, PUERTO), allow_none=True) as server:
        server.register_introspection_functions()
        server.register_instance(gestor)
        print(f"Servidor RPC en http://{IP_TAREA}:{PUERTO}")
        server.serve_forever()
