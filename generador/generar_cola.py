"""Rellena la cola de publicaciones hasta tener N dias preparados.

    python generar_cola.py            # deja 30 dias preparados
    python generar_cola.py --dias 45
    python generar_cola.py --subir    # ademas hace commit y push a GitHub

Cada dia de la cola es una carpeta cola/AAAA-MM-DD con las imagenes, caption.txt y meta.json.
estado/usadas.json guarda que preguntas ya se han usado para no repetirlas nunca.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import random
import subprocess
from collections import defaultdict

from caption import caption
from carrusel import generar
from datos import cargar, es_desarrollo, problemas

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(AQUI, ".."))
COLA = os.path.join(REPO, "cola")
USADAS = os.path.join(REPO, "estado", "usadas.json")

# lunes=0 ... domingo=6
PLAN_SEMANAL = {0: "test", 1: "test", 2: "corta", 3: "test", 4: "test", 5: "corta", 6: "test"}

# Separacion minima (en publicaciones) antes de repetir tema / convocatoria / caso
SEPARACION_TEMA = 4
SEPARACION_CONV = 3
SEPARACION_CASO = 20


def leer_json(ruta, defecto):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return defecto


def guardar_json(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, sort_keys=True)


def caso(p):
    """Identificador del supuesto: preguntas del mismo enunciado no deben ir seguidas."""
    return p["id"].split("#")[0] + "|" + hashlib.md5(p["enunciado"].encode()).hexdigest()[:8]


def peso(p):
    # mas probabilidad para examenes recientes
    return 1 + max(0, p["anio"] - 2017) / 3


def elegir(candidatas, historial, rng):
    temas = [h["tema"] for h in historial[-SEPARACION_TEMA:]]
    convs = [h["convocatoria"] for h in historial[-SEPARACION_CONV:]]
    casos = [h.get("caso") for h in historial[-SEPARACION_CASO:]]
    for estricto in (3, 2, 1, 0):  # relaja las restricciones si no hay candidatas
        pool = [p for p in candidatas
                if (estricto < 3 or p["tema"] not in temas)
                and (estricto < 2 or p["convocatoria"] not in convs)
                and (estricto < 1 or caso(p) not in casos)]
        if pool:
            return rng.choices(pool, weights=[peso(p) for p in pool])[0]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dias", type=int, default=30, help="dias de cola que deben quedar preparados")
    ap.add_argument("--subir", action="store_true", help="commit + push a GitHub al terminar")
    a = ap.parse_args()

    usadas = leer_json(USADAS, {})
    os.makedirs(COLA, exist_ok=True)
    ya_en_cola = sorted(d for d in os.listdir(COLA) if os.path.isfile(os.path.join(COLA, d, "meta.json")))

    hoy = dt.date.today()
    fin = hoy + dt.timedelta(days=a.dias)
    inicio = hoy + dt.timedelta(days=1)
    if ya_en_cola:
        inicio = max(inicio, dt.date.fromisoformat(ya_en_cola[-1]) + dt.timedelta(days=1))
    if inicio > fin:
        print(f"La cola ya llega hasta {ya_en_cola[-1]}. Nada que hacer.")
        return

    disponibles = defaultdict(list)
    descartadas = 0
    for tipo in ("test", "corta"):
        for p in cargar(tipo):
            if p["id"] in usadas:
                continue
            if problemas(p):
                descartadas += 1
                continue
            disponibles[tipo].append(p)

    historial = [leer_json(os.path.join(COLA, d, "meta.json"), {}) for d in ya_en_cola[-SEPARACION_CASO:]]
    rng = random.Random(hoy.isoformat())
    dia = inicio
    nuevas = 0
    while dia <= fin:
        tipo = PLAN_SEMANAL[dia.weekday()]
        if not disponibles[tipo]:  # se agoto un tipo: usa el otro
            tipo = "test" if tipo == "corta" else "corta"
        p = elegir(disponibles[tipo], historial, rng)
        if p is None:
            print("No quedan preguntas disponibles.")
            break
        disponibles[tipo].remove(p)

        carpeta = os.path.join(COLA, dia.isoformat())
        imagenes = [os.path.basename(r) for r in generar(p, carpeta)]
        with open(os.path.join(carpeta, "caption.txt"), "w", encoding="utf-8") as f:
            f.write(caption(p))
        meta = {
            "fecha": dia.isoformat(), "id": p["id"],
            "formato": "desarrollo" if es_desarrollo(p) else p["tipo"],
            "convocatoria": p["convocatoria"], "tema": p["tema"], "caso": caso(p),
            "imagenes": imagenes,
        }
        guardar_json(os.path.join(carpeta, "meta.json"), meta)
        usadas[p["id"]] = dia.isoformat()
        historial.append(meta)
        nuevas += 1
        print(f"{dia}  {meta['formato']:<10} {p['convocatoria']:<28} {p['pregunta'][:60]}")
        dia += dt.timedelta(days=1)

    guardar_json(USADAS, usadas)
    print(f"\n{nuevas} publicaciones nuevas. Quedan sin usar: "
          f"{len(disponibles['test'])} test y {len(disponibles['corta'])} supuestos "
          f"({descartadas} descartadas por el filtro de calidad).")

    if a.subir and nuevas:
        def git(*args):
            subprocess.run(["git", *args], cwd=REPO, check=True)
        git("pull", "--rebase", "--autostash")
        git("add", "cola", "estado/usadas.json")
        git("commit", "-m", f"Cola: {nuevas} publicaciones hasta {dia - dt.timedelta(days=1)}")
        git("push")


if __name__ == "__main__":
    main()
