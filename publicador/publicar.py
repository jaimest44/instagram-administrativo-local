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
import re
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
# GitHub lanza los cron con horas de retraso: una ejecucion de madrugada aun publica el dia anterior
HORA_RECUPERACION = dt.time(6, 0)


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
    # la fecha son los 10 primeros caracteres ("2026-10-23_mediodia" es del dia 23)
    return [d for d in dias if d[:10] <= hoy.isoformat() and d not in publicadas]


# Dos publicaciones al dia: (sufijo de la carpeta en cola/, hora de Madrid a partir de la que se publica)
FRANJAS = [("_mediodia", dt.time(14, 0)), ("", None)]  # None = HORA_PUBLICACION (noche)


def franja_actual(ahora):
    """Sufijo de la franja que toca a esta hora, o None si aun no toca ninguna."""
    sufijo = None
    for suf, hora in FRANJAS:
        if ahora.time() >= (hora or HORA_PUBLICACION):
            sufijo = suf
    return sufijo


def comprobar_cuenta():
    """Para en seco si las credenciales son de otra cuenta que la de este repositorio (cuenta.txt)."""
    with open(os.path.join(AQUI, "cuenta.txt"), encoding="utf-8") as f:
        esperada = f.read().strip().lstrip("@").lower()
    real = api("GET", os.environ["IG_USER_ID"], fields="username").get("username", "")
    if real.lower() != esperada:
        raise ErrorAPI(f"Las credenciales guardadas son de @{real}, pero este repositorio publica en @{esperada}. "
                       f"No se publica nada. Repite publicador/configurar_token.py en la carpeta correcta.")
    return real


def publicar_reel(dia, meta, texto, base):
    """Publica el reel.mp4 de la carpeta como Reel (y lo comparte tambien en el feed)."""
    ig = os.environ["IG_USER_ID"]
    cont = api("POST", f"{ig}/media", media_type="REELS", video_url=f"{base}/{meta['reel']}",
               caption=texto, share_to_feed="true")
    esperar_contenedor(cont["id"], maximo=600)  # el video tarda mas en procesarse
    pub = api("POST", f"{ig}/media_publish", creation_id=cont["id"])
    info = api("GET", pub["id"], fields="permalink")
    return {"media_id": pub["id"], "permalink": info.get("permalink", ""), "tipo": "reel",
            "publicado": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "id_pregunta": meta.get("id")}


def publicar(dia):
    carpeta = os.path.join(COLA, dia)
    meta = leer_json(os.path.join(carpeta, "meta.json"), {})
    with open(os.path.join(carpeta, "caption.txt"), encoding="utf-8") as f:
        texto = f.read()
    ig = os.environ["IG_USER_ID"]
    base = f"{url_base()}/{dia}"
    comprobar_cuenta()
    if meta.get("reel"):
        return publicar_reel(dia, meta, texto, base)

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


# ---------------------------------------------------------------- Facebook (pagina)

def fb_api(metodo, ruta, host="graph.facebook.com", **params):
    """Llamada a la API de Facebook con el token de la PAGINA (secreto FB_PAGE_TOKEN)."""
    params["access_token"] = os.environ["FB_PAGE_TOKEN"]
    url = f"https://{host}/{VERSION}/{ruta}"
    datos = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=datos, method="POST") if metodo == "POST" \
        else urllib.request.Request(url + "?" + datos.decode())
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            cuerpo = e.read().decode(errors="replace")
            if e.code >= 500 and intento < 2:
                time.sleep(10 * (intento + 1))
                continue
            try:
                msg = json.loads(cuerpo).get("error", {}).get("message", cuerpo)
            except ValueError:
                msg = cuerpo
            raise ErrorAPI(f"Facebook {e.code}: {msg[:300]}") from None


def texto_facebook(texto):
    """En Facebook los enlaces se pueden pulsar: sobra "(enlace en la bio)" y se añade https y utm."""
    texto = texto.replace(" (enlace en la bio)", "").replace("(enlace en la bio)", "")
    return re.sub(r"(?<![/\w.])(app\.[a-z]+\.com)\b",
                  r"https://\1/?utm_source=facebook&utm_medium=post", texto)


