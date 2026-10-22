"""Configura (una vez) la publicación automática en la PÁGINA DE FACEBOOK de esta cuenta.

Lo ejecutas TÚ. Pide el App ID, el App Secret y un token de usuario del Explorador de la API Graph
(sin mostrarlos en pantalla) y guarda en GitHub el token de la página, que no caduca:
    FB_PAGE_ID, FB_PAGE_TOKEN

    python publicador/configurar_facebook.py

La página que corresponde a esta carpeta está en publicador/pagina.txt: si el token no da acceso
a esa página, no se guarda nada.
"""
import getpass
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "v24.0"
AQUI = os.path.dirname(os.path.abspath(__file__))
NECESARIOS = ["pages_manage_posts", "pages_read_engagement", "pages_show_list"]

with open(os.path.join(AQUI, "pagina.txt"), encoding="utf-8") as _f:
    PAGINA = _f.read().strip()


def get(ruta, **params):
    url = f"https://graph.facebook.com/{VERSION}/{ruta}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode(errors="replace")).get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        sys.exit(f"Error de Meta: {msg or e.code}")


def secreto(nombre, valor):
    subprocess.run(["gh", "secret", "set", nombre], input=valor.encode(), cwd=os.path.dirname(AQUI), check=True)


def normal(t):
    return " ".join(t.lower().replace("í", "i").replace("á", "a").split())


def main():
    print(f"Publicación en la página de Facebook «{PAGINA}»\n")
    app_id = input("App ID: ").strip()
    app_secret = getpass.getpass("App Secret (no se verá al escribir): ").strip()
    corto = getpass.getpass("Token del Explorador de la API Graph (no se verá): ").strip()

    info = get("debug_token", input_token=corto, access_token=f"{app_id}|{app_secret}").get("data", {})
    faltan = [p for p in NECESARIOS if p not in info.get("scopes", [])]
    if faltan:
        sys.exit("El token NO tiene estos permisos: " + ", ".join(faltan) + ". No se ha guardado nada.")
    if info.get("type") != "USER":
        sys.exit("Ese token es de PÁGINA: en el Explorador elige 'Identificador de usuario'. No se ha guardado nada.")

    largo = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                client_secret=app_secret, fb_exchange_token=corto)["access_token"]
    paginas = get("me/accounts", fields="id,name,access_token", access_token=largo).get("data", [])
    vistas = {p["id"] for p in paginas}
    for g in info.get("granular_scopes", []):  # paginas de portfolios empresariales
        for pid in g.get("target_ids", []) if g.get("scope") == "pages_manage_posts" else []:
            if pid not in vistas:
                paginas.append(get(pid, fields="id,name,access_token", access_token=largo))
                vistas.add(pid)
    print("Páginas a las que da acceso este token:", ", ".join(p.get("name", "?") for p in paginas))
    elegida = next((p for p in paginas if normal(p.get("name", "")) == normal(PAGINA) and p.get("access_token")), None)
    if not elegida:
        sys.exit(f"El token no da acceso a la página «{PAGINA}». No se ha guardado nada.")
    secreto("FB_PAGE_ID", elegida["id"])
    secreto("FB_PAGE_TOKEN", elegida["access_token"])  # token de pagina: no caduca
    print(f"\nListo. Las publicaciones saldrán también en la página «{elegida['name']}».")


if __name__ == "__main__":
    main()
