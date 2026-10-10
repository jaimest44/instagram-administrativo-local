"""Dibuja los carruseles de Instagram (1080x1350) a partir de una pregunta de datos.py.

Tres formatos:
  - test       pregunta · solucion · trampa · cta
  - corta      caso (1-2) · pregunta · solucion · trampa · cta      (supuesto con opciones)
  - desarrollo pregunta · respuesta modelo (1-2) · ley · cta         (supuesto sin opciones)

Prueba rapida:
    python carrusel.py "10. TEST/20. SOLUCIONES/2022 - Cadiz.xlsx#10"
"""
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

from datos import RAIZ, acortar, es_desarrollo

LOGO = os.path.join(RAIZ, "30. MEDIA", "LOGO", "ChatGPT Image 23 ago 2026, 10_57_46.png")
URL_APP = "app.administrativolocal.com"

W, H = 1080, 1350
M = 80  # margen lateral
LIMITE = H - 160  # por debajo va el pie
MIN_CASO = 250  # enunciados mas cortos son solo una introduccion: no merecen diapositiva

# Paleta tomada del logo
NAVY = (11, 21, 51)
AZUL = (0, 153, 255)
VERDE = (0, 102, 63)
VERDE_CLARO = (107, 170, 142)
FONDO = (243, 246, 251)
BLANCO = (255, 255, 255)
GRIS = (90, 100, 120)
BORDE = (220, 226, 236)
ROJO = (200, 55, 55)

FUENTES = "C:/Windows/Fonts/"
TIT = "ARIALNB.TTF"   # condensada, como el logo
TXT = "segoeui.ttf"
TXT_B = "segoeuib.ttf"
TXT_I = "segoeuii.ttf"

_cache_fuentes = {}


def fuente(nombre, tam):
    clave = (nombre, tam)
    if clave not in _cache_fuentes:
        _cache_fuentes[clave] = ImageFont.truetype(FUENTES + nombre, tam)
    return _cache_fuentes[clave]


# ---------------------------------------------------------------- utilidades de texto

def envolver(draw, texto, f, ancho):
    """Parte el texto en lineas que caben en `ancho` pixeles (respeta saltos de linea)."""
    lineas = []
    for parrafo in texto.split("\n"):
        actual = ""
        for p in parrafo.split():
            prueba = (actual + " " + p).strip()
            if draw.textlength(prueba, font=f) <= ancho:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = p
        lineas.append(actual)
    return lineas


def ajustar(draw, texto, nombre, ancho, alto, maximo, minimo=24, interlineado=1.25):
    """Mayor tamano de fuente con el que el texto cabe en la caja."""
    for tam in range(maximo, minimo - 1, -2):
        f = fuente(nombre, tam)
        lineas = envolver(draw, texto, f, ancho)
        if len(lineas) * tam * interlineado <= alto:
            return f, lineas, tam
    f = fuente(nombre, minimo)
    return f, envolver(draw, texto, f, ancho), minimo


def escribir(draw, xy, lineas, f, tam, color, interlineado=1.25):
    x, y = xy
    for ln in lineas:
        draw.text((x, y), ln, font=f, fill=color)
        y += int(tam * interlineado)
    return y


