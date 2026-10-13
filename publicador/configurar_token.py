"""Configura (una sola vez) el token de Instagram en los secretos de GitHub.

Lo ejecutas TU en tu PC. Las credenciales se piden sin mostrarse en pantalla y se guardan
directamente como secretos del repositorio con `gh secret set`: no se escriben en ningun archivo.

    python configurar_token.py

Necesitas:
  1. El App ID y el App Secret de tu app de Meta (developers.facebook.com > tu app > Configuración > Básica).
  2. Un token de usuario recién generado en el Explorador de la API Graph
     (developers.facebook.com/tools/explorer) con estos permisos:
     instagram_basic, instagram_content_publish, pages_show_list,
     pages_read_engagement, business_management

El script lo cambia por un token de larga duración, saca de él el token de la página de Facebook
(que no caduca) y el id de la cuenta de Instagram vinculada.
"""
import getpass
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

VERSION = "v24.0"
NECESARIOS = ["instagram_basic", "instagram_content_publish", "pages_read_engagement",
              "pages_show_list", "business_management"]


def get(ruta, **params):
    url = f"https://graph.facebook.com/{VERSION}/{ruta}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        msg = json.loads(e.read().decode(errors="replace")).get("error", {}).get("message", "")
        sys.exit(f"Error de Meta: {msg}")


def secreto(nombre, valor):
    subprocess.run(["gh", "secret", "set", nombre], input=valor.encode(), check=True)


def main():
    print("Configuración del publicador de Instagram\n")
    app_id = input("App ID: ").strip()
    app_secret = getpass.getpass("App Secret (no se verá al escribir): ").strip()
    corto = getpass.getpass("Token del Explorador de la API Graph (no se verá): ").strip()

    # comprueba los permisos ANTES de guardar nada (con el token de app, que siempre puede consultarlo)
    info = get("debug_token", input_token=corto, access_token=f"{app_id}|{app_secret}").get("data", {})
    concedidos = set(info.get("scopes", []))
    faltan = [p for p in NECESARIOS if p not in concedidos]
    if faltan:
        sys.exit("\nEl token NO tiene estos permisos: " + ", ".join(faltan) + "\n"
                 "Vuelve al Explorador, comprueba que están en la lista de Permisos, pulsa Generate Access Token\n"
                 "y en la ventana de Facebook acepta todo (si no te pregunta nada, pulsa 'Editar acceso').\n"
                 "No se ha guardado nada.")
    print("Permisos correctos:", ", ".join(sorted(concedidos & set(NECESARIOS))))
    if info.get("type") != "USER":
        sys.exit("\nEse token es de PÁGINA, no de usuario. En el Explorador, en el desplegable 'Usuario o página',\n"
                 "elige 'Identificador de usuario' y vuelve a pulsar Generate Access Token. No se ha guardado nada.")

    largo = get("oauth/access_token", grant_type="fb_exchange_token",
                client_id=app_id, client_secret=app_secret, fb_exchange_token=corto)["access_token"]

    campos = "name,access_token,instagram_business_account{id,username}"
    paginas = get("me/accounts", fields=campos, access_token=largo).get("data", [])
    # paginas gestionadas desde un portfolio empresarial: no salen en me/accounts,
    # pero sus ids vienen en los permisos granulares del token
    vistas = {p["id"] for p in paginas}
    for g in info.get("granular_scopes", []):
        if g.get("scope") == "pages_show_list":
            for pid in g.get("target_ids", []):
                if pid not in vistas:
                    paginas.append(get(pid, fields=campos, access_token=largo))
                    vistas.add(pid)
    con_ig = [p for p in paginas if p.get("instagram_business_account") and p.get("access_token")]
    if not con_ig:
        sys.exit("Ninguna de tus páginas de Facebook tiene una cuenta de Instagram profesional vinculada.")

    for i, p in enumerate(con_ig, 1):
        print(f"  {i}. {p['name']}  ->  @{p['instagram_business_account'].get('username')}")
    n = int(input("¿Qué cuenta usar? ") or 1) if len(con_ig) > 1 else 1
    elegida = con_ig[n - 1]

    secreto("IG_USER_ID", elegida["instagram_business_account"]["id"])
    secreto("IG_ACCESS_TOKEN", elegida["access_token"])  # token de pagina: no caduca
    print(f"\nListo. Secretos guardados en GitHub para @{elegida['instagram_business_account'].get('username')}.")
    print("Pruébalo en GitHub > Actions > Publicar en Instagram > Run workflow (modo: comprobar).")


if __name__ == "__main__":
    main()
