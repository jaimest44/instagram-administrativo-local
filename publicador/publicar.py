"""Publica en Instagram el carrusel del dia que esta en cola/AAAA-MM-DD.

Se ejecuta en GitHub Actions (ver .github/workflows/publicar.yml). Solo usa la libreria estandar.

Variables de entorno (secretos del repositorio):
    IG_USER_ID       id de la cuenta de Instagram profesional
    IG_ACCESS_TOKEN  token con permiso instagram_content_publish
Opcionales:
    GRAPH_HOST       graph.facebook.com (por defecto) o graph.instagram.com
    GRAPH_VERSION    v24.0 por defecto
    URL_BASE         de donde descarga Instagram las imagenes; por defecto el raw de GitHub

    python publicar.py              publica lo pendiente de hoy
    python publicar.py --comprobar  solo comprueba que el token funciona y que hay cola
    python publicar.py --simular    dice que publicaria, sin publicar
"""
import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, ".."))
COLA = os.path.join(REPO, "cola")
PUBLICADAS = os.path.join(REPO, "estado", "publicadas.json")

HOST = os.environ.get("GRAPH_HOST", "graph.facebook.com")
VERSION = os.environ.get("GRAPH_VERSION", "v24.0")
AVISO_COLA = 7  # avisa cuando queden menos dias preparados
HORA_PUBLICACION = dt.time(20, 30)  # hora de Madrid; antes de esta hora no se publica


class ErrorAPI(Exception):
    pass


