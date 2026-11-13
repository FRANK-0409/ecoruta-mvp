import json
import os
import re
import secrets
import sqlite3
from contextlib import closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from http import HTTPStatus
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unicodedata import normalize
from urllib.parse import parse_qs, urlsplit


ROOT = Path(__file__).resolve().parent
SEDES = {"lima", "arequipa", "trujillo"}
ZONE = timezone(timedelta(hours=-5))
SESSION = "ecoruta_viajes"
ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/viajes.html": ("viajes.html", "text/html; charset=utf-8"),
    "/viajes.css": ("viajes.css", "text/css; charset=utf-8"),
    "/viajes.js": ("viajes.js", "text/javascript; charset=utf-8"),
    "/sedes.js": ("sedes.js", "text/javascript; charset=utf-8"),
}
ACTION = re.compile(r"/api/publicaciones/([1-9][0-9]{0,14})/(unirse|confirmar|ofrecer)")
SCHEMA = """
CREATE TABLE IF NOT EXISTS publicaciones (
    id INTEGER PRIMARY KEY,
    tipo TEXT NOT NULL CHECK (tipo IN ('viaje', 'grupo')),
    propietario TEXT NOT NULL,
    alias TEXT NOT NULL,
    sede TEXT NOT NULL,
    distrito TEXT NOT NULL,
    distrito_clave TEXT NOT NULL,
    fecha TEXT NOT NULL,
    hora TEXT NOT NULL,
    punto TEXT,
    llegada TEXT,
    cupos INTEGER CHECK (cupos BETWEEN 1 AND 8),
    aporte INTEGER CHECK (aporte >= 0),
    grupo_id INTEGER REFERENCES publicaciones(id),
    operacion TEXT,
    UNIQUE (grupo_id, propietario),
    UNIQUE (propietario, operacion)
);
CREATE TABLE IF NOT EXISTS participantes (
    publicacion_id INTEGER NOT NULL REFERENCES publicaciones(id),
    persona TEXT NOT NULL,
    alias TEXT NOT NULL,
    estado TEXT NOT NULL CHECK (estado IN ('pendiente', 'confirmado')),
    PRIMARY KEY (publicacion_id, persona)
);
CREATE INDEX IF NOT EXISTS publicaciones_busqueda
ON publicaciones (sede, fecha, distrito_clave);
"""


