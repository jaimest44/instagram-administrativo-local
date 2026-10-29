"""Serie «Esquemas visuales» de Administrativo: un tema del temario por post, martes y viernes a las 11:00.
Usa las fichas A4 de INFOGRAFIA LEYES/ADMINISTRATIVO (una por tema; el 13 tiene dos).
Se alternan Reel 9:16 (barrido por la ficha) y carrusel 4:5 «¿Sabrías responder?» con un caso de la ficha.

    python infografias.py programar 2026-11-03 14     # mete en cola los 14 siguientes temas
    python infografias.py muestra Tema_22_Potestad_Sancionadora carrusel

Mientras no este confirmado que los esquemas estan en la app, el CTA es generico (examenes oficiales en la app)
y nunca se dice «la ficha completa esta en la app». Cambiar EN_LA_APP a True cuando Jaime lo confirme.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

import pymupdf
from PIL import Image, ImageDraw, ImageFilter

import carrusel as C

FICHAS = r"C:/Users/jaime/Downloads/INFOGRAFIA LEYES/ADMINISTRATIVO"
AQUI = os.path.dirname(os.path.abspath(__file__))
COLA = os.path.join(AQUI, "..", "cola")
ESTADO = os.path.join(AQUI, "..", "estado", "infografias_usadas.json")
EN_LA_APP = True  # Jaime confirmo el 29/10 que los esquemas estan en la app
RUTA_APP = ""  # ruta dentro de la app (vacio: solo la URL)
SIN_LEY = (9, 39, 40, 41)  # sintesis sin una ley detras (IA, Windows, ofimatica, navegadores): al final de la serie


# ---------------------------------------------------------------- lectura de la ficha

def temas():
    """[(n, carpeta, pdf)] en el orden de la serie: 1..41 con los temas sin ley al final."""
    out = []
    for carpeta in sorted(os.listdir(FICHAS)):
        m = re.match(r"Tema_(\d+)_", carpeta)
        if not m:
            continue
        for pdf in sorted(f for f in os.listdir(os.path.join(FICHAS, carpeta)) if f.lower().endswith(".pdf")):
            out.append((int(m.group(1)), carpeta, pdf))
    return sorted(out, key=lambda t: (t[0] in SIN_LEY, t[0]))


def limpiar(texto):
    texto = re.sub(r"\s+", " ", texto).strip()
    # palabras partidas al final de linea: "6– 18" -> "6–18", "consi- derar" -> "considerar"
    return re.sub(r"(\w)([–-]) (\w)", lambda m: m.group(1) + (m.group(2) if m.group(1).isdigit() else "") + m.group(3), texto)


def leer_ficha(ruta):
    """Imagen de la pagina, titulo y subtitulo de la cabecera, norma, casos y consejos de examen."""
    p = pymupdf.open(ruta)[0]
    w = p.rect.width
    spans = [s for b in p.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]
             if 20 < s["bbox"][1] < 50 and s["bbox"][0] < w * 0.85 and s["text"].strip()]
    grande = max(s["size"] for s in spans)
    titulo = limpiar("".join(s["text"] for s in spans if s["size"] >= grande - 0.5))
    sub = limpiar("".join(s["text"] for s in spans if s["size"] < grande - 0.5 and s["size"] > 9)).lstrip("· ").strip()
    norma = next((limpiar(s["text"]) for b in p.get_text("dict")["blocks"] for l in b.get("lines", []) for s in l["spans"]
                  if 44 < s["bbox"][1] < 56 and s["text"].strip()), "")

    lineas = [l.strip() for l in p.get_text().splitlines() if l.strip()]
    casos = []
    try:
        i = next(k for k, l in enumerate(lineas) if l == "SUPUESTOS") + 2
        actual = None
        for l in lineas[i:]:
            if l == "TIPS":
                break
            if re.match(r"^\d+\. ", l):
                actual = [re.sub(r"^\d+\. ", "", l), ""]
                casos.append(actual)
            elif l.startswith("➜") and actual:
                actual[1] = l[1:].strip()
            elif actual:
                actual[1 if actual[1] else 0] += " " + l
        casos = [(limpiar(a), limpiar(b)) for a, b in casos if b]
    except StopIteration:
        pass
    consejos = []
    try:
        i = next(k for k, l in enumerate(lineas) if "TRAMPAS DE EXAMEN" in l.upper()) + 1
        for l in lineas[i:]:
            if l.startswith("Fuente") or l.startswith("Material de estudio"):
                break
            if re.match(r"^[^\w\s(¿¡«\"'+\-–]", l):  # nuevo consejo (empieza por icono)
                consejos.append([re.sub(r"^[^\wÁÉÍÓÚÑ¿¡«\"(]+", "", l).strip(), ""])
            elif consejos:
                consejos[-1][1] += " " + l
        consejos = [(limpiar(a), limpiar(b)) for a, b in consejos if a]
    except StopIteration:
        pass

    zoom = 2160 / w
    pix = p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).resize((1080, int(1080 * pix.height / pix.width)), Image.LANCZOS)
    return {"img": img, "titulo": titulo, "sub": sub, "norma": norma, "casos": casos, "consejos": consejos}


def difuminar(img, desde):
    """Deja nitida la parte de arriba (hasta 'desde', fraccion de alto) y difumina el resto."""
    y = int(img.height * desde)
    out = img.copy()
    borroso = img.crop((0, y, img.width, img.height)).filter(ImageFilter.GaussianBlur(14))
    out.paste(Image.blend(borroso, Image.new("RGB", borroso.size, C.FONDO), 0.25), (0, y))
    trans = 60
    for i in range(trans):
        a = i / trans
        fila_n = img.crop((0, y - trans + i, img.width, y - trans + i + 1))
        fila_b = Image.blend(fila_n.filter(ImageFilter.GaussianBlur(4)), Image.new("RGB", fila_n.size, C.FONDO), 0.25 * a)
        out.paste(Image.blend(fila_n, fila_b, a), (0, y - trans + i))
    return out


def candado(d, cx, cy, r=62):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=C.FONDO, outline=C.CIAN, width=5)
    d.rounded_rectangle((cx - 26, cy - 6, cx + 26, cy + 34), radius=7, fill=C.AMBAR)
    d.arc((cx - 18, cy - 36, cx + 18, cy + 6), start=180, end=360, fill=C.AMBAR, width=8)
    d.ellipse((cx - 5, cy + 8, cx + 5, cy + 18), fill=C.FONDO)


def frase_adelanto():
    return "La ficha completa, en la app" if EN_LA_APP else "Martes y viernes, un tema nuevo"


def tarjeta_cierre(d, y):
    """Tarjeta blanca con LISTA_CTA + boton azul hacia la app."""
    items = C.LISTA_CTA
    alto = 84 + len(items) * 52
    d.rounded_rectangle((C.M, y, C.W - C.M, y + alto), radius=26, fill=(255, 255, 255))
    d.text((C.M + 40, y + 28), "En la app tienes:", font=C.fuente(C.SEMI, 33), fill=C.NAVY_TXT)
    yy = y + 84
    for it in items:
        cx, cy = C.M + 56, yy + 18
        d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=C.CIAN)
        d.line((cx - 8, cy, cx - 2, cy + 7, cx + 9, cy - 7), fill=C.NAVY_TXT, width=4)
        f, _, _ = C.ajustar(d, it, C.TXT_SB, C.W - 2 * C.M - 130, 40, 31, 22, 1.0)
        d.text((cx + 32, cy), it, font=f, fill=C.NAVY_TXT, anchor="lm")
        yy += 52
    y += alto + 26
    d.rounded_rectangle((C.M, y, C.W - C.M, y + 150), radius=30, fill=C.CIAN)
    if EN_LA_APP:
        if RUTA_APP:
            d.text((C.W // 2, y + 38), "Regístrate en " + C.URL_APP, font=C.fuente(C.DISPLAY, 40), fill=C.NAVY_TXT, anchor="mm")
            d.text((C.W // 2, y + 96), RUTA_APP, font=C.fuente(C.SEMI, 31), fill=C.NAVY_TXT, anchor="mm")
        else:
            d.text((C.W // 2, y + 44), "Todas las fichas en", font=C.fuente(C.SEMI, 34), fill=C.NAVY_TXT, anchor="mm")
            d.text((C.W // 2, y + 102), C.URL_APP, font=C.fuente(C.DISPLAY, 56), fill=C.NAVY_TXT, anchor="mm")
    else:
        d.text((C.W // 2, y + 44), "Empieza gratis en", font=C.fuente(C.SEMI, 34), fill=C.NAVY_TXT, anchor="mm")
        d.text((C.W // 2, y + 102), C.URL_APP, font=C.fuente(C.DISPLAY, 56), fill=C.NAVY_TXT, anchor="mm")
    return y + 150


def titulos_cierre(d, y, tam=90, paso=96):
    lineas = (("LAS FICHAS DE", C.BLANCO), ("LOS 41 TEMAS,", C.CIAN), ("EN LA APP.", C.BLANCO)) if EN_LA_APP else         (("ESTUDIA TU", C.BLANCO), ("OPOSICIÓN", C.CIAN), ("CON EXÁMENES REALES.", C.BLANCO))
    for texto, color in lineas:
        f, _, _ = C.ajustar(d, texto, C.TIT, C.W - 2 * C.M, paso, tam, 50, 1.0)
        d.text((C.M, y), texto, font=f, fill=color)
        y += paso
    return y


# ---------------------------------------------------------------- carrusel «¿Sabrias responder?» (5 diapositivas 4:5)

def carrusel(fi, n, salida):
    os.makedirs(salida, exist_ok=True)
    W, M = C.W, C.M
    corte = 0.40
    ficha = fi["img"]
    nitida = ficha.crop((0, 0, ficha.width, int(ficha.height * corte)))
    caso = fi["casos"][0] if fi["casos"] else None
    imgs = []

    # 1. portada
    img, d = C.lienzo(f"ESQUEMA VISUAL · TEMA {n}")
    y = C.TOP - 10
    f, l, t = C.ajustar(d, fi["titulo"].upper(), C.TIT, W - 2 * M, 200, 96, 56, 1.0)
    y = C.escribir(d, (M, y), l, f, t, C.CIAN, 1.0) + 8
    if fi["sub"]:
        f, l, t = C.ajustar(d, fi["sub"], C.TIT, W - 2 * M, 130, 56, 34, 1.1)
        y = C.escribir(d, (M, y), l, f, t, C.BLANCO, 1.1) + 26
    C.pegatina(img, "¿Sabrías responder?" if caso else "Lo que más cae en el examen", (M - 6, y), angulo=-3, tam=36)
    y += 110
    prev = nitida.resize((W - 2 * M, int((W - 2 * M) * nitida.height / nitida.width)), Image.LANCZOS)
    alto = min(prev.height, C.LIMITE - y)
    d.rounded_rectangle((M - 6, y - 6, W - M + 6, y + alto + 6), radius=18, fill=C.CIAN)
    img.paste(prev.crop((0, 0, prev.width, alto)), (M, y))
    C.pie(d, "Desliza  >")
    imgs.append(img)

    if caso:
        # 2. el caso
        img, d = C.lienzo("CASO PRÁCTICO DE OFICINA")
        y = C.TOP + 10
        f, l, t = C.ajustar(d, caso[0], C.TIT, W - 2 * M, 620, 84, 48, 1.12)
        y = C.escribir(d, (M, y), l, f, t, C.BLANCO, 1.12) + 50
        C.pegatina(img, "Piénsalo antes de deslizar", (M - 6, min(y, C.LIMITE - 90)), angulo=-3, tam=36)
        C.pie(d, "La respuesta, en la siguiente  >")
        imgs.append(img)

        # 3. respuesta + truco
        img, d = C.lienzo("RESPUESTA")
        y = C.TOP - 10
        f, l, t = C.ajustar(d, caso[1], C.TIT, W - 2 * M, 420, 76, 44, 1.12)
        y = C.escribir(d, (M, y), l, f, t, C.CIAN, 1.12) + 40
        for truco in fi["consejos"][:2]:  # uno o dos trucos de examen de la ficha, si caben
            if C.LIMITE - y < 220:
                break
            f, l, t = C.ajustar(d, truco[1], C.TXT, W - 2 * M - 72, min(220, C.LIMITE - y - 120), 34, 24, 1.35)
            y = C.caja_texto(d, y, l, f, t, C.TEXTO, titulo="TRUCO DE EXAMEN · " + truco[0][:44], barra=C.AMBAR) + 22
        C.pie(d, "Guárdalo para repasar")
        imgs.append(img)

    # 4. la ficha: nitida arriba, difuminada abajo
    img, d = C.lienzo("ASÍ ES LA FICHA DEL TEMA")
    y = C.TOP - 20
    dif = difuminar(ficha, corte)
    dif = dif.resize((W - 2 * M, int((W - 2 * M) * dif.height / dif.width)), Image.LANCZOS)
    alto = C.LIMITE - y - 10
    d.rounded_rectangle((M - 6, y - 6, W - M + 6, y + alto + 6), radius=18, fill=C.CIAN)
    img.paste(dif.crop((0, 0, dif.width, alto)), (M, y))
    d = ImageDraw.Draw(img)
    cy = y + int(dif.height * corte) + 120
    candado(d, W // 2, cy, r=56)
    d.text((W // 2, cy + 105), "ESTO ES SOLO UN ADELANTO", font=C.fuente(C.TIT, 60), fill=C.BLANCO, anchor="mm",
           stroke_width=6, stroke_fill=C.FONDO)
    d.text((W // 2, cy + 165), frase_adelanto(), font=C.fuente(C.SEMI, 38), fill=C.CIAN, anchor="mm",
           stroke_width=5, stroke_fill=C.FONDO)
    C.pie(d, "Desliza  >")
    imgs.append(img)

    # 5. cierre
    img, d = C.lienzo("ESQUEMAS VISUALES")
    y = titulos_cierre(d, C.TOP - 6)
    tarjeta_cierre(d, y + 24)
    C.pie(d, "Guárdalo y compártelo con quien prepare la oposición")
    imgs.append(img)

    nombres = []
    for i, im in enumerate(imgs):
        C.puntos(im, i, len(imgs))
        nombre = f"{i + 1:02d}.jpg"
        im.save(os.path.join(salida, nombre), "JPEG", quality=90, optimize=True, progressive=True)
        nombres.append(nombre)
    return nombres


# ---------------------------------------------------------------- reel (9:16, ~15 s)

def reel(fi, n, salida, fps=30):
    """Barrido lento por la ficha (nitida arriba, difuminada abajo) y tarjeta final."""
    import imageio_ffmpeg
    os.makedirs(salida, exist_ok=True)
    W, H, M = 1080, 1920, C.M
    corte = 0.45
    dif = difuminar(fi["img"], corte)
    ancho = W - 2 * 40
    doc = dif.resize((ancho, int(ancho * dif.height / dif.width)), Image.LANCZOS)

    base = C.fondo_base(W, H)
    d = ImageDraw.Draw(base)
    lg = C.logo()
    lg = lg.resize((int(lg.width * 84 / lg.height), 84), Image.LANCZOS)
    base.paste(lg, (M, 56), lg)
    fk = C.fuente(C.SEMI, 30)
    x = M
    for c in f"ESQUEMA VISUAL · TEMA {n}":
        d.text((x, 172), c, font=fk, fill=C.AMBAR)
        x += d.textlength(c, font=fk) + 5
    f, l, t = C.ajustar(d, fi["titulo"], C.TIT, W - 2 * M, 150, 72, 44, 1.05)
    C.escribir(d, (M, 222), l, f, t, C.BLANCO, 1.05)
    ventana_y, ventana_h = 410, 1330
    recorrido = max(0, doc.height - ventana_h)

    seg_barrido, seg_cierre = 10, 5
    total = seg_barrido + seg_cierre
    cierre = None
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    destino = os.path.join(salida, "reel.mp4")
    proc = subprocess.Popen([ff, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
                             "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                             "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "21",
                             "-c:a", "aac", "-b:a", "96k", "-t", str(total), "-shortest",
                             "-movflags", "+faststart", destino], stdin=subprocess.PIPE)
    for k in range(total * fps):
        s = k / fps
        if s < seg_barrido:
            a = min(1, max(0, (s - 1) / (seg_barrido - 2)))
            a = a * a * (3 - 2 * a)
            off = int(recorrido * a)
            frame = base.copy()
            frame.paste(doc.crop((0, off, doc.width, off + ventana_h)), (40, ventana_y))
            if s > seg_barrido - 3.5:
                fd = ImageDraw.Draw(frame)
                cy = ventana_y + ventana_h // 2
                candado(fd, W // 2, cy - 40, r=70)
                fd.text((W // 2, cy + 80), "ESTO ES SOLO UN ADELANTO", font=C.fuente(C.TIT, 70), fill=C.BLANCO,
                        anchor="mm", stroke_width=7, stroke_fill=C.FONDO)
                fd.text((W // 2, cy + 150), frase_adelanto(), font=C.fuente(C.SEMI, 42), fill=C.CIAN,
                        anchor="mm", stroke_width=6, stroke_fill=C.FONDO)
        else:
            if cierre is None:
                cierre = C.fondo_base(W, H)
                cd = ImageDraw.Draw(cierre)
                cierre.paste(lg, (M, 56), lg)
                y = titulos_cierre(cd, 300, tam=120, paso=128)
                tarjeta_cierre(cd, y + 40)
                cd.text((W // 2, H - 140), "Guárdalo y compártelo con quien prepare la oposición",
                        font=C.fuente(C.TXT_SB, 30), fill=(185, 200, 221), anchor="mm")
            frame = cierre
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    proc.wait()
    if proc.returncode:
        raise RuntimeError("ffmpeg falló al crear el reel")
    return destino


# ---------------------------------------------------------------- texto y programacion

def caption(fi, n, formato):
    caso = fi["casos"][0] if fi["casos"] else None
    partes = []
    if caso and formato == "carrusel":
        partes.append(f"❓ {caso[0]}\n\nDesliza para ver la respuesta 👉")
    elif caso:
        partes.append(f"❓ {caso[0]}\n\n✅ {caso[1]}")
    else:
        partes.append(f"Lo que más cae del Tema {n} en el examen de Administrativo.")
    if fi["consejos"]:
        a, b = fi["consejos"][0]
        partes.append(f"🧠 Truco: {a}. {b}")
    partes.append(f"Esquema visual del Tema {n}: {fi['titulo']}" + (f" · {fi['sub']}" if fi["sub"] else "") + "."
                  + (f" {fi['norma']}" if fi["norma"] else ""))
    if EN_LA_APP:
        partes.append("Cada martes y viernes, un tema nuevo. Las fichas completas de los 41 temas, con casos prácticos y "
                      f"trampas de examen, están en {C.URL_APP}" + (f" → {RUTA_APP}" if RUTA_APP else "") + " (enlace en la bio).")
    else:
        partes.append("Cada martes y viernes, un tema nuevo. Exámenes oficiales de Ayuntamientos andaluces, "
                      f"con cada pregunta justificada, en {C.URL_APP} (enlace en la bio). Puedes empezar gratis.")
    partes.append("📌 Guárdalo y compártelo con quien esté preparando la oposición.")
    partes.append("#oposicionesandalucia #administrativo #esquemasvisuales")
    return "\n\n".join(partes)


def generar_post(n, carpeta, pdf, formato, salida):
    fi = leer_ficha(os.path.join(FICHAS, carpeta, pdf))
    os.makedirs(salida, exist_ok=True)
    meta = {"id": f"infografia-{carpeta}-{pdf}", "formato": "infografia_" + formato, "tema": "infografia",
            "convocatoria": "", "caso": "", "ley": f"Tema {n}", "ficha": pdf, "imagenes": []}
    if formato == "reel":
        reel(fi, n, salida)
        meta["reel"] = "reel.mp4"
    else:
        meta["imagenes"] = carrusel(fi, n, salida)
    with open(os.path.join(salida, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(caption(fi, n, formato))
    return meta, fi


def programar(inicio, cuantos):
    """Los siguientes temas sin publicar, martes y viernes a las 11:00, alternando carrusel y Reel."""
    usadas = json.load(open(ESTADO, encoding="utf-8")) if os.path.exists(ESTADO) else {}
    dia = dt.date.fromisoformat(inicio)
    hechos = 0
    for n, carpeta, pdf in temas():
        if hechos >= cuantos:
            break
        if f"{carpeta}/{pdf}" in usadas:
            continue
        while dia.weekday() not in (1, 4):  # martes y viernes
            dia += dt.timedelta(days=1)
        clave = dia.isoformat() + "_manana"
        salida = os.path.join(COLA, clave)
        if os.path.exists(os.path.join(salida, "meta.json")):
            dia += dt.timedelta(days=1)
            continue
        formato = "carrusel" if len(usadas) % 2 == 0 else "reel"
        meta, fi = generar_post(n, carpeta, pdf, formato, salida)
        meta.update({"fecha": dia.isoformat(), "franja": "manana"})
        json.dump(meta, open(os.path.join(salida, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        usadas[f"{carpeta}/{pdf}"] = clave
        print(f"{dia:%a %d/%m} 11:00  {formato:<8} Tema {n} · {fi['titulo']}")
        hechos += 1
        dia += dt.timedelta(days=1)
    json.dump(usadas, open(ESTADO, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)


if __name__ == "__main__":
    if sys.argv[1] == "programar":
        programar(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 14)
    elif sys.argv[1] == "muestra":
        carpeta = sys.argv[2]
        n = int(re.match(r"Tema_(\d+)_", carpeta).group(1))
        pdf = sorted(f for f in os.listdir(os.path.join(FICHAS, carpeta)) if f.lower().endswith(".pdf"))[0]
        destino = os.path.join(AQUI, "..", "salida", "muestra_infografia_" + sys.argv[3])
        meta, fi = generar_post(n, carpeta, pdf, sys.argv[3], destino)
        print(meta, fi["titulo"], "|", fi["sub"], "|", fi["norma"], "|", len(fi["casos"]), "casos,", len(fi["consejos"]), "consejos")
