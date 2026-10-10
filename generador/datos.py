"""Carga las preguntas de los Excel corregidos y descarta las que no se deben publicar."""
import glob
import os
import re

import openpyxl

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, "..", ".."))

CARPETA_TEST = os.path.join(RAIZ, "10. TEST", "20. SOLUCIONES")
CARPETA_CORTAS = os.path.join(RAIZ, "20. PREGUNTAS CORTAS", "20. SOLUCIONES")

# Limites para que el texto quepa con un tamano legible
MAX_PREGUNTA = 300
MAX_OPCION = 220
MAX_ENUNCIADO = 1500  # dos diapositivas como maximo
MAX_RESPUESTA = 1400  # respuesta modelo de las preguntas de desarrollo

# Datos que cambian con el tiempo o normas derogadas: no publicar sin revisar
DESFASADAS = [
    r"eurodiputad", r"diputados? (del|al) parlamento europeo", r"parlamento europeo est[aá] compuesto",
    r"ley 30/1992", r"ley 11/2007", r"ley 6/1997", r"ley 30/1984",
    r"real decreto legislativo 781/1986",
]

NORMAS_CORTAS = {
    "Constitución Española": "CE",
    "Ley 39/2015": "Ley 39/2015",
    "Ley 40/2015": "Ley 40/2015",
    "Ley 7/1985": "LRBRL",
    "Ley 9/2017": "LCSP",
    "Real Decreto Legislativo 2/2004": "TRLRHL",
    "Real Decreto Legislativo 5/2015": "TREBEP",
    "Estatuto de Autonomía": "EAA",
    "Ley 5/2010": "LAULA",
    "Ley 7/1999": "Ley 7/1999 Bienes EELL",
    "Ley Orgánica 3/2018": "LOPDGDD",
    "Ley 19/2013": "Ley 19/2013",
    "Ley 38/2003": "LGS",
    "Ley 31/1995": "LPRL",
    "Ley Orgánica 3/2007": "LO 3/2007",
    "Real Decreto 2568/1986": "ROF",
    "Real Decreto 500/1990": "RD 500/1990",
}

TILDES = {"Cadiz": "Cádiz", "Malaga": "Málaga", "Cordoba": "Córdoba", "Jaen": "Jaén",
          "Diputacion": "Diputación", "Almeria": "Almería", "Gines": "Ginés",
          "Ogijares": "Ogíjares", "Velez": "Vélez", "Alcala": "Alcalá"}


def limpiar(t):
    t = "" if t is None else str(t)
    t = t.replace("/n", "\n").strip()
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{3,}", "\n\n", t)


def acortar(t, maximo):
    if len(t) <= maximo:
        return t
    corte = t[:maximo].rsplit(" ", 1)[0]
    punto = corte.rfind(". ")
    if punto > maximo * 0.5:
        return corte[:punto + 1]
    return corte + "…"


def tildar(t):
    for k, v in TILDES.items():
        t = re.sub(r"\b" + k + r"\b", v, t)
    return t


def norma_corta(n):
    for k, v in NORMAS_CORTAS.items():
        if k.lower() in n.lower():
            return v
    return n if len(n) <= 30 else ""


def nombre_convocatoria(conv):
    conv = re.sub(r"\s+(PC|SP|TEST|SP TEST|PC TEST)$", "", conv.strip())
    m = re.match(r"^(\d{4}) - (.+)$", conv)
    if m:
        conv = f"{m.group(2)} {m.group(1)}"
    conv = re.sub(r"\s*\(.*?\)", "", conv)  # quita "(Concurso Oposición)" etc.
    lugar, _, anio = conv.rpartition(" ")
    if anio.isdigit() and len(anio) == 4:
        # corta coletillas: "SEGUNDO EJERCICIO supuesto...", "2" (segundo examen del año)...
        lugar = re.split(r"\s+(?:primer|segundo|tercer|supuesto|cuestionario|plantilla|promoci|interino|\d)",
                         lugar, maxsplit=1, flags=re.I)[0]
        if lugar.isupper():
            lugar = re.sub(r"(?<= )(De|La|Del|Las|Los|Y|El)(?= )", lambda x: x.group(1).lower(), lugar.title())
        conv = f"{lugar} {anio}"
    menores = {"de", "la", "del", "las", "los", "y", "el"}
    conv = " ".join(w if (i and w.lower() in menores) else w[:1].upper() + w[1:]
                    for i, w in enumerate(conv.split()))
    return tildar(conv.strip())