def publicar_facebook(dia):
    """Publica en la pagina de Facebook lo mismo que se acaba de publicar en Instagram.
    Devuelve None si esta cuenta no tiene Facebook configurado."""
    pagina = os.environ.get("FB_PAGE_ID")
    if not pagina or not os.environ.get("FB_PAGE_TOKEN"):
        return None
    carpeta = os.path.join(COLA, dia)
    meta = leer_json(os.path.join(carpeta, "meta.json"), {})
    with open(os.path.join(carpeta, "caption.txt"), encoding="utf-8") as f:
        texto = texto_facebook(f.read())
    base = f"{url_base()}/{dia}"
    if meta.get("reel"):
        r = fb_api("POST", f"{pagina}/videos", host="graph-video.facebook.com",
                   file_url=f"{base}/{meta['reel']}", description=texto)
        return {"video_id": r.get("id")}
    fotos = [fb_api("POST", f"{pagina}/photos", url=f"{base}/{img}", published="false")["id"]
             for img in meta["imagenes"]]
    r = fb_api("POST", f"{pagina}/feed", message=texto,
               attached_media=json.dumps([{"media_fbid": f} for f in fotos]))
    return {"post_id": r.get("id")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--comprobar", action="store_true")
    ap.add_argument("--simular", action="store_true")
    ap.add_argument("--ya", action="store_true", help="publica aunque no sea la hora")
    ap.add_argument("--diagnosticar", action="store_true", help="muestra los permisos del token (nunca el token)")
    ap.add_argument("--probar_reel", action="store_true",
                    help="Instagram descarga y procesa el proximo Reel de la cola, sin publicarlo")
    a = ap.parse_args()

    ahora = dt.datetime.now(ZoneInfo("Europe/Madrid"))
    hoy = ahora.date()
    de_madrugada = ahora.time() < HORA_RECUPERACION
    if de_madrugada:
        hoy -= dt.timedelta(days=1)  # el cron de anoche llego tarde: le toca al dia de ayer
    publicadas = leer_json(PUBLICADAS, {})
    cola = pendientes(hoy, publicadas)
    futuras = sorted({d[:10] for d in os.listdir(COLA) if d[:10] > hoy.isoformat()}) if os.path.isdir(COLA) else []
    print(f"Hoy {hoy}. Pendientes: {len(cola)}. Días preparados por delante: {len(futuras)}.")
    if len(futuras) < AVISO_COLA:
        print(f"::warning::Solo quedan {len(futuras)} días en cola. Ejecuta generar_cola.py en el PC.")

    if a.comprobar:
        print(f"Token correcto. Cuenta: @{comprobar_cuenta()}")
        if os.environ.get("FB_PAGE_ID") and os.environ.get("FB_PAGE_TOKEN"):
            pagina = fb_api("GET", os.environ["FB_PAGE_ID"], fields="name")
            print(f"Facebook correcto. Página: {pagina.get('name')}")
        else:
            print("Facebook: sin configurar (falta ejecutar publicador/configurar_facebook.py).")
        return
    if a.probar_reel:
        prox = next((d for d in sorted(os.listdir(COLA)) if d[:10] >= hoy.isoformat() and d not in publicadas
                     and leer_json(os.path.join(COLA, d, "meta.json"), {}).get("reel")), None)
        if not prox:
            print("No hay ningún Reel en la cola.")
            return
        comprobar_cuenta()
        url = f"{url_base()}/{prox}/reel.mp4"
        cont = api("POST", f"{os.environ['IG_USER_ID']}/media", media_type="REELS", video_url=url,
                   caption="prueba", share_to_feed="true")
        try:
            esperar_contenedor(cont["id"], maximo=600)
        except ErrorAPI as e:
            print(f"::error::Instagram no aceptó el Reel de {prox}: {e}")
            sys.exit(1)
        print(f"Reel de {prox} aceptado y procesado por Instagram (NO se ha publicado).")
        return
    if a.diagnosticar:
        diagnosticar()
        return
    if not cola:
        print("Nada que publicar hoy.")
        return
    # franja que toca: de madrugada, la noche de ayer (el cron llego tarde)
    sufijo = "" if de_madrugada else franja_actual(ahora)
    if sufijo is None:
        if not (a.ya or a.simular):
            print(f"Son las {ahora:%H:%M} en Madrid: la primera publicación es a las {FRANJAS[0][1]:%H:%M}.")
            return
        sufijo = FRANJAS[0][0]

    # solo la de esta franja y como mucho una por franja: las que fallaron se saltan
    dia = hoy.isoformat() + sufijo
    if dia not in cola:
        hecho = dia in publicadas
        print(f"Nada para {dia}" + (" (ya publicada)." if hecho else f" (hay {len(cola)} antiguas sin publicar que se saltan)."))
        return
    if a.simular:
        print(f"Publicaría {dia}: {url_base()}/{dia}")
        return
    try:
        resultado = publicar(dia)
    except ErrorAPI as e:
        print(f"::error::No se pudo publicar {dia}: {e}")
        sys.exit(1)
    # Facebook: si falla, Instagram ya esta publicado; se avisa pero no se marca como error
    try:
        fb = publicar_facebook(dia)
        if fb:
            resultado["facebook"] = fb
            print(f"Publicado también en Facebook: {fb}")
    except Exception as e:  # noqa: BLE001
        resultado["facebook_error"] = str(e)[:300]
        print(f"::warning::Instagram OK, pero falló Facebook: {e}")
    publicadas[dia] = resultado
    os.makedirs(os.path.dirname(PUBLICADAS), exist_ok=True)
    with open(PUBLICADAS, "w", encoding="utf-8") as f:
        json.dump(publicadas, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Publicado {dia}: {resultado['permalink']}")


if __name__ == "__main__":
    main()
