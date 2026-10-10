"""Texto (caption) de cada publicacion.

Reglas: la primera linea es lo unico que se ve antes del "... mas", asi que lleva el gancho.
Una sola peticion de accion, el enlace a la app y pocos hashtags (3-5) que describan el tema.
Sin rayas largas ni frases de relleno: tiene que sonar a persona, no a plantilla.
"""
import hashlib
import re

from datos import acortar, es_desarrollo

URL_APP = "app.administrativolocal.com"

GANCHOS_TEST = [
    "¿Sabrías responder esta pregunta del examen de {conv}?",
    "Esta pregunta cayó en {conv}. ¿La aciertas sin mirar?",
    "Pregunta oficial de {conv}. Mucha gente falla aquí.",
    "Si te presentas a Administrativo en Andalucía, esta te puede caer. Salió en {conv}.",
    "{conv}: una pregunta de las que deciden una plaza.",
]

GANCHOS_CORTA = [
    "Supuesto práctico real de {conv}. ¿Cómo lo resolverías?",
    "Este caso cayó en el examen de {conv}. ¿Lo tenías?",
    "Supuesto de {conv}: lee el caso y elige antes de mirar la solución.",
]

GANCHOS_DESARROLLO = [
    "Pregunta de desarrollo del examen de {conv}. ¿Qué pondrías tú?",
    "Así se responde una pregunta corta del supuesto de {conv}.",
    "Esto preguntaron en {conv}. Te dejamos la respuesta modelo.",
]

PIDE_TEST = [
    "Deja tu respuesta en comentarios (A, B, C o D) y desliza para ver la solución con el artículo exacto.",
    "Responde en comentarios antes de deslizar. En la segunda imagen tienes la solución y lo que dice la ley.",
]
PIDE_DESARROLLO = [
    "Escribe en comentarios los puntos clave que pondrías y desliza para comparar con la respuesta modelo.",
]

CIERRES = [
    "Guárdalo para tu próximo repaso.\n\nMás preguntas oficiales de Ayuntamientos andaluces, justificadas una a una, en {url} (enlace en la bio).",
    "Guárdalo y compártelo con quien esté opositando contigo.\n\nPractica con exámenes oficiales de Andalucía en {url} (enlace en la bio).",
    "Si te ha servido, guárdalo.\n\nTest por temas, supuestos prácticos reales y duelos en {url} (enlace en la bio).",
]

# Hashtag de tema segun la norma
TEMAS = [
    (r"constituci", "#constitucionespañola"),
    (r"39/2015", "#ley39"),
    (r"40/2015", "#ley40"),
    (r"7/1985|bases del r[eé]gimen local|2568/1986", "#regimenlocal"),
    (r"9/2017|contratos del sector", "#contratacionpublica"),
    (r"2/2004|haciendas locales|presupuest", "#haciendaslocales"),
    (r"5/2015|empleado p[uú]blico|funci[oó]n p[uú]blica", "#trebep"),
    (r"estatuto de autonom", "#estatutoandalucia"),
    (r"3/2018|protecci[oó]n de datos", "#protecciondedatos"),
    (r"19/2013|transparencia", "#transparencia"),
    (r"38/2003|subvenci", "#subvenciones"),
    (r"uni[oó]n europea|tratado", "#unioneuropea"),
]
FIJOS = ["#oposicionesandalucia", "#administrativo", "#oposiciones"]


def _elige(lista, semilla, n=0):
    h = int(hashlib.md5(f"{semilla}{n}".encode()).hexdigest(), 16)
    return lista[h % len(lista)]


def hashtags(p):
    texto = " ".join([p["norma"], p["tema"], p["pregunta"]])
    tags = list(FIJOS)
    for patron, tag in TEMAS:
        if re.search(patron, texto, re.I):
            tags.append(tag)
            break
    tags.append("#supuestopractico" if p["tipo"] == "corta" else "#testoposiciones")
    return " ".join(tags)


def caption(p):
    sid = p["id"]
    conv = p["convocatoria"]
    if es_desarrollo(p):
        gancho, pide = _elige(GANCHOS_DESARROLLO, sid), _elige(PIDE_DESARROLLO, sid, 1)
    elif p["tipo"] == "corta":
        gancho, pide = _elige(GANCHOS_CORTA, sid), _elige(PIDE_TEST, sid, 1)
    else:
        gancho, pide = _elige(GANCHOS_TEST, sid), _elige(PIDE_TEST, sid, 1)

    partes = [gancho.format(conv=conv), acortar(p["pregunta"], 400)]
    if p["norma"]:
        partes.append(f"Norma: {acortar(p['norma'], 120)}")
    partes += [pide, _elige(CIERRES, sid, 2).format(url=URL_APP), hashtags(p)]
    texto = "\n\n".join(partes)
    # nada de rayas largas
    texto = texto.replace("—", ",").replace("–", "-")
    return texto[:2200]


if __name__ == "__main__":
    from datos import cargar
    p = next(x for x in cargar("test") if x["id"].endswith("2022 - Cadiz.xlsx#10"))
    print(caption(p))