def api(metodo, ruta, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    url = f"https://{HOST}/{VERSION}/{ruta}"
    datos = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        req = urllib.request.Request(url + "?" + datos.decode())
    else:
        req = urllib.request.Request(url, data=datos, method="POST")
    for intento in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode(errors="replace")
            try:
                err = json.loads(cuerpo).get("error", {})
            except ValueError:
                err = {}
            # errores transitorios: reintenta
            if e.code >= 500 or err.get("is_transient") or err.get("code") in (1, 2, 4, 17, 32, 613):
                time.sleep(10 * (intento + 1))
                continue
            # nunca imprimir el token
            raise ErrorAPI(f"{e.code} {err.get('message', cuerpo)[:400]}") from None
        except urllib.error.URLError:
            time.sleep(10 * (intento + 1))
    raise ErrorAPI(f"La API no responde tras varios intentos ({ruta})")


def esperar_contenedor(cid, maximo=180):
    inicio = time.time()
    while time.time() - inicio < maximo:
        estado = api("GET", cid, fields="status_code,status").get("status_code")
        if estado == "FINISHED":
            return
        if estado in ("ERROR", "EXPIRED"):
            raise ErrorAPI(f"El contenedor {cid} quedó en estado {estado}")
        time.sleep(5)
    raise ErrorAPI(f"El contenedor {cid} no terminó de procesarse")


def url_base():
    if os.environ.get("URL_BASE"):
        return os.environ["URL_BASE"].rstrip("/")
    repo = os.environ["GITHUB_REPOSITORY"]
    rama = os.environ.get("GITHUB_REF_NAME", "main")
    return f"https://raw.githubusercontent.com/{repo}/{rama}/cola"


def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return defecto


def pendientes(hoy, publicadas):
    if not os.path.isdir(COLA):
        return []
    dias = sorted(d for d in os.listdir(COLA) if os.path.isfile(os.path.join(COLA, d, "meta.json")))
    return [d for d in dias if d <= hoy.isoformat() and d not in publicadas]


def publicar(dia):
    carpeta = os.path.join(COLA, dia)
    meta = leer_json(os.path.join(carpeta, "meta.json"), {})
    with open(os.path.join(carpeta, "caption.txt"), encoding="utf-8") as f:
        texto = f.read()
    ig = os.environ["IG_USER_ID"]
    base = f"{url_base()}/{dia}"

    hijos = []
    for img in meta["imagenes"]:
        r = api("POST", f"{ig}/media", image_url=f"{base}/{img}", is_carousel_item="true")
        hijos.append(r["id"])
    for h in hijos:
        esperar_contenedor(h)
    carrusel = api("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(hijos), caption=texto)
    esperar_contenedor(carrusel["id"])
    pub = api("POST", f"{ig}/media_publish", creation_id=carrusel["id"])
    info = api("GET", pub["id"], fields="permalink")
    return {"media_id": pub["id"], "permalink": info.get("permalink", ""),
            "publicado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "id_pregunta": meta.get("id")}


NECESARIOS = ["instagram_basic", "instagram_content_publish", "pages_read_engagement", "pages_show_list"]


def diagnosticar():
    """Lista los permisos del token guardado y dice cuales faltan para publicar."""
    token = os.environ["IG_ACCESS_TOKEN"]
    try:
        info = api("GET", "debug_token", input_token=token).get("data", {})
    except ErrorAPI as e:
        if "pages_read_engagement" in str(e):
            print("::error::El token guardado no tiene pages_read_engagement (ni puede consultarse a sí mismo). "
                  "Genera uno nuevo y vuelve a ejecutar publicador/configurar_token.py.")
        else:
            print(f"::error::No se pudo consultar el token: {e}")
        sys.exit(1)
    permisos = sorted(info.get("scopes", []))
    print(f"Tipo de token: {info.get('type')}  ·  válido: {info.get('is_valid')}  ·  "
          f"caduca: {'nunca' if not info.get('expires_at') else dt.datetime.fromtimestamp(info['expires_at'])}")
    print("Permisos concedidos:", ", ".join(permisos) or "(ninguno)")
    for g in info.get("granular_scopes", []):
        print(f"  {g.get('scope')}: {len(g.get('target_ids', []))} recursos")
    faltan = [p for p in NECESARIOS if p not in permisos]
    if faltan:
        print(f"::error::Al token le faltan permisos para publicar: {', '.join(faltan)}")
        sys.exit(1)
    print("Tiene todos los permisos necesarios para publicar.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comprobar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--ya", action="store_true", help="publica aunque no sea la hora")
    ap.add_argument("--diagnosticar", action="store_true", help="muestra los permisos del token (nunca el token)")
    a = ap.parse_args()

    ahora = dt.datetime.now(ZoneInfo("Europe/Madrid"))
    hoy = ahora.date()
    publicadas = leer_json(PUBLICADAS, {})
    cola = pendientes(hoy, publicadas)
    futuras = [d for d in os.listdir(COLA) if d > hoy.isoformat()] if os.path.isdir(COLA) else []
    print(f"Hoy {hoy}. Pendientes: {len(cola)}. Días preparados por delante: {len(futuras)}.")
    if len(futuras) < AVISO_COLA:
        print(f"::warning::Solo quedan {len(futuras)} días en cola. Ejecuta generar_cola.py en el PC.")

    if a.comprobar:
        cuenta = api("GET", os.environ["IG_USER_ID"], fields="username")
        print(f"Token correcto. Cuenta: @{cuenta.get('username')}")
        return
    if a.diagnosticar:
        diagnosticar()
        return
    if not cola:
        print("Nada que publicar hoy.")
        return
    if not (a.ya or a.simular) and ahora.time() < HORA_PUBLICACION:
        print(f"Son las {ahora:%H:%M} en Madrid: se publica a partir de las {HORA_PUBLICACION:%H:%M}.")
        return

    # solo la de hoy y como mucho una al dia: los dias que fallaron se saltan
    dia = hoy.isoformat()
    if dia not in cola:
        print(f"Nada para hoy (hay {len(cola)} días antiguos sin publicar que se saltan).")
        return
    if a.simular:
        print(f"Publicaría {dia}: {url_base()}/{dia}")
        return
    try:
        resultado = publicar(dia)
    except ErrorAPI as e:
        print(f"::error::No se pudo publicar {dia}: {e}")
        sys.exit(1)
    publicadas[dia] = resultado
    os.makedirs(os.path.dirname(PUBLICADAS), exist_ok=True)
    with open(PUBLICADAS, "w", encoding="utf-8") as f:
        json.dump(publicadas, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Publicado {dia}: {resultado['permalink']}")


if __name__ == "__main__":
    main()
