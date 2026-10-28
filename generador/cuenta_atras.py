"""Cuenta atrás de diciembre: «Quedan X días para congelar los 9,99 €/mes».
Quien se suscribe antes de 2027 mantiene 9,99 €/mes mientras siga suscrito (compromiso con los alumnos).
No se menciona el precio de 2027 (no está decidido).

    python cuenta_atras.py programar          # 1, 11, 21 y 31 de diciembre a las 18:00
Mismo archivo en los dos repositorios: usa el carrusel (marca) de cada uno.
"""
import datetime as dt
import json
import os
import sys

from PIL import ImageDraw

import carrusel as C

AQUI = os.path.dirname(os.path.abspath(__file__))
COLA = os.path.join(AQUI, "..", "cola")
FECHAS = ["2026-12-01", "2026-12-11", "2026-12-21", "2026-12-31"]
FIN = dt.date(2027, 1, 1)


def dias_que_quedan(fecha):
    return (FIN - dt.date.fromisoformat(fecha)).days


def slides(fecha):
    W, M = C.W, C.M
    n = dias_que_quedan(fecha)
    imgs = []
    # 1. el numero
    img, d = C.lienzo("PRECIO DE LANZAMIENTO")
    y = C.TOP - 20
    if n == 1:
        d.text((M, y), "ÚLTIMO", font=C.fuente(C.TIT, 190), fill=C.CIAN)
        d.text((M, y + 200), "DÍA", font=C.fuente(C.TIT, 190), fill=C.BLANCO)
        y += 420
    else:
        d.text((M, y - 30), "QUEDAN", font=C.fuente(C.TIT, 90), fill=C.BLANCO)
        d.text((M - 8, y + 50), str(n), font=C.fuente(C.TIT, 330), fill=C.CIAN)
        d.text((M, y + 400), "DÍAS", font=C.fuente(C.TIT, 90), fill=C.BLANCO)
        y += 520
    f, l, t = C.ajustar(d, "para congelar tu precio a 9,99 €/mes", C.TIT, W - 2 * M, 150, 70, 40, 1.05)
    y = C.escribir(d, (M, y), l, f, t, C.BLANCO, 1.05) + 30
    C.pegatina(img, "Se mantiene mientras sigas suscrito", (M - 6, min(y, C.LIMITE - 70)), angulo=-3, tam=34)
    imgs.append(img)
    # 2. como funciona + que incluye
    img, d = C.lienzo("CÓMO FUNCIONA")
    y = C.TOP - 10
    pasos = ["Te suscribes al Plan Completo antes del 1 de enero de 2027.",
             "Pagas 9,99 €/mes y ese precio se queda congelado.",
             "Lo mantienes todos los meses mientras sigas suscrito."]
    for i, p in enumerate(pasos, 1):
        f, l, t = C.ajustar(d, p, C.TXT_SB, W - 2 * M - 150, 160, 36, 26, 1.3)
        alto = max(120, len(l) * int(t * 1.3) + 50)
        C.tarjeta(d, (M, y, W - M, y + alto))
        d.ellipse((M + 30, y + alto // 2 - 34, M + 98, y + alto // 2 + 34), fill=C.AMBAR)
        d.text((M + 64, y + alto // 2), str(i), font=C.fuente(C.DISPLAY, 44), fill=C.NAVY_TXT, anchor="mm")
        C.escribir(d, (M + 126, y + (alto - len(l) * int(t * 1.3)) // 2), l, f, t, C.BLANCO, 1.3)
        y += alto + 20
    y += 10
    d.text((M, y), "Y tienes acceso a:", font=C.fuente(C.SEMI, 36), fill=C.CIAN)
    y += 56
    for item in C.LISTA_CTA[:3]:
        cx, cy = M + 18, y + 20
        d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=C.CIAN)
        d.line((cx - 8, cy, cx - 2, cy + 7, cx + 9, cy - 7), fill=C.NAVY_TXT, width=4)
        d.text((cx + 34, cy), item, font=C.fuente(C.TXT_SB, 32), fill=C.BLANCO, anchor="lm")
        y += 56
    C.pie(d, "Desliza  >")
    imgs.append(img)
    # 3. cierre
    img, d = C.lienzo("NO LO DEJES PARA ENERO")
    y = C.TOP
    for texto, color in (("ENTRA AHORA", C.BLANCO), ("Y QUÉDATE CON", C.BLANCO), ("9,99 €/MES.", C.CIAN)):
        f, _, _ = C.ajustar(d, texto, C.TIT, W - 2 * M, 110, 104, 56, 1.0)
        d.text((M, y), texto, font=f, fill=color)
        y += 110
    y += 40
    d.rounded_rectangle((M, y, W - M, y + 150), radius=30, fill=C.CIAN)
    d.text((W // 2, y + 44), "Suscríbete en", font=C.fuente(C.SEMI, 34), fill=C.NAVY_TXT, anchor="mm")
    fu, _, _ = C.ajustar(d, C.URL_APP, C.DISPLAY, W - 2 * M - 80, 80, 62, 36, 1.0)
    d.text((W // 2, y + 102), C.URL_APP, font=fu, fill=C.NAVY_TXT, anchor="mm")
    y += 190
    d.text((W // 2, y), "Puedes empezar gratis y pasarte al Plan Completo cuando quieras",
           font=C.fuente(C.TXT_SB, 28), fill=(185, 200, 221), anchor="mm")
    C.pie(d, "Enlace en la bio")
    imgs.append(img)
    return imgs


def texto(fecha):
    n = dias_que_quedan(fecha)
    gancho = "⏳ Último día para congelar tu precio a 9,99 €/mes." if n == 1 else \
        f"⏳ Quedan {n} días para congelar tu precio a 9,99 €/mes."
    return "\n\n".join([
        gancho,
        "Quien se suscriba al Plan Completo antes del 1 de enero de 2027 mantiene los 9,99 €/mes "
        "todos los meses mientras siga suscrito.",
        "Exámenes oficiales resueltos y justificados, supuestos prácticos y mucho más en "
        f"{C.URL_APP} (enlace en la bio). Puedes empezar gratis.",
        "#oposicionesandalucia #oposiciones #preciocongelado",
    ])


def programar():
    for fecha in FECHAS:
        clave = fecha + "_tarde"
        salida = os.path.join(COLA, clave)
        if os.path.exists(os.path.join(salida, "meta.json")):
            print(clave, "ya existe: no se toca")
            continue
        os.makedirs(salida, exist_ok=True)
        imgs = slides(fecha)
        nombres = []
        for i, im in enumerate(imgs):
            C.puntos(im, i, len(imgs))
            n = f"{i + 1:02d}.jpg"
            im.save(os.path.join(salida, n), "JPEG", quality=90, optimize=True, progressive=True)
            nombres.append(n)
        open(os.path.join(salida, "caption.txt"), "w", encoding="utf-8").write(texto(fecha))
        meta = {"fecha": fecha, "franja": "tarde", "id": f"cuenta-atras-{fecha}", "formato": "cuenta_atras",
                "tema": "promo", "convocatoria": "", "caso": "", "imagenes": nombres}
        json.dump(meta, open(os.path.join(salida, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        print(f"{clave}: quedan {dias_que_quedan(fecha)} días")


if __name__ == "__main__":
    programar()
