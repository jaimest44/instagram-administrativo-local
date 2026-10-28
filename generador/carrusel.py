"""Dibuja los carruseles de @administrativo_local_andalucia (1080x1350, mismo formato que Local Andalucía).

Formatos:
  - test        pregunta · solucion · trampa · cta
  - corta       caso (1-2) · pregunta · solucion · trampa · cta          (supuesto con opciones)
  - desarrollo  caso (1-2) · pregunta · respuesta modelo (1-3) · cta     (supuesto sin opciones)
  - infraccion  conducta + "¿leve, grave o muy grave?" · solucion · cta

Prueba rapida:
    python carrusel.py "20. RECURSOS IA/CODIFICADO/TRÁFICO COMPLETO - CODIFICADO.xlsx#4"
"""
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

from datos import RAIZ, acortar, es_desarrollo

LOGO = os.path.join(RAIZ, "30. MEDIA", "LOGO", "ChatGPT Image 23 ago 2026, 10_57_46.png")
URL_APP = "app.administrativolocal.com"
USUARIO = "@administrativo_local_andalucia"

W, H = 1080, 1350
M = 70  # margen lateral
TOP = 330  # donde empieza el contenido (debajo de la cabecera)
LIMITE = H - 150  # por debajo va el pie
MIN_CASO = 350  # mas corto: el caso va en la diapositiva de la pregunta (nunca se omite)

# Paleta de la marca (logo y posts anteriores)
FONDO = (11, 37, 69)        # azul marino de la infografia (#0b2545)
FONDO_ALTO = (13, 44, 85)   # degradado: arriba (#0d2c55)
FONDO_BAJO = (8, 26, 51)    # degradado: abajo (#081a33)
TARJETA = (24, 50, 84)      # tarjeta translucida sobre el fondo
BORDE = (58, 86, 124)
CIAN = (56, 182, 255)  # azul de la marca Administrativo
BLANCO = (255, 255, 255)
TEXTO = (226, 230, 242)
GRIS = (150, 160, 192)
PILDORA = (214, 218, 226)
VERDE = (52, 199, 120)
NARANJA = (245, 166, 35)
ROJO = (235, 87, 87)
MORADO = (176, 146, 255)
AMBAR = (242, 183, 5)       # antetitulos (#f2b705)
NAVY_TXT = (11, 37, 69)

MARCA = "ADMINISTRATIVO"     # pastilla de la cabecera
LISTA_CTA = ["Exámenes oficiales de Ayuntamientos andaluces", "Cada pregunta justificada con su artículo",
             "Supuestos prácticos resueltos paso a paso", "Plan completo: 9,99 €/mes, precio congelado"]

GRAVEDAD = {"leve": VERDE, "grave": NARANJA, "muy grave": ROJO}

FUENTES = "C:/Windows/Fonts/"
TIT = "bahn:Bold Condensed"    # titulos y preguntas (Bahnschrift, como la infografia)
DISPLAY = "bahn:Bold"         # cifras y botones
SEMI = "bahn:SemiBold"        # antetitulos y etiquetas
TXT = "segoeui.ttf"
TXT_B = "segoeuib.ttf"
TXT_SB = "seguisb.ttf"
TXT_I = "segoeuii.ttf"

_cache = {}


def fuente(nombre, tam):
    """Admite "bahn:<variante>" para Bahnschrift (fuente variable de Windows)."""
    if (nombre, tam) not in _cache:
        try:
            if nombre.startswith("bahn:"):
                f = ImageFont.truetype(FUENTES + "bahnschrift.ttf", tam)
                f.set_variation_by_name(nombre[5:])
            else:
                f = ImageFont.truetype(FUENTES + nombre, tam)
        except OSError:
            f = ImageFont.truetype(FUENTES + TXT_B, tam)
        _cache[(nombre, tam)] = f
    return _cache[(nombre, tam)]


# ---------------------------------------------------------------- texto

def envolver(draw, texto, f, ancho):
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