def _fila_a_pregunta(r, tipo, origen):
    articulo = r.get("Artículo num.", "")
    if articulo and not articulo.lower().startswith("art"):
        articulo = "Art. " + articulo
    articulo = articulo.replace("Artículo", "Art.")
    norma = r.get("Normativa", "")
    conv = r.get("Convocatoria", "") or os.path.splitext(os.path.basename(origen.split("#")[0]))[0]
    return {
        "id": origen,
        "tipo": tipo,  # "test" | "corta"
        "enunciado": r.get("Enunciado", ""),
        "pregunta": re.sub(r"^RESERVA\s*\d*\s*[.:-]?\s*", "", r.get("Pregunta", ""), flags=re.I),
        "opciones": [r.get(f"Opción {l}", "") for l in "ABCD"],
        "correcta": r.get("Respuesta Correcta", "").strip().upper()[:1],
        "justificacion": r.get("Justificación", ""),
        "justificacion_incorrecta": r.get("Justificación Incorrecta", ""),
        "literal": r.get("Artículo Literal", ""),
        "articulo": articulo,
        "norma": norma,
        "norma_corta": norma_corta(norma) if norma else "",
        "tema": r.get("Tema", ""),
        "convocatoria": nombre_convocatoria(conv),
        "anio": int(m.group(1)) if (m := re.search(r"(20\d\d)", conv)) else 0,
    }


def _leer_excel(ruta, tipo):
    ws = openpyxl.load_workbook(ruta, read_only=True).worksheets[0]
    filas = ws.iter_rows(values_only=True)
    canon = {"enunciado": "Enunciado"}
    cab = [canon.get(limpiar(c).lower(), limpiar(c)) for c in next(filas)]
    base = os.path.relpath(ruta, RAIZ).replace("\\", "/")
    for n, val in enumerate(filas, start=2):
        r = {c: limpiar(v) for c, v in zip(cab, val)}
        if r.get("Pregunta"):
            yield _fila_a_pregunta(r, tipo, f"{base}#{n}")


def es_desarrollo(p):
    return p["tipo"] == "corta" and not any(p["opciones"])


def problemas(p):
    """Lista de motivos por los que una pregunta NO debe publicarse (vacia = OK)."""
    mal = []
    ops = [o for o in p["opciones"] if o]
    if es_desarrollo(p):
        # pregunta abierta: la "justificacion" es la respuesta modelo
        if len(p["justificacion"]) < 80:
            mal.append("respuesta modelo vacía o insuficiente")
        if len(p["justificacion"]) > MAX_RESPUESTA:
            mal.append("respuesta modelo demasiado larga para el carrusel")
    else:
        if len(ops) < 3:
            mal.append("menos de 3 opciones")
        if p["correcta"] not in "ABCD" or not p["correcta"]:
            mal.append("sin respuesta correcta")
        elif not p["opciones"]["ABCD".index(p["correcta"])]:
            mal.append("la respuesta correcta apunta a una opción vacía")
        if not p["justificacion"]:
            mal.append("sin justificación")
    todo = " ".join([p["enunciado"], p["pregunta"], *p["opciones"]])
    if re.search(r"opci[oó]n omitida|\[.*?(ilegible|omitid).*?\]|\?\?", todo, re.I):
        mal.append("texto incompleto en el original")
    # años imposibles (2030-2999) que no son el numero de una norma tipo "2568/1986"
    if re.search(r"\b(20[3-9]\d|2[1-9]\d\d)\b(?!/)", " ".join([p["pregunta"], *p["opciones"]])):
        mal.append("año sospechoso (posible errata)")
    for patron in DESFASADAS:
        if re.search(patron, todo, re.I):
            mal.append(f"dato que puede estar desfasado ({patron})")
            break
    if len(p["pregunta"]) > MAX_PREGUNTA:
        mal.append("pregunta demasiado larga para el carrusel")
    if any(len(o) > MAX_OPCION for o in ops):
        mal.append("opción demasiado larga para el carrusel")
    if p["tipo"] == "corta" and len(p["enunciado"]) > MAX_ENUNCIADO:
        mal.append("enunciado demasiado largo para el carrusel")
    if p["tipo"] == "corta" and len(p["enunciado"]) < 60:
        mal.append("enunciado vacío o insuficiente")
    return mal


def cargar(tipo):
    carpeta = CARPETA_TEST if tipo == "test" else CARPETA_CORTAS
    for ruta in sorted(glob.glob(os.path.join(carpeta, "*.xlsx"))):
        if os.path.basename(ruta).startswith("~$"):
            continue
        yield from _leer_excel(ruta, tipo)


def informe():
    """Resumen de cuantas preguntas son publicables y por que se descartan las demas."""
    from collections import Counter
    for tipo in ("test", "corta"):
        total, ok, motivos = 0, 0, Counter()
        for p in cargar(tipo):
            total += 1
            m = problemas(p)
            if m:
                motivos[m[0].split(" (")[0]] += 1
            else:
                ok += 1
        print(f"\n{tipo.upper()}: {ok} publicables de {total}")
        for k, v in motivos.most_common():
            print(f"   descartadas por {k}: {v}")


if __name__ == "__main__":
    informe()
