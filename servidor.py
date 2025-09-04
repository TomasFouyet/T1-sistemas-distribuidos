import socket
import threading
import json
import signal
import sys
import xmlrpc.client
from constantes import IP_TAREA, COMANDO_PYTHON

def _recv_exact(conn, n):
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def recv_json(conn):
    header = _recv_exact(conn, 4)
    if not header:
        return None
    length = int.from_bytes(header, "big")
    payload = _recv_exact(conn, length)
    if not payload:
        return None
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return None


def send_json(conn, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    header = len(data).to_bytes(4, "big")
    conn.sendall(header + data)

class Nodo(threading.Thread):
    def __init__(self, id_nodo: str, puertos: dict, puerto_rpc: int) -> None:
        super().__init__()
        self.daemon = True
        self.id = id_nodo
        self.main_socket = None
        self.puertos = puertos
        self.puerto_rpc = puerto_rpc
        self.activo = True
        self.lamport = 0
        self.ratings = {}
        self.lock = threading.RLock()
        self._stopped = threading.Event()

    def _set_rating(self, usuario, anime, puntaje, ts):
        self.ratings[(usuario, anime)] = {"puntaje": int(puntaje), "ts": int(ts)}

    def _merge_rating(self, usuario, anime, puntaje, ts):
        key = (usuario, anime)
        nuevo = {"puntaje": int(puntaje), "ts": int(ts)}
        actual = self.ratings.get(key)
        if actual is None:
            self.ratings[key] = nuevo
            return True
        if nuevo["ts"] > actual["ts"]:
            self.ratings[key] = nuevo
            return True
        if nuevo["ts"] == actual["ts"] and nuevo["puntaje"] > actual["puntaje"]:
            self.ratings[key] = nuevo
            return True
        return False

    def _serialize_store(self):
        return [
            {"usuario": u, "anime": a, "puntaje": v["puntaje"], "ts": v["ts"]}
            for (u, a), v in self.ratings.items()
        ]

    def _install_store(self, data):
        self.ratings.clear()
        for item in data:
            self._set_rating(item["usuario"], item["anime"], item["puntaje"], item["ts"])

    def _tick(self, value=None):
        if value is None:
            self.lamport += 1
        else:
            self.lamport = max(self.lamport, int(value)) + 1
        return self.lamport

    def _synchronize_clock(self):
        max_clock = self.lamport
        for pid, port in self._peers():
            try:
                req = {"tipo": "CLOCK_REQ"}
                res = self._send_one(port, req, expect_reply=True, timeout=0.3)
                if res and res.get("tipo") == "CLOCK_RES":
                    max_clock = max(max_clock, int(res.get("lamport", 0)))
            except Exception:
                pass
        self.lamport = max_clock + 1

    def _peers(self):
        return [(pid, port) for pid, port in self.puertos.items() if pid != self.id]

    def _send_one(self, port, payload, expect_reply=False, timeout=0.6):
        try:
            with socket.create_connection((IP_TAREA, port), timeout=timeout) as s:
                s.settimeout(timeout)
                send_json(s, payload)
                if expect_reply:
                    return recv_json(s)
                return None
        except Exception:
            return None

    def _handle_user_msg(self, msg):
        tipo = msg.get("tipo")
        if tipo == "SCORE":
            usuario = msg.get("usuario")
            anime = msg.get("anime")
            puntaje = msg.get("puntaje")
            if not self.activo:
                return
            with self.lock:
                ts = self._tick()
                self._set_rating(usuario, anime, puntaje, ts)
                try:
                    rpc = xmlrpc.client.ServerProxy(f"http://{IP_TAREA}:{self.puerto_rpc}")
                    rpc.calificar(usuario, anime, int(puntaje))
                except Exception:
                    pass
                send_clock = self._tick()
            self._propagate_score(usuario, anime, puntaje, ts, send_clock)

        elif tipo == "STOP":
            with self.lock:
                self.activo = False

        elif tipo == "START":
            with self.lock:
                self.activo = True
                self._synchronize_clock()

        elif tipo == "CONSOLIDAR":
            with self.lock:
                if not self.activo:
                    return
            self._consolidar()

    def _propagate_score(self, usuario, anime, puntaje, ts, send_clock):
        payload = {
            "tipo": "PROPAGATE_SCORE",
            "usuario": usuario,
            "anime": anime,
            "puntaje": int(puntaje),
            "ts": int(ts),
            "sender": self.id,
            "sender_clock": int(send_clock),
        }
        for _, port in self._peers():
            self._send_one(port, payload, expect_reply=False)

    def _handle_internal_msg(self, msg, conn):
        tipo = msg.get("tipo")
        if tipo == "PROPAGATE_SCORE":
            with self.lock:
                if not self.activo:
                    return
                key = (msg.get("usuario"), msg.get("anime"))
                before = self.ratings.get(key)
                self._tick(value=msg.get("sender_clock", 0))
                self._merge_rating(
                    msg["usuario"], msg["anime"], int(msg["puntaje"]), int(msg["ts"])\
                )
                after = self.ratings.get(key)
            if after != before:
                try:
                    rpc = xmlrpc.client.ServerProxy(f"http://{IP_TAREA}:{self.puerto_rpc}")
                    rpc.calificar(msg["usuario"], msg["anime"], int(msg["puntaje"]))
                except Exception:
                    pass

        elif tipo == "STATE_REQ":
            with self.lock:
                if not self.activo:
                    return
                state = self._serialize_store()
                lam = self.lamport
            reply = {"tipo": "STATE_RES", "from": self.id, "lamport": lam, "state": state}
            try:
                send_json(conn, reply)
            except Exception:
                return

        elif tipo == "STATE_APPLY":
            with self.lock:
                if not self.activo:
                    return
                incoming = msg.get("state", [])
                self._install_store(incoming)
                self.lamport = 0

        elif tipo == "CLOCK_REQ":
            with self.lock:
                if not self.activo:
                    return
                reply = {"tipo": "CLOCK_RES", "lamport": self.lamport}
                try:
                    send_json(conn, reply)
                except Exception:
                    return

    def _request_state(self, port):
        req = {"tipo": "STATE_REQ"}
        return self._send_one(port, req, expect_reply=True, timeout=0.9)

    def _consolidar(self):
        participants = []
        with self.lock:
            local_state = self._serialize_store()
            local_lam = self.lamport
        participants.append((self.id, local_lam, local_state))

        responders = set([self.id])
        for pid, port in self._peers():
            res = self._request_state(port)
            if res and res.get("tipo") == "STATE_RES":
                participants.append((res.get("from", pid), int(res.get("lamport", 0)), res.get("state", [])))
                responders.add(pid)

        merged = {}
        for _pid, _lam, state in participants:
            for item in state:
                key = (item["usuario"], item["anime"])
                val = {"puntaje": int(item["puntaje"]), "ts": int(item["ts"]) }
                cur = merged.get(key)
                if cur is None:
                    merged[key] = val
                else:
                    if val["ts"] > cur["ts"] or (val["ts"] == cur["ts"] and val["puntaje"] > cur["puntaje"]):
                        merged[key] = val

        consolidated_list = [
            {"usuario": u, "anime": a, "puntaje": v["puntaje"], "ts": v["ts"]}
            for (u, a), v in merged.items()
        ]

        with self.lock:
            self._install_store(consolidated_list)
            self.lamport = 0

        for pid, port in self._peers():
            if pid in responders:
                msg = {"tipo": "STATE_APPLY", "state": consolidated_list}
                self._send_one(port, msg, expect_reply=False)

        try:
            rpc = xmlrpc.client.ServerProxy(f"http://{IP_TAREA}:{self.puerto_rpc}")
            for item in consolidated_list:
                try:
                    rpc.calificar(item["usuario"], item["anime"], int(item["puntaje"]))
                except Exception:
                    pass
        except Exception:
            pass

    def run(self):
        self.main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.main_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.main_socket.bind((IP_TAREA, self.puertos[self.id]))
        self.main_socket.listen()
        print(f"Nodo {self.id} escuchando en puerto {self.puertos[self.id]}...")

        while not self._stopped.is_set():
            try:
                conn, addr = self.main_socket.accept()
                t = threading.Thread(target=self._handle_connection, args=(conn, addr), daemon=True)
                t.start()
            except Exception:
                break

    def _handle_connection(self, conn, addr):
        with conn:
            try:
                while True:
                    msg = recv_json(conn)
                    if not msg:
                        break
                    tipo = msg.get("tipo")
                    if tipo in {"SCORE", "STOP", "START", "CONSOLIDAR"}:
                        self._handle_user_msg(msg)
                    else:
                        self._handle_internal_msg(msg, conn)
            except Exception:
                return

    def stop(self):
        self._stopped.set()
        try:
            if self.main_socket:
                self.main_socket.close()
        except Exception:
            pass


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
        nodo.stop()

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    nodo.start()
    nodo.join()