def ajustar(draw, texto, nombre, ancho, alto, maximo, minimo=22, interlineado=1.3):
    for tam in range(maximo, minimo - 1, -2):
        f = fuente(nombre, tam)
        lineas = envolver(draw, texto, f, ancho)
        if len(lineas) * tam * interlineado <= alto:
            return f, lineas, tam
    f = fuente(nombre, minimo)
    return f, envolver(draw, texto, f, ancho), minimo


def escribir(draw, xy, lineas, f, tam, color, interlineado=1.3):
    x, y = xy
    for ln in lineas:
        draw.text((x, y), ln, font=f, fill=color)
        y += int(tam * interlineado)
    return y


def paginar(texto, nombre, tam, ancho, alto, interlineado=1.4):
    d = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lineas = envolver(d, texto, fuente(nombre, tam), ancho)
    por_pag = max(1, int(alto // (tam * interlineado)))
    paginas = [lineas[i:i + por_pag] for i in range(0, len(lineas), por_pag)]
    return [pg if pg and pg[0] else pg[1:] for pg in paginas]


def sin_mayusculas(t):
    """Pasa a tipo frase los textos escritos enteros en mayusculas."""
    letras = [c for c in t if c.isalpha()]
    if letras and sum(c.isupper() for c in letras) / len(letras) > 0.8:
        t = t.lower()
        t = re.sub(r"(^|[.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), t)
        t = re.sub(r"\b(dgt|itv|vtc|cp|ce|ue|sp|lsv|rgc|ss\.ss|i{1,3}|iv|vi{0,3}|ix|x)\b",
                   lambda m: m.group(1).upper(), t)
    return t


def formatear_respuesta(t):
    t = re.sub(r"\s+(?=(?:[a-h]\)|\d{1,2}\.\s|[-•]\s)\s*[A-ZÁÉÍÓÚ])", "\n", t)
    return t.strip()


def frase_relevante(literal, respuesta):
    partes = [x.strip() for x in re.split(r"\n+|(?<=\.)\s+(?=\d+\.\s)", literal) if x.strip()]
    if not partes:
        return literal
    clave = set(w.lower() for w in re.findall(r"\w{4,}", respuesta))
    return max(partes, key=lambda x: len(clave & set(w.lower() for w in re.findall(r"\w{4,}", x))))


def cuantia_legible(c):
    """'80 / 40' -> '80 € (40 € con pronto pago)';  '2.001 / 10.000' -> '2.001 a 10.000 €'."""
    m = re.match(r"^\s*([\d.,]+)\s*/\s*([\d.,]+)\s*€?\s*$", c)
    if not m:
        return c
    num = lambda s: float(s.replace(".", "").replace(",", "."))
    a, b = m.group(1), m.group(2)
    if num(a) > num(b):
        return f"{a} € ({b} € con pronto pago)"
    return f"{a} a {b} €"


# ---------------------------------------------------------------- piezas comunes

_logo = None


def logo():
    """Logo de Administrativo adaptado a fondo oscuro: lo azul marino pasa a blanco,
    el azul y el verde se mantienen y el fondo blanco se vuelve transparente.
    Solo la parte de texto (sin el simbolo de flechas)."""
    global _logo
    if _logo is None:
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
        corte = bandas[-2][1] if len(bandas) > 1 else h  # la ultima banda son las flechas
        img = img.crop((0, bandas[0][0], w, corte))
        img = img.crop(img.convert("L").point(lambda v: 255 if v < 200 else 0).getbbox()).convert("RGBA")
        px = []
        for r, g, b, _ in img.getdata():
            alfa = max(0, min(255, int((255 - min(r, g, b)) * 3)))
            if max(r, g, b) < 110:  # azul marino casi negro -> blanco
                r, g, b = 255, 255, 255
            elif g > r and g > b and g < 140:  # verde oscuro -> verde claro legible
                r, g, b = 80, 200, 140
            px.append((r, g, b, alfa))
        img.putdata(px)
        alto = 110
        _logo = img.resize((int(img.width * alto / img.height), alto), Image.LANCZOS)
    return _logo


def texto_espaciado(d, centro_x, y, texto, f, color, espacio=4):
    ancho = sum(d.textlength(c, font=f) for c in texto) + espacio * (len(texto) - 1)
    x = centro_x - ancho / 2
    for c in texto:
        d.text((x, y), c, font=f, fill=color)
        x += d.textlength(c, font=f) + espacio


_fondos = {}


def fondo_base(w, h):
    """Degradado azul (arriba mas claro, abajo mas oscuro) con rayas diagonales muy suaves,
    como el fondo de la infografia. Se calcula una vez por tamaño."""
    if (w, h) not in _fondos:
        img = Image.new("RGB", (w, h))
        d = ImageDraw.Draw(img)
        for y in range(h):
            t = y / (h - 1)
            if t < 0.55:
                a, b, k = FONDO_ALTO, FONDO, t / 0.55
            else:
                a, b, k = FONDO, FONDO_BAJO, (t - 0.55) / 0.45
            d.line((0, y, w, y), fill=tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3)))
        rayas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dr = ImageDraw.Draw(rayas)
        for x in range(-h, w + h, 36):  # franjas de 18 px cada 36 px, a 45 grados
            dr.polygon([(x, 0), (x + 18, 0), (x + 18 + h, h), (x + h, h)], fill=(255, 255, 255, 7))
        brillo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        db = ImageDraw.Draw(brillo)
        for i in range(8):  # resplandor suave arriba a la derecha
            r = 700 - i * 70
            db.ellipse((w - r // 2, -r // 2, w + r // 2, r // 2), fill=(70, 140, 220, 6))
        img = Image.alpha_composite(Image.alpha_composite(img.convert("RGBA"), rayas), brillo).convert("RGB")
        _fondos[(w, h)] = img
    return _fondos[(w, h)].copy()


def pegatina(img, texto, xy, angulo=-3, tam=34):
    """Etiqueta blanca inclinada con sombra cian, como «Lo que más cae en el examen»."""
    d0 = ImageDraw.Draw(img)
    f = fuente(SEMI, tam)
    ancho, alto = int(d0.textlength(texto, font=f)) + 56, tam + 34
    capa = Image.new("RGBA", (ancho + 20, alto + 20), (0, 0, 0, 0))
    dc = ImageDraw.Draw(capa)
    dc.rounded_rectangle((8, 10, ancho + 8, alto + 10), radius=14, fill=CIAN + (255,))
    dc.rounded_rectangle((0, 0, ancho, alto), radius=14, fill=(255, 255, 255, 255))
    dc.text((28, alto // 2), texto, font=f, fill=NAVY_TXT, anchor="lm")
    capa = capa.rotate(-angulo, expand=True, resample=Image.BICUBIC)
    img.paste(capa, xy, capa)


def lienzo(titulo_pildora):
    """Cabecera como la infografia: logo a la izquierda, pastilla de la marca a la derecha
    y antetitulo en ambar con letras espaciadas."""
    img = fondo_base(W, H)
    d = ImageDraw.Draw(img)
    lg = logo()
    esc = 92 / lg.height
    lg = lg.resize((int(lg.width * esc), 92), Image.LANCZOS)
    img.paste(lg, (M, 52), lg)
    f = fuente(SEMI, 28)
    ancho = sum(d.textlength(c, font=f) for c in MARCA) + 3 * (len(MARCA) - 1) + 56
    x1 = W - M
    d.rounded_rectangle((x1 - ancho, 70, x1, 124), radius=27, outline=CIAN, width=3)
    texto_espaciado(d, x1 - ancho / 2, 82, MARCA, f, CIAN, 3)
    fk = fuente(SEMI, 30)
    x = M
    for c in titulo_pildora:  # antetitulo espaciado, alineado a la izquierda
        d.text((x, 210), c, font=fk, fill=AMBAR)
        x += d.textlength(c, font=fk) + 7
    d.line((M, 262, M + 120, 262), fill=AMBAR, width=4)
    return img, d


def pie(d, texto):
    d.text((M, H - 92), texto, font=fuente(TXT_SB, 28), fill=(185, 200, 221))


def puntos(img, actual, total):
    d = ImageDraw.Draw(img)
    r, sep = 7, 26
    x0 = W - M - (total - 1) * sep
    for i in range(total):
        cx = x0 + i * sep
        d.ellipse((cx - r, H - 77 - r, cx + r, H - 77 + r), fill=CIAN if i == actual else BORDE)


def etiqueta(d, xy, texto, color, tam=24):
    f = fuente(SEMI, tam + 2)
    x, y = xy
    w = d.textlength(texto, font=f)
    caja = (x, y, x + w + 36, y + tam + 22)
    d.rounded_rectangle(caja, radius=(tam + 22) // 2, fill=TARJETA, outline=color, width=2)
    d.text((x + 18, y + 9), texto, font=f, fill=color)
    return caja[2], caja[3]


def fila_etiquetas(d, y, etiquetas, tam=24):
    """Etiquetas en linea; salta de linea si no caben. Devuelve la y final."""
    x, fin_y = M, y
    for texto, color in etiquetas:
        if not texto:
            continue
        f = fuente(SEMI, tam + 2)
        if x > M and x + d.textlength(texto, font=f) + 36 > W - M:
            x, y = M, fin_y + 12
        x2, fin_y = etiqueta(d, (x, y), texto, color, tam)
        x = x2 + 12
    return fin_y


def tarjeta(d, caja, borde=BORDE, fondo=TARJETA, barra=None):
    d.rounded_rectangle(caja, radius=24, fill=fondo, outline=borde, width=2)
    if barra:
        x0, y0, _, y1 = caja
        d.rounded_rectangle((x0, y0 + 18, x0 + 7, y1 - 18), radius=3, fill=barra)


def caja_texto(d, y, lineas, f, tam, color=TEXTO, titulo=None, barra=None, interlineado=1.4):
    extra = 62 if titulo else 34
    alto = len(lineas) * int(tam * interlineado) + extra + 34
    tarjeta(d, (M, y, W - M, y + alto), barra=barra)
    if titulo:
        d.text((M + 36, y + 22), titulo, font=fuente(TXT_B, 22), fill=CIAN)
    escribir(d, (M + 36, y + extra), lineas, f, tam, color, interlineado)
    return y + alto


def tarjeta_opcion(d, caja, letra, texto, estado="normal"):
    x0, y0, x1, y1 = caja
    fondo, borde, circ, txt, ltxt = TARJETA, BORDE, CIAN, BLANCO, NAVY_TXT
    if estado == "correcta":
        fondo, borde, circ, txt, ltxt = (14, 52, 46), VERDE, VERDE, BLANCO, FONDO
    elif estado == "incorrecta":
        fondo, borde, circ, txt, ltxt = (14, 20, 48), (32, 40, 78), (30, 38, 74), (110, 118, 150), (110, 118, 150)
    d.rounded_rectangle(caja, radius=20, fill=fondo, outline=borde, width=2)
    r = 26
    cx, cy = x0 + 26 + r, (y0 + y1) // 2
    d.rounded_rectangle((cx - r, cy - r, cx + r, cy + r), radius=12, fill=circ)
    d.text((cx, cy), letra, font=fuente(DISPLAY, 32), fill=ltxt, anchor="mm")
    tx = cx + r + 24
    derecha = x1 - (80 if estado == "incorrecta" else 22)
    f, lineas, tam = ajustar(d, texto, TXT_SB if estado == "correcta" else TXT,
                             derecha - tx, y1 - y0 - 22, 32, 19, 1.22)
    alto = len(lineas) * int(tam * 1.22)
    escribir(d, (tx, cy - alto // 2 - 3), lineas, f, tam, txt, 1.22)
    if estado == "incorrecta":
        ax = x1 - 46
        d.line((ax - 14, cy - 14, ax + 14, cy + 14), fill=ROJO, width=6)
        d.line((ax - 14, cy + 14, ax + 14, cy - 14), fill=ROJO, width=6)


def pildora(p):
    return {"test": "TEST DEL DÍA", "infraccion": "INFRACCIÓN DEL DÍA"}.get(p["tipo"], "SUPUESTO DEL DÍA")


# ---------------------------------------------------------------- test y supuestos

def slides_caso(p):
    tam = 31
    paginas = paginar(p["enunciado"], TXT, tam, W - 2 * M - 72, LIMITE - TOP - 160)
    if len(paginas) > 2:
        tam = 27
        paginas = paginar(p["enunciado"], TXT, tam, W - 2 * M - 72, LIMITE - TOP - 160)[:2]
    imgs = []
    for i, lineas in enumerate(paginas):
        img, d = lienzo(pildora(p))
        y = fila_etiquetas(d, TOP, [(f"SUPUESTO REAL · {p['convocatoria'].upper()}", CIAN)]) + 22
        caja_texto(d, y, lineas, fuente(TXT, tam), tam,
                   titulo="EL CASO" if i == 0 else "EL CASO (SIGUE)", barra=CIAN)
        pie(d, "Lee el caso y desliza  →" if i == len(paginas) - 1 else "Sigue leyendo  →")
        imgs.append(img)
    return imgs


def caso_en_linea(d, y, p, alto_max=380):
    """Si el supuesto tiene un enunciado corto (no lleva diapositiva propia), lo dibuja en un
    recuadro "EL CASO" encima de la pregunta. Sin el caso la pregunta no se entiende."""
    if p["tipo"] != "corta" or len(p["enunciado"]) < 60 or len(p["enunciado"]) >= MIN_CASO:
        return y
    f, lineas, tam = ajustar(d, p["enunciado"], TXT, W - 2 * M - 80, alto_max - 90, 30, 22, 1.35)
    return caja_texto(d, y, lineas, f, tam, TEXTO, titulo="EL CASO", barra=CIAN, interlineado=1.35) + 26


def slide_pregunta(p):
    img, d = lienzo(pildora(p))
    etiqueta_conv = ("EXAMEN " if p["tipo"] == "test" else "SUPUESTO ") + p["convocatoria"].upper()
    y = fila_etiquetas(d, TOP, [(etiqueta_conv, CIAN), (p["norma_corta"], MORADO)]) + 24
    y0 = y
    y = caso_en_linea(d, y, p, alto_max=330)
    opciones = [(l, t) for l, t in zip("ABCD", p["opciones"]) if t]
    alto_preg = 250 if sum(len(t) for _, t in opciones) < 400 else 190
    if y > y0:
        alto_preg = 150
    f, lineas, tam = ajustar(d, p["pregunta"], TIT, W - 2 * M, alto_preg, 50, 32, 1.2)
    y = escribir(d, (M, y), lineas, f, tam, BLANCO, 1.2) + 24
    hueco = 18
    alto = min(150, (LIMITE + 10 - y - hueco * (len(opciones) - 1)) // len(opciones))
    for letra, texto in opciones:
        tarjeta_opcion(d, (M, y, W - M, y + alto), letra, texto)
        y += alto + hueco
    pegatina(img, "¿La sabes? Comenta tu respuesta", (M - 6, H - 128), angulo=-2.5, tam=32)
    return img


def slide_solucion(p):
    img, d = lienzo(pildora(p))
    d.text((M, TOP - 8), "SOLUCIÓN", font=fuente(TIT, 64), fill=VERDE)
    y = TOP + 85
    idx = "ABCD".index(p["correcta"])
    tarjeta_opcion(d, (M, y, W - M, y + 150), p["correcta"], p["opciones"][idx], "correcta")
    y += 172
    if p["articulo"] or p["norma_corta"]:
        txt = " · ".join(x for x in (p["articulo"], p["norma_corta"]) if x)
        y = fila_etiquetas(d, y, [(acortar(txt, 55), MORADO)]) + 20
    hay_literal = bool(p["literal"])
    texto = sin_mayusculas(acortar(p["justificacion"], 360 if hay_literal else 650))
    f, lineas, tam = ajustar(d, texto, TXT, W - 2 * M, 270 if hay_literal else LIMITE - y, 33, 22, 1.38)
    y = escribir(d, (M, y), lineas, f, tam, TEXTO, 1.38) + 24
    if hay_literal and LIMITE - y > 190:
        literal = acortar(frase_relevante(p["literal"], p["opciones"][idx]), 330)
        fl, ll, tl = ajustar(d, "«" + literal + "»", TXT_I, W - 2 * M - 72, LIMITE - y - 100, 30, 20, 1.35)
        caja_texto(d, y, ll, fl, tl, GRIS, titulo="LO QUE DICE LA LEY", interlineado=1.35)
    pie(d, "¿Acertaste? Guárdalo para repasar")
    return img


def slide_trampa(p):
    img, d = lienzo(pildora(p))
    d.text((M, TOP - 8), "LA TRAMPA", font=fuente(TIT, 64), fill=ROJO)
    d.text((M, TOP + 75), "Por qué fallan las demás opciones", font=fuente(TXT_SB, 30), fill=GRIS)
    y = TOP + 135
    malas = [(l, t) for l, t in zip("ABCD", p["opciones"]) if t and l != p["correcta"]]
    alto_op = 108 if len(malas) == 3 else 130
    for l, t in malas:
        tarjeta_opcion(d, (M, y, W - M, y + alto_op), l, t, "incorrecta")
        y += alto_op + 14
    y += 16
    texto = sin_mayusculas(acortar(p["justificacion_incorrecta"], 420))
    f, lineas, tam = ajustar(d, texto, TXT, W - 2 * M - 72, LIMITE - y - 80, 32, 21, 1.4)
    caja_texto(d, y, lineas, f, tam, barra=ROJO)
    pie(d, "Así es como lo preguntan en el examen")
    return img


def slide_pregunta_abierta(p):
    img, d = lienzo(pildora(p))
    y = fila_etiquetas(d, TOP, [(f"SUPUESTO REAL · {p['convocatoria'].upper()}", CIAN),
                               ("PREGUNTA A DESARROLLAR", MORADO)]) + 34
    y0 = y
    y = caso_en_linea(d, y, p)
    f, lineas, tam = ajustar(d, p["pregunta"], TIT, W - 2 * M, 470 if y == y0 else 300, 62, 30, 1.2)
    y = escribir(d, (M, y), lineas, f, tam, BLANCO, 1.2) + 40
    d.line((M, y, M + 260, y), fill=CIAN, width=5)
    y += 40
    texto = ("¿Cómo lo resolverías en el examen?\n"
             "Escribe los puntos clave en comentarios y desliza para ver la solución.")
    f2, l2, t2 = ajustar(d, texto, TXT, W - 2 * M, LIMITE - y, 34, 24, 1.4)
    escribir(d, (M, y), l2, f2, t2, GRIS, 1.4)
    pie(d, "Desliza para la solución  →")
    return img


def slides_respuesta(p):
    texto = formatear_respuesta(sin_mayusculas(p["justificacion"]))
    tam = 31
    alto = LIMITE - TOP - 190
    paginas = paginar(texto, TXT, tam, W - 2 * M - 72, alto)
    if len(paginas) > 2:
        tam = 27
        paginas = paginar(texto, TXT, tam, W - 2 * M - 72, alto)
    imgs = []
    total = min(len(paginas), 3)
    for i, lineas in enumerate(paginas[:3]):
        img, d = lienzo(pildora(p))
        d.text((M, TOP - 8), "SOLUCIÓN", font=fuente(TIT, 64), fill=VERDE)
        y = TOP + 88
        if p["norma"]:
            y = fila_etiquetas(d, y, [(acortar(p["norma_corta"] or p["norma"], 60), MORADO)]) + 20
        caja_texto(d, y, lineas, fuente(TXT, tam), tam, barra=VERDE)
        pie(d, "Guárdalo para repasar" if i == total - 1 else "Sigue  →")
        imgs.append(img)
    return imgs


# ---------------------------------------------------------------- infracciones

def slide_infraccion(i):
    img, d = lienzo("INFRACCIÓN DEL DÍA")
    texto = sin_mayusculas(i["texto"])
    f, lineas, tam = ajustar(d, texto, TXT_SB, W - 2 * M - 80, 430, 48, 28, 1.32)
    alto = len(lineas) * int(tam * 1.32) + 80
    bloque = 60 + alto + 50 + 90 + 72  # etiquetas + tarjeta + pregunta + botones
    y = TOP + max(0, (LIMITE - TOP - bloque) // 2)
    y = fila_etiquetas(d, y, [(i["materia"].upper(), CIAN), (i["norma_corta"], MORADO)]) + 26
    tarjeta(d, (M, y, W - M, y + alto), barra=CIAN)
    escribir(d, (M + 42, y + 40), lineas, f, tam, BLANCO, 1.32)
    y += alto + 50
    d.text((W // 2, y), "¿Qué tipo de infracción es?", font=fuente(TIT, 46), fill=BLANCO, anchor="mt")
    y += 90
    opciones = [("LEVE", VERDE), ("GRAVE", NARANJA), ("MUY GRAVE", ROJO)]
    fo = fuente(TXT_B, 30)
    anchos = [d.textlength(t, font=fo) + 70 for t, _ in opciones]
    x = (W - sum(anchos) - 24 * 2) / 2
    for (t, c), a in zip(opciones, anchos):
        d.rounded_rectangle((x, y, x + a, y + 72), radius=36, fill=TARJETA, outline=c, width=3)
        d.text((x + a / 2, y + 36), t, font=fo, fill=c, anchor="mm")
        x += a + 24
    pie(d, "Comenta tu respuesta  ·  Desliza para la solución  →")
    return img


def slide_infraccion_solucion(i):
    img, d = lienzo("INFRACCIÓN DEL DÍA")
    color = GRAVEDAD.get(i["gravedad"].lower(), CIAN)
    d.text((M, TOP - 8), "SOLUCIÓN", font=fuente(TIT, 64), fill=BLANCO)
    f = fuente(TXT_B, 44)
    t = i["gravedad"].upper()
    w = d.textlength(t, font=f)
    d.rounded_rectangle((M, TOP + 90, M + w + 70, TOP + 170), radius=40, fill=color)
    d.text((M + 35, TOP + 130), t, font=f, fill=FONDO, anchor="lm")
    y = TOP + 205

    filas = [("PRECEPTO", " · ".join(x for x in (i["referencia"], i["norma_media"]) if x)),
             ("CUANTÍA", cuantia_legible(i["cuantia"])),
             ("PUNTOS", f"{i['puntos']} puntos" if i["puntos"] else ""),
             ("RESPONSABLE", i["responsable"]),
             ("ÓRGANO COMPETENTE", i["organo"])]
    filas = [(k, v) for k, v in filas if v]
    fe, fv = fuente(TXT_B, 21), fuente(TXT_SB, 29)
    bloques = [(k, envolver(d, v, fv, W - 2 * M - 72)[:3]) for k, v in filas]
    alto = sum(30 + len(ls) * 38 + 18 for _, ls in bloques) + 34
    tarjeta(d, (M, y, W - M, y + alto), barra=color)
    yy = y + 26
    for k, ls in bloques:
        d.text((M + 36, yy), k, font=fe, fill=CIAN)
        yy = escribir(d, (M + 36, yy + 30), ls, fv, 29, BLANCO, 1.3) + 18
    y += alto + 22

    if i["comentario"] and LIMITE - y > 150:
        fl, ll, tl = ajustar(d, sin_mayusculas(i["comentario"]), TXT, W - 2 * M - 72, LIMITE - y - 90, 28, 20, 1.38)
        caja_texto(d, y, ll, fl, tl, TEXTO, titulo="A TENER EN CUENTA", interlineado=1.38)
    elif LIMITE - y > 80 and i["norma"]:
        fn, ln, tn = ajustar(d, i["norma"], TXT_I, W - 2 * M, LIMITE - y, 24, 18, 1.35)
        escribir(d, (M, y), ln, fn, tn, GRIS, 1.35)
    pie(d, "Guárdalo para tu próximo servicio")
    return img


# ---------------------------------------------------------------- llamada a la app

def slide_cta(p):
    """Cierre como la infografia: titulo en dos colores, tarjeta blanca con lo que incluye la app,
    boton cian con la web y «Guárdalo y compártelo»."""
    img, d = lienzo(pildora(p))
    conv = p["convocatoria"].upper() + "."
    if p["tipo"] == "test":
        lineas = [("ESTA CAYÓ EN", BLANCO), (conv, CIAN), ("¿CUÁNTAS MÁS", BLANCO), ("ACERTARÍAS?", BLANCO)]
    elif p["tipo"] == "infraccion":
        lineas = [("TODO EL", BLANCO), ("CODIFICADO", CIAN), ("EN TU", BLANCO), ("BOLSILLO.", BLANCO)]
    else:
        lineas = [("ESTE SUPUESTO", BLANCO), ("CAYÓ EN", BLANCO), (conv, CIAN), ("¿LO TENÍAS?", BLANCO)]
    y = TOP - 6
    for texto, color in lineas:
        f, _, _ = ajustar(d, texto, TIT, W - 2 * M, 96, 86, 50, 1.0)
        d.text((M, y), texto, font=f, fill=color)
        y += 94
    y += 26
    # tarjeta blanca con lo que incluye la app
    fl = fuente(TXT_SB, 31)
    alto_card = 74 + len(LISTA_CTA) * 54
    d.rounded_rectangle((M, y, W - M, y + alto_card), radius=26, fill=(255, 255, 255))
    d.text((M + 40, y + 26), "En la app tienes:", font=fuente(SEMI, 32), fill=NAVY_TXT)
    yy = y + 78
    for item in LISTA_CTA:
        cx, cy = M + 56, yy + 18
        d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=CIAN)
        d.line((cx - 8, cy, cx - 2, cy + 7, cx + 9, cy - 7), fill=NAVY_TXT, width=4)
        d.text((cx + 32, cy), item, font=fl, fill=NAVY_TXT, anchor="lm")
        yy += 54
    y += alto_card + 28
    # boton cian con la web
    d.rounded_rectangle((M, y, W - M, y + 128), radius=30, fill=CIAN)
    d.text((W // 2, y + 36), "Empieza gratis en", font=fuente(SEMI, 32), fill=NAVY_TXT, anchor="mm")
    fu, _, _ = ajustar(d, URL_APP, DISPLAY, W - 2 * M - 80, 70, 58, 36, 1.0)
    d.text((W // 2, y + 86), URL_APP, font=fu, fill=NAVY_TXT, anchor="mm")
    pie(d, "Guárdalo y compártelo con quien prepare la oposición")
    return img


# ---------------------------------------------------------------- montaje

def construir(p):
    if p["tipo"] == "infraccion":
        imgs = [slide_infraccion(p), slide_infraccion_solucion(p)]
    elif es_desarrollo(p):
        imgs = slides_caso(p) if len(p["enunciado"]) >= MIN_CASO else []
        imgs += [slide_pregunta_abierta(p), *slides_respuesta(p)]
    else:
        imgs = slides_caso(p) if p["tipo"] == "corta" and len(p["enunciado"]) >= MIN_CASO else []
        imgs += [slide_pregunta(p), slide_solucion(p)]
        if len(p["justificacion_incorrecta"]) >= 40:
            imgs.append(slide_trampa(p))
    imgs.append(slide_cta(p))
    for n, img in enumerate(imgs):
        puntos(img, n, len(imgs))
    return imgs


def generar(p, salida):
    """Guarda las diapositivas como JPEG (Instagram solo admite JPEG) y devuelve las rutas."""
    os.makedirs(salida, exist_ok=True)
    rutas = []
    for n, img in enumerate(construir(p), 1):
        r = os.path.join(salida, f"{n:02d}.jpg")
        img.save(r, "JPEG", quality=90, optimize=True, progressive=True)
        rutas.append(r)
    return rutas


if __name__ == "__main__":
    from datos import cargar

    objetivo = sys.argv[1]
    tipo = ("infraccion" if "CODIFICADO" in objetivo else
            "corta" if "SUPUESTOS" in objetivo else "test")
    p = next(x for x in cargar(tipo) if x["id"] == objetivo)
    salida = os.path.join(RAIZ, "40. INSTAGRAM", "salida", "muestra_" + tipo)
    for r in generar(p, salida):
        print(r)