def paginar(texto, nombre, tam, ancho, alto, interlineado=1.4):
    """Reparte un texto largo en paginas que caben en (ancho, alto) a tamano fijo."""
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lineas = envolver(d, texto, fuente(nombre, tam), ancho)
    por_pag = max(1, int(alto // (tam * interlineado)))
    paginas = [lineas[i:i + por_pag] for i in range(0, len(lineas), por_pag)]
    # evita que una pagina empiece con una linea en blanco
    return [[ln for ln in pg] if pg and pg[0] else pg[1:] for pg in paginas]


def sin_mayusculas(t):
    """Pasa a tipo frase los textos escritos enteros en mayusculas."""
    letras = [c for c in t if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.8:
        t = t.lower()
        t = re.sub(r"(^|[.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), t)
        t = re.sub(r"\b(lcsp|lrbrl|ce|trlrhl|trebep|lbrl|rof|i{1,3}|iv|vi{0,3}|ix|x)\b", lambda m: m.group(1).upper(), t)
    return t


def formatear_respuesta(t):
    """Pone cada apartado a) b) c) / 1. 2. 3. en su propia linea."""
    t = re.sub(r"\s+(?=(?:[a-h]\)|\d{1,2}\.\s|[-•]\s)\s*[A-ZÁÉÍÓÚ])", "\n", t)
    return t.strip()


def frase_relevante(literal, respuesta):
    """Del articulo literal, el apartado que mas palabras comparte con la respuesta."""
    partes = [x.strip() for x in re.split(r"\n+|(?<=\.)\s+(?=\d+\.\s)", literal) if x.strip()]
    if not partes:
        return literal
    clave = set(w.lower() for w in re.findall(r"\w{4,}", respuesta))
    return max(partes, key=lambda x: len(clave & set(w.lower() for w in re.findall(r"\w{4,}", x))))


# ---------------------------------------------------------------- piezas comunes

_logo = None


def logo_recortado():
    """Parte de texto del logo (sin las flechas), con fondo transparente."""
    global _logo
    if _logo is not None:
        return _logo
    img = Image.open(LOGO).convert("RGB")
    gris = img.convert("L")
    w, h = img.size
    filas = [gris.crop((0, y, w, y + 1)).getextrema()[0] < 200 for y in range(h)]
    bandas, ini = [], None
    for y, c in enumerate(filas + [False]):
        if c and ini is None:
            ini = y
        if not c and ini is not None:
            bandas.append((ini, y))
            ini = None
    # la ultima banda es el simbolo de flechas
    corte = bandas[-2][1] if len(bandas) > 1 else h
    img = img.crop((0, bandas[0][0], w, corte))
    caja = img.convert("L").point(lambda v: 255 if v < 200 else 0).getbbox()
    img = img.crop(caja).convert("RGBA")
    px = [(r, g, b, max(0, min(255, int((255 - min(r, g, b)) * 4)))) for r, g, b, _ in img.getdata()]
    img.putdata(px)
    alto = 96
    _logo = img.resize((int(img.width * alto / img.height), alto), Image.LANCZOS)
    return _logo


def lienzo(oscuro=False):
    img = Image.new("RGB", (W, H), NAVY if oscuro else FONDO)
    d = ImageDraw.Draw(img)
    logo = logo_recortado()
    if oscuro:
        pad = 18
        d.rounded_rectangle((M - pad, 50 - pad, M + logo.width + pad, 50 + logo.height + pad),
                            radius=18, fill=BLANCO)
    img.paste(logo, (M, 50), logo)
    x, y = W - M - 50, 52
    d.line((x, y, x + 32, y + 32, x, y + 64), fill=BLANCO if oscuro else VERDE, width=12, joint="curve")
    img.oscuro = oscuro
    return img, d


def pie(d, texto, oscuro=False):
    d.text((M, H - 95), texto, font=fuente(TXT_B, 30), fill=BLANCO if oscuro else GRIS)


def puntos(img, actual, total):
    d = ImageDraw.Draw(img)
    oscuro = getattr(img, "oscuro", False)
    r, sep = 7, 26
    x0 = W - M - (total - 1) * sep
    for i in range(total):
        c = AZUL if i == actual else ((80, 90, 120) if oscuro else (200, 208, 222))
        cx = x0 + i * sep
        d.ellipse((cx - r, H - 78 - r, cx + r, H - 78 + r), fill=c)


def badge(d, xy, texto, color_fondo, color_texto=BLANCO, tam=28):
    f = fuente(TXT_B, tam)
    x, y = xy
    w = d.textlength(texto, font=f)
    d.rounded_rectangle((x, y, x + w + 44, y + tam + 26), radius=(tam + 26) // 2, fill=color_fondo)
    d.text((x + 22, y + 10), texto, font=f, fill=color_texto)
    return y + tam + 26


def titulo(d, texto, color, y=175, tam=96):
    d.text((M, y), texto, font=fuente(TIT, tam), fill=color)
    return y + int(tam * 1.15)


def caja_texto(d, y, lineas, f, tam, color=NAVY, etiqueta=None, barra=None, interlineado=1.4):
    """Tarjeta blanca con texto. Devuelve la y final."""
    extra_top = 62 if etiqueta else 35
    alto = len(lineas) * int(tam * interlineado) + extra_top + 35
    d.rounded_rectangle((M, y, W - M, y + alto), radius=26, fill=BLANCO, outline=BORDE, width=3)
    if barra:
        d.rectangle((M, y + 20, M + 8, y + alto - 20), fill=barra)
    if etiqueta:
        d.text((M + 40, y + 22), etiqueta, font=fuente(TXT_B, 24), fill=AZUL)
    escribir(d, (M + 40, y + extra_top), lineas, f, tam, color, interlineado)
    return y + alto


def tarjeta_opcion(d, caja, letra, texto, estado="normal"):
    """estado: normal | correcta | incorrecta"""
    x0, y0, x1, y1 = caja
    fondo, borde, circ, txt = BLANCO, BORDE, NAVY, NAVY
    if estado == "correcta":
        fondo, borde, circ, txt = (232, 245, 238), VERDE, VERDE, NAVY
    elif estado == "incorrecta":
        fondo, borde, circ, txt = (250, 250, 252), (230, 232, 238), (190, 195, 205), (160, 165, 178)
    d.rounded_rectangle(caja, radius=22, fill=fondo, outline=borde, width=3)
    r = 30
    cx, cy = x0 + 28 + r, (y0 + y1) // 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=circ)
    d.text((cx, cy), letra, font=fuente(TXT_B, 32), fill=BLANCO, anchor="mm")
    tx = cx + r + 26
    derecha = x1 - (90 if estado == "incorrecta" else 24)
    f, lineas, tam = ajustar(d, texto, TXT_B if estado == "correcta" else TXT,
                             derecha - tx, y1 - y0 - 24, 34, 20, 1.2)
    alto_txt = len(lineas) * int(tam * 1.2)
    escribir(d, (tx, cy - alto_txt // 2 - 4), lineas, f, tam, txt, 1.2)
    if estado == "incorrecta":
        ax = x1 - 50
        d.line((ax - 16, cy - 16, ax + 16, cy + 16), fill=ROJO, width=7)
        d.line((ax - 16, cy + 16, ax + 16, cy - 16), fill=ROJO, width=7)


def etiqueta_examen(p):
    tipo = "PREGUNTA REAL" if p["tipo"] == "test" else "SUPUESTO PRÁCTICO REAL"
    return f"{tipo} · {p['convocatoria'].upper()}"


# ---------------------------------------------------------------- diapositivas

def slides_caso(p):
    """El enunciado del supuesto, en 1 o 2 diapositivas."""
    tam = 32
    paginas = paginar(p["enunciado"], TXT, tam, W - 2 * M - 80, LIMITE - 400)
    if len(paginas) > 2:  # no deberia pasar por el filtro de datos.py; por si acaso
        tam = 28
        paginas = paginar(p["enunciado"], TXT, tam, W - 2 * M - 80, LIMITE - 400)[:2]
    imgs = []
    for i, lineas in enumerate(paginas):
        img, d = lienzo()
        y = badge(d, (M, 175), etiqueta_examen(p), AZUL)
        y = titulo(d, "EL CASO" if i == 0 else "EL CASO (SIGUE)", NAVY, y + 25, 80) + 10
        caja_texto(d, y, lineas, fuente(TXT, tam), tam, barra=AZUL)
        ultima = i == len(paginas) - 1
        pie(d, "Lee el caso y desliza para la pregunta  →" if ultima else "Sigue leyendo  →")
        imgs.append(img)
    return imgs


def slide_pregunta(p):
    img, d = lienzo()
    y = badge(d, (M, 175), etiqueta_examen(p), AZUL)
    opciones = [(l, t) for l, t in zip("ABCD", p["opciones"]) if t]
    largo_ops = sum(len(t) for _, t in opciones)
    alto_preg = 270 if largo_ops < 400 else 210
    f, lineas, tam = ajustar(d, p["pregunta"], TIT, W - 2 * M, alto_preg, 64, 36, 1.15)
    y = escribir(d, (M, y + 35), lineas, f, tam, NAVY, 1.15) + 30
    hueco = 20
    alto = min(170, (LIMITE + 10 - y - hueco * (len(opciones) - 1)) // len(opciones))
    for letra, texto in opciones:
        tarjeta_opcion(d, (M, y, W - M, y + alto), letra, texto)
        y += alto + hueco
    pie(d, "Comenta tu respuesta   ·   Desliza para la solución  →")
    return img


def slide_solucion(p):
    img, d = lienzo()
    y = titulo(d, "SOLUCIÓN", VERDE)
    y += 15
    idx = "ABCD".index(p["correcta"])
    tarjeta_opcion(d, (M, y, W - M, y + 190), p["correcta"], p["opciones"][idx], "correcta")
    y += 225
    if p["articulo"] or p["norma_corta"]:
        txt = " · ".join(x for x in (p["articulo"], p["norma_corta"]) if x)
        y = badge(d, (M, y), acortar(txt, 50), NAVY) + 28
    hay_literal = bool(p["literal"])
    texto = sin_mayusculas(acortar(p["justificacion"], 360 if hay_literal else 650))
    alto_just = 290 if hay_literal else LIMITE - y
    f, lineas, tam = ajustar(d, texto, TXT, W - 2 * M, alto_just, 36, 24, 1.35)
    y = escribir(d, (M, y), lineas, f, tam, NAVY, 1.35) + 28
    if hay_literal and LIMITE - y > 200:
        literal = acortar(frase_relevante(p["literal"], p["opciones"][idx]), 330)
        fl, ll, tl = ajustar(d, "«" + literal + "»", TXT_I, W - 2 * M - 80, LIMITE - y - 100, 32, 22, 1.35)
        caja_texto(d, y, ll, fl, tl, GRIS, etiqueta="LO QUE DICE LA LEY", interlineado=1.35)
    pie(d, "¿Acertaste? Guárdalo para repasar")
    return img


def slide_trampa(p):
    img, d = lienzo()
    y = titulo(d, "LA TRAMPA", ROJO)
    d.text((M, y - 5), "Por qué fallan las demás opciones", font=fuente(TXT_B, 36), fill=GRIS)
    y += 75
    malas = [(l, t) for l, t in zip("ABCD", p["opciones"]) if t and l != p["correcta"]]
    alto_op = 118 if len(malas) == 3 else 140
    for l, t in malas:
        tarjeta_opcion(d, (M, y, W - M, y + alto_op), l, t, "incorrecta")
        y += alto_op + 16
    y += 20
    if p["justificacion_incorrecta"]:
        texto = acortar(p["justificacion_incorrecta"], 420)
        f, lineas, tam = ajustar(d, texto, TXT, W - 2 * M - 80, LIMITE - y - 80, 34, 22, 1.4)
        caja_texto(d, y, lineas, f, tam, barra=ROJO)
    pie(d, "Así es como lo preguntan en el examen")
    return img


def slide_pregunta_abierta(p):
    img, d = lienzo()
    y = badge(d, (M, 175), etiqueta_examen(p), AZUL)
    y = badge(d, (M, y + 18), "PREGUNTA DE DESARROLLO", NAVY, tam=24)
    f, lineas, tam = ajustar(d, p["pregunta"], TIT, W - 2 * M, 520, 76, 40, 1.15)
    y = escribir(d, (M, y + 45), lineas, f, tam, NAVY, 1.15) + 50
    d.line((M, y, M + 300, y), fill=VERDE_CLARO, width=6)
    y += 50
    texto = ("¿Cómo lo responderías en el examen?\n"
             "Escribe los puntos clave en comentarios y desliza para ver la respuesta modelo.")
    f2, l2, t2 = ajustar(d, texto, TXT, W - 2 * M, LIMITE - y, 38, 26, 1.4)
    escribir(d, (M, y), l2, f2, t2, GRIS, 1.4)
    pie(d, "Desliza para la respuesta modelo  →")
    return img


def slides_respuesta(p):
    texto = formatear_respuesta(sin_mayusculas(p["justificacion"]))
    tam = 33
    paginas = paginar(texto, TXT, tam, W - 2 * M - 80, LIMITE - 420)
    if len(paginas) > 2:
        tam = 29
        paginas = paginar(texto, TXT, tam, W - 2 * M - 80, LIMITE - 420)
    imgs = []
    for i, lineas in enumerate(paginas[:3]):
        img, d = lienzo()
        y = titulo(d, "RESPUESTA MODELO", VERDE, tam=88)
        if p["articulo"] or p["norma_corta"]:
            txt = " · ".join(x for x in (p["articulo"], p["norma_corta"]) if x)
            y = badge(d, (M, y + 10), acortar(txt, 50), NAVY) + 28
        else:
            y += 20
        caja_texto(d, y, lineas, fuente(TXT, tam), tam, barra=VERDE)
        ultima = i == min(len(paginas), 3) - 1
        pie(d, "Guárdalo para repasar" if ultima else "Sigue  →")
        imgs.append(img)
    return imgs


def slide_ley(p):
    img, d = lienzo()
    y = titulo(d, "LO QUE DICE LA LEY", AZUL, tam=88)
    if p["articulo"] or p["norma"]:
        cab = ", ".join(x for x in (p["articulo"], acortar(p["norma"], 90)) if x)
        f, ll, t = ajustar(d, cab, TXT_B, W - 2 * M, 120, 34, 26, 1.3)
        y = escribir(d, (M, y + 5), ll, f, t, NAVY, 1.3) + 25
    literal = acortar(p["literal"], 900)
    fl, ll, tl = ajustar(d, "«" + literal + "»", TXT_I, W - 2 * M - 80, LIMITE - y - 80, 34, 22, 1.4)
    caja_texto(d, y, ll, fl, tl, GRIS, barra=AZUL)
    pie(d, "Memoriza el literal: es lo que preguntan")
    return img


def slide_cta(p):
    img, d = lienzo(oscuro=True)
    conv = p["convocatoria"].upper() + "."
    if p["tipo"] == "test":
        lineas = [("ESTA CAYÓ EN", BLANCO), (conv, AZUL), ("¿CUÁNTAS MÁS", BLANCO), ("ACERTARÍAS?", BLANCO)]
        sub = ("Entrena con preguntas oficiales de Ayuntamientos andaluces, "
               "justificadas artículo a artículo. Test por temas, supuestos prácticos y duelos.")
        pie_txt = "Síguenos: una pregunta oficial cada día"
    else:
        lineas = [("ESTE SUPUESTO", BLANCO), ("CAYÓ EN", BLANCO), (conv, AZUL), ("¿LO TENÍAS?", BLANCO)]
        sub = ("Practica supuestos prácticos reales de Ayuntamientos andaluces, "
               "resueltos paso a paso y con la norma aplicable.")
        pie_txt = "Síguenos: supuestos reales cada semana"
    y = 250
    for texto, color in lineas:
        f = fuente(TIT, 92)
        if d.textlength(texto, font=f) > W - 2 * M:
            f, _, _ = ajustar(d, texto, TIT, W - 2 * M, 100, 92, 50, 1.0)
        d.text((M, y), texto, font=f, fill=color)
        y += 102
    d.line((M, y + 25, M + 420, y + 25), fill=VERDE_CLARO, width=6)
    y += 70
    f2, l2, t2 = ajustar(d, sub, TXT, W - 2 * M, 200, 40, 28, 1.35)
    y = escribir(d, (M, y), l2, f2, t2, (210, 220, 240), 1.35) + 50
    fb = fuente(TXT_B, 46)
    bw = d.textlength(URL_APP, font=fb) + 100
    bx = (W - bw) // 2
    d.rounded_rectangle((bx, y, bx + bw, y + 110), radius=55, fill=VERDE)
    d.text((W // 2, y + 55), URL_APP, font=fb, fill=BLANCO, anchor="mm")
    d.text((W // 2, y + 165), "Enlace en la bio", font=fuente(TXT_B, 34), fill=VERDE_CLARO, anchor="mm")
    pie(d, pie_txt, oscuro=True)
    return img


# ---------------------------------------------------------------- montaje

def construir(p):
    if es_desarrollo(p):
        imgs = slides_caso(p) if len(p["enunciado"]) >= MIN_CASO else []
        imgs += [slide_pregunta_abierta(p), *slides_respuesta(p)]
        if p["literal"]:
            imgs.append(slide_ley(p))
    else:
        imgs = slides_caso(p) if p["tipo"] == "corta" and len(p["enunciado"]) >= MIN_CASO else []
        imgs += [slide_pregunta(p), slide_solucion(p)]
        if len(p["justificacion_incorrecta"]) >= 40:
            imgs.append(slide_trampa(p))
    imgs.append(slide_cta(p))
    for i, img in enumerate(imgs):
        puntos(img, i, len(imgs))
    return imgs


def generar(p, salida):
    """Guarda las diapositivas como JPEG (Instagram solo admite JPEG) y devuelve las rutas."""
    os.makedirs(salida, exist_ok=True)
    rutas = []
    for i, img in enumerate(construir(p), 1):
        r = os.path.join(salida, f"{i:02d}.jpg")
        img.save(r, "JPEG", quality=92, optimize=True, progressive=True)
        rutas.append(r)
    return rutas


if __name__ == "__main__":
    from datos import cargar

    objetivo = sys.argv[1] if len(sys.argv) > 1 else "10. TEST/20. SOLUCIONES/2022 - Cadiz.xlsx#10"
    tipo = "corta" if "PREGUNTAS CORTAS" in objetivo else "test"
    p = next(x for x in cargar(tipo) if x["id"] == objetivo)
    salida = os.path.join(RAIZ, "40. INSTAGRAM", "salida", "muestra_" + p["tipo"] + ("_desarrollo" if es_desarrollo(p) else ""))
    for r in generar(p, salida):
        print(r)