class SolicitudInvalida(Exception):
    def __init__(self, message, status=HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


def texto(data, key, maximum, required=True):
    value = data.get(key, "")
    if not isinstance(value, str):
        raise SolicitudInvalida("Revisa los datos de la publicación.")
    value = " ".join(value.split())
    if (required and not value) or len(value) > maximum:
        raise SolicitudInvalida("Completa los campos y respeta su longitud máxima.")
    return value


def clave_distrito(value):
    return "".join(char for char in normalize("NFKD", value.casefold()) if char.isalpha())


def distrito(data, required=True):
    name = normalize("NFC", texto(data, "distrito", 60, required))
    normalized = clave_distrito(name)
    if name and (not normalized or not all(char.isalpha() or char in " -'’." for char in name)):
        raise SolicitudInvalida("Escribe un nombre de distrito, como Paucarpata o Cayma.")
    return name, normalized


def entero(data, key, minimum, maximum, message):
    value = data.get(key)
    if type(value) is not int or not minimum <= value <= maximum:
        raise SolicitudInvalida(message)
    return value


def fecha_iso(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise SolicitudInvalida("Elige una fecha válida.")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise SolicitudInvalida("Elige una fecha válida.") from error


def hora_valida(value):
    if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value):
        raise SolicitudInvalida("Elige una hora válida.")
    return value


def validar_sede(sede):
    if sede not in SEDES:
        raise SolicitudInvalida("Elige una sede de Tecsup.")
    return sede


def hoy():
    return datetime.now(ZONE).date().isoformat()


def horario_actual():
    now = datetime.now(ZONE)
    return now.date().isoformat(), now.strftime("%H:%M")


def campos_viaje(data):
    point = texto(data, "punto", 120)
    arrival = hora_valida(texto(data, "llegada", 5))
    seats = entero(data, "cupos", 1, 8, "Indica entre 1 y 8 asientos.")
    cost = entero(data, "aporte", 0, (2**53 - 1) // 100,
                  "Indica un aporte válido, de cero soles en adelante.")
    return point, arrival, seats, cost


class Viajes:
    def __init__(self, database):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.conectar()) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)

    def conectar(self):
        db = sqlite3.connect(self.database, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @contextmanager
    def escritura(self):
        with closing(self.conectar()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            yield db

    def listar(self, filtros, persona):
        today, current_time = horario_actual()
        conditions = ["p.sede = ?"]
        parameters = [validar_sede(filtros.get("sede", "arequipa"))]
        _, key = distrito(filtros, required=False)
        if key:
            conditions.append("p.distrito_clave = ?")
            parameters.append(key)
        if filtros.get("fecha"):
            conditions.append("p.fecha = ?")
            parameters.append(fecha_iso(filtros["fecha"]))
        else:
            conditions.append("(p.fecha > ? OR (p.fecha = ? AND p.hora >= ?))")
            parameters.extend((today, today, current_time))
        if filtros.get("tipo"):
            if filtros["tipo"] not in {"viaje", "grupo"}:
                raise SolicitudInvalida("Elige un tipo de publicación válido.")
            conditions.append("p.tipo = ?")
            parameters.append(filtros["tipo"])

        with closing(self.conectar()) as db, db:
            db.execute("BEGIN")
            rows = db.execute(
                f"""SELECT p.*, g.alias AS grupo_alias,
                           CASE WHEN g.id IS NULL OR g.propietario = ? OR EXISTS (
                               SELECT 1 FROM participantes gm
                               WHERE gm.publicacion_id = g.id AND gm.persona = ?
                           ) THEN 1 ELSE 0 END AS puede_solicitar
                    FROM publicaciones p
                    LEFT JOIN publicaciones g ON g.id = p.grupo_id
                    WHERE {' AND '.join(conditions)} AND (g.id IS NULL OR g.propietario = ?
                        OR p.propietario = ? OR EXISTS (
                            SELECT 1 FROM participantes gm
                            WHERE gm.publicacion_id = g.id AND gm.persona = ?
                        ))
                    ORDER BY p.fecha, p.hora, p.id DESC LIMIT 100""",
                [persona, persona, *parameters, persona, persona, persona],
            ).fetchall()
            if not rows:
                return []
            placeholders = ",".join("?" for _ in rows)
            participants = {}
            for member in db.execute(
                f"""SELECT rowid AS id, * FROM participantes
                    WHERE publicacion_id IN ({placeholders}) ORDER BY rowid""",
                [row["id"] for row in rows],
            ):
                participants.setdefault(member["publicacion_id"], []).append(member)
            return [self.presentar(row, participants.get(row["id"], []), persona, (today, current_time))
                    for row in rows]

    @staticmethod
    def presentar(row, participants, persona, now):
        keys = ("id", "tipo", "alias", "sede", "distrito", "fecha", "hora", "llegada",
                "punto", "cupos", "aporte", "grupo_id", "grupo_alias")
        item = {key: row[key] for key in keys}
        item["activo"] = (row["fecha"], row["hora"]) >= now
        item["puede_solicitar"] = bool(row["puede_solicitar"])
        owner = row["propietario"] == persona
        item["propia"] = owner
        item["mi_estado"] = next(
            (member["estado"] for member in participants if member["persona"] == persona), None
        )
        if row["tipo"] == "viaje":
            item["disponibles"] = row["cupos"] - sum(
                member["estado"] == "confirmado" for member in participants
            )
            item["solicitudes"] = [
                {"id": member["id"], "alias": member["alias"], "estado": member["estado"]}
                for member in participants
            ] if owner else []
        else:
            item["integrantes"] = len(participants) + 1
        return item

    def publicar(self, data, persona):
        operation = texto(data, "operacion", 32)
        if not re.fullmatch(r"[0-9a-f]{32}", operation):
            raise SolicitudInvalida("Vuelve a abrir el formulario de publicación.")
        kind = data.get("tipo")
        if kind not in ("viaje", "grupo"):
            raise SolicitudInvalida("Elige si ofreces asientos o buscas compañía.")
        alias = texto(data, "alias", 36)
        sede = validar_sede(texto(data, "sede", 12))
        district, key = distrito(data)
        date = fecha_iso(texto(data, "fecha", 10))
        time = hora_valida(texto(data, "hora", 5))
        trip = campos_viaje(data) if kind == "viaje" else (texto(data, "punto", 120, False), None, None, None)
        if kind == "viaje" and time >= trip[1]:
            raise SolicitudInvalida("La hora de recojo debe ser anterior a la hora de llegada.")
        with self.escritura() as db:
            previous = db.execute(
                "SELECT id FROM publicaciones WHERE propietario = ? AND operacion = ?",
                (persona, operation),
            ).fetchone()
            if previous:
                return previous["id"]
            if (date, time) < horario_actual():
                raise SolicitudInvalida("Elige una fecha y hora que aún no hayan pasado.")
            result = db.execute(
                """INSERT INTO publicaciones
                   (tipo, propietario, alias, sede, distrito, distrito_clave, fecha, hora,
                    punto, llegada, cupos, aporte, operacion) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (kind, persona, alias, sede, district, key, date, time, *trip, operation),
            )
            return result.lastrowid

    def actuar(self, item_id, action, data, persona):
        with self.escritura() as db:
            item = db.execute("SELECT * FROM publicaciones WHERE id = ?", (item_id,)).fetchone()
            if not item:
                raise SolicitudInvalida("La publicación ya no está disponible.", HTTPStatus.NOT_FOUND)
            if (item["fecha"], item["hora"]) < horario_actual():
                raise SolicitudInvalida("La fecha u hora de esta publicación ya pasó.", HTTPStatus.CONFLICT)
            owner = item["propietario"] == persona

            if action == "unirse":
                if owner:
                    raise SolicitudInvalida("Esta publicación es tuya.")
                previous = db.execute(
                    "SELECT estado FROM participantes WHERE publicacion_id = ? AND persona = ?",
                    (item_id, persona),
                ).fetchone()
                if previous:
                    return item_id
                if item["tipo"] == "viaje":
                    if item["grupo_id"] and not self.es_del_grupo(db, item["grupo_id"], persona):
                        raise SolicitudInvalida("Esta oferta está reservada para el grupo.", HTTPStatus.FORBIDDEN)
                    confirmed = self.confirmados(db, item_id)
                    if confirmed >= item["cupos"]:
                        raise SolicitudInvalida("El viaje está lleno.", HTTPStatus.CONFLICT)
                db.execute(
                    "INSERT INTO participantes (publicacion_id, persona, alias, estado) VALUES (?, ?, ?, ?)",
                    (item_id, persona, texto(data, "alias", 36),
                     "pendiente" if item["tipo"] == "viaje" else "confirmado"),
                )
                return item_id

            if action == "confirmar":
                if not owner or item["tipo"] != "viaje":
                    raise SolicitudInvalida("Solo el conductor puede confirmar solicitudes.", HTTPStatus.FORBIDDEN)
                request_id = entero(data, "solicitud", 1, 10**15 - 1, "La solicitud no es válida.")
                request = db.execute(
                    "SELECT estado FROM participantes WHERE rowid = ? AND publicacion_id = ?",
                    (request_id, item_id),
                ).fetchone()
                if not request:
                    raise SolicitudInvalida("La solicitud ya no está disponible.", HTTPStatus.NOT_FOUND)
                if request["estado"] == "confirmado":
                    return item_id
                if self.confirmados(db, item_id) >= item["cupos"]:
                    raise SolicitudInvalida("El último asiento ya se confirmó.", HTTPStatus.CONFLICT)
                db.execute("UPDATE participantes SET estado = 'confirmado' WHERE rowid = ?", (request_id,))
                return item_id

            if action != "ofrecer" or item["tipo"] != "grupo":
                raise SolicitudInvalida("Solo puedes ofrecer asientos a un grupo.")
            if self.es_del_grupo(db, item_id, persona):
                raise SolicitudInvalida("Ofrece asientos a un grupo en el que no participes.", HTTPStatus.CONFLICT)
            previous = db.execute(
                "SELECT id FROM publicaciones WHERE grupo_id = ? AND propietario = ?", (item_id, persona)
            ).fetchone()
            if previous:
                return previous["id"]
            alias = texto(data, "alias", 36)
            time = hora_valida(texto(data, "hora", 5))
            point, arrival, seats, cost = campos_viaje(data)
            if time >= arrival or arrival > item["hora"]:
                raise SolicitudInvalida("El recojo debe ser anterior a la llegada y la llegada no puede superar la hora del grupo.")
            if (item["fecha"], time) < horario_actual():
                raise SolicitudInvalida("La hora de recojo ya pasó.")
            result = db.execute(
                """INSERT INTO publicaciones
                   (tipo, propietario, alias, sede, distrito, distrito_clave, fecha, hora,
                    punto, llegada, cupos, aporte, grupo_id)
                   VALUES ('viaje', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (persona, alias, item["sede"], item["distrito"], item["distrito_clave"],
                 item["fecha"], time, point, arrival, seats, cost, item_id),
            )
            return result.lastrowid

    @staticmethod
    def confirmados(db, item_id):
        return db.execute(
            "SELECT count(*) FROM participantes WHERE publicacion_id = ? AND estado = 'confirmado'", (item_id,)
        ).fetchone()[0]

    @staticmethod
    def es_del_grupo(db, group_id, persona):
        return db.execute(
            """SELECT 1 FROM publicaciones WHERE id = ? AND propietario = ?
               UNION ALL SELECT 1 FROM participantes WHERE publicacion_id = ? AND persona = ? LIMIT 1""",
            (group_id, persona, group_id, persona),
        ).fetchone() is not None


class EcoRutaHandler(BaseHTTPRequestHandler):
    def responder(self, status, body, media_type, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", media_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def json(self, status, value, cookie=None):
        self.responder(status, json.dumps(value, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8", cookie)

    def sesion(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except CookieError:
            cookies.clear()
        token = cookies[SESSION].value if SESSION in cookies else ""
        cookie = None
        if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
            token = secrets.token_urlsafe(32)
            cookie = f"{SESSION}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age=2592000"
            if self.server.secure_cookie:
                cookie += "; Secure"
        return sha256(token.encode("ascii")).hexdigest(), cookie

    def datos(self):
        if self.headers.get_content_type() != "application/json":
            raise SolicitudInvalida("Se esperaba un formulario válido.")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                raise SolicitudInvalida("El formulario supera el tamaño permitido.", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeError) as error:
            raise SolicitudInvalida("Revisa los datos del formulario.") from error
        if not isinstance(data, dict):
            raise SolicitudInvalida("Revisa los datos del formulario.")
        return data

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/api/publicaciones":
            persona, cookie = self.sesion()
            try:
                query = parse_qs(url.query, max_num_fields=16)
                filtros = {key: values[0] for key, values in query.items()}
                publicaciones = self.server.viajes.listar(filtros, persona)
                self.json(HTTPStatus.OK, {"publicaciones": publicaciones, "hoy": hoy()}, cookie)
            except SolicitudInvalida as error:
                self.json(error.status, {"error": str(error)}, cookie)
            except ValueError:
                self.json(HTTPStatus.BAD_REQUEST, {"error": "Revisa los filtros de búsqueda."}, cookie)
            except sqlite3.OperationalError as error:
                self.log_error("%s", error)
                self.json(HTTPStatus.SERVICE_UNAVAILABLE,
                          {"error": "No pudimos consultar los viajes. Inténtalo otra vez."}, cookie)
            return

        if url.path in ASSETS:
            filename, media_type = ASSETS[url.path]
            self.responder(HTTPStatus.OK, (ROOT / filename).read_bytes(), media_type)
        else:
            self.send_error(HTTPStatus.NOT_FOUND)

    do_HEAD = do_GET

    def do_POST(self):
        path = urlsplit(self.path).path
        action = ACTION.fullmatch(path)
        if path != "/api/publicaciones" and not action:
            self.json(HTTPStatus.NOT_FOUND, {"error": "La operación no está disponible."})
            return
        persona, cookie = self.sesion()
        try:
            data = self.datos()
            if action:
                item_id = self.server.viajes.actuar(int(action[1]), action[2], data, persona)
                self.json(HTTPStatus.OK, {"id": item_id}, cookie)
            else:
                item_id = self.server.viajes.publicar(data, persona)
                self.json(HTTPStatus.CREATED, {"id": item_id}, cookie)
        except SolicitudInvalida as error:
            self.json(error.status, {"error": str(error)}, cookie)
        except sqlite3.OperationalError as error:
            self.log_error("%s", error)
            self.json(HTTPStatus.SERVICE_UNAVAILABLE,
                      {"error": "No pudimos guardar el cambio. Inténtalo otra vez."}, cookie)


def main():
    host = os.environ.get("ECORUTA_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    database = os.environ.get("ECORUTA_DB", ROOT / "datos" / "viajes.sqlite3")
    with ThreadingHTTPServer((host, port), EcoRutaHandler) as server:
        server.viajes = Viajes(database)
        server.secure_cookie = os.environ.get("ECORUTA_HTTPS") == "1"
        print(f"EcoRuta en http://{host}:{server.server_port}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
