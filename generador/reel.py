"""Convierte un carrusel ya generado en un Reel vertical (1080x1920, ~15 s).

    pregunta + cuenta atras de 5 s (con pitidos)  ->  solucion (5 s)  ->  llamada a la app (3 s)

Reutiliza las diapositivas del carrusel (misma marca y diseño) y las coloca en un lienzo 9:16.
Usa el ffmpeg que trae el paquete imageio-ffmpeg; el audio son pitidos sintetizados (sin derechos).

    python reel.py cola/2026-10-23_mediodia      # prueba sobre una carpeta de la cola
"""
import math
import os
import struct
import subprocess
import sys
import tempfile
import wave

from PIL import Image, ImageDraw

import carrusel as C

W, H = 1080, 1920
ARRIBA = (H - C.H) // 2  # el carrusel (1350 de alto) va centrado: 285 px arriba y abajo

# colores de la marca, sacados del modulo del carrusel de cada cuenta
OSCURO = getattr(C, "NAVY", (11, 21, 51))
FONDO = getattr(C, "FONDO", (243, 246, 251))
ACENTO = getattr(C, "AZUL", getattr(C, "CIAN", (0, 153, 255)))
VERDE = getattr(C, "VERDE", (52, 199, 120))
TEMA_OSCURO = sum(FONDO) < 200  # Local Andalucia usa fondo oscuro
TEXTO = (255, 255, 255) if TEMA_OSCURO else OSCURO
TIT = getattr(C, "TIT", "segoeuib.ttf")

SEGUNDOS_PREGUNTA = 5
SEGUNDOS_SOLUCION = 5
SEGUNDOS_CTA = 3


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def lienzo(diapositiva, arriba, abajo=None, color_abajo=None):
    img = Image.new("RGB", (W, H), FONDO)
    img.paste(Image.open(diapositiva).convert("RGB"), (0, ARRIBA))
    d = ImageDraw.Draw(img)
    # tapa el pie del carrusel ("Desliza para la solucion" y los puntos): en un video no aplica
    d.rectangle((0, ARRIBA + C.H - 140, W, ARRIBA + C.H), fill=FONDO)
    f, _, _ = C.ajustar(d, arriba, TIT, W - 120, 120, 84, 48, 1.0)
    d.text((W // 2, ARRIBA // 2 + 10), arriba, font=f, fill=TEXTO, anchor="mm")
    if abajo:
        f2, _, _ = C.ajustar(d, abajo, TIT, W - 120, 120, 76, 40, 1.0)
        d.text((W // 2, ARRIBA + C.H + (H - ARRIBA - C.H) // 2), abajo, font=f2, fill=color_abajo or ACENTO, anchor="mm")
    return img, d


def marco_cuenta_atras(diapositiva, quedan):
    img, d = lienzo(diapositiva, "¿SABRÍAS RESPONDER?")
    cy = ARRIBA + C.H + (H - ARRIBA - C.H) // 2
    r = 95
    # anillo de progreso
    d.ellipse((W // 2 - r, cy - r, W // 2 + r, cy + r), outline=(200, 205, 215) if not TEMA_OSCURO else (60, 70, 110), width=14)
    fin = -90 + 360 * quedan / SEGUNDOS_PREGUNTA
    d.arc((W // 2 - r, cy - r, W // 2 + r, cy + r), start=-90, end=fin, fill=ACENTO, width=14)
    d.text((W // 2, cy), str(quedan), font=C.fuente(TIT, 110), fill=TEXTO, anchor="mm")
    return img


def pitidos(ruta, duracion):
    """Un pitido por segundo durante la cuenta atras y uno mas agudo al mostrar la solucion."""
    fs = 44100
    muestras = [0.0] * int(fs * duracion)

    def pitido(t0, hz, dur=0.12, vol=0.35):
        for i in range(int(fs * dur)):
            n = int(fs * t0) + i
            if n < len(muestras):
                env = math.sin(math.pi * i / (fs * dur))
                muestras[n] += vol * env * math.sin(2 * math.pi * hz * i / fs)

    for s in range(SEGUNDOS_PREGUNTA):
        pitido(s, 880)
    pitido(SEGUNDOS_PREGUNTA, 1320, dur=0.35, vol=0.45)
    with wave.open(ruta, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, m)) * 32767)) for m in muestras))


def generar_reel(carpeta, salida_nombre="reel.mp4"):
    """Crea carpeta/reel.mp4 a partir de 01.jpg (pregunta), 02.jpg (solucion) y la ultima (CTA)."""
    jpgs = sorted(f for f in os.listdir(carpeta) if f.endswith(".jpg") and f[:2].isdigit())
    if len(jpgs) < 3:
        raise ValueError(f"{carpeta}: hacen falta al menos 3 diapositivas")
    pregunta, solucion, cta = (os.path.join(carpeta, x) for x in (jpgs[0], jpgs[1], jpgs[-1]))

    with tempfile.TemporaryDirectory() as tmp:
        lista = []
        for i, quedan in enumerate(range(SEGUNDOS_PREGUNTA, 0, -1)):
            r = os.path.join(tmp, f"c{i}.png")
            marco_cuenta_atras(pregunta, quedan).save(r)
            lista.append((r, 1))
        r = os.path.join(tmp, "sol.png")
        lienzo(solucion, "LA RESPUESTA ES…", "¿LA ACERTASTE?", VERDE)[0].save(r)
        lista.append((r, SEGUNDOS_SOLUCION))
        r = os.path.join(tmp, "cta.png")
        lienzo(cta, "MÁS PREGUNTAS ASÍ", "ENLACE EN LA BIO")[0].save(r)
        lista.append((r, SEGUNDOS_CTA))

        concat = os.path.join(tmp, "lista.txt")
        with open(concat, "w", encoding="utf-8") as f:
            for ruta, dur in lista:
                f.write(f"file '{ruta}'\nduration {dur}\n")
            f.write(f"file '{lista[-1][0]}'\n")  # ffmpeg necesita repetir el ultimo
        audio = os.path.join(tmp, "audio.wav")
        total = SEGUNDOS_PREGUNTA + SEGUNDOS_SOLUCION + SEGUNDOS_CTA
        pitidos(audio, total)

        destino = os.path.join(carpeta, salida_nombre)
        subprocess.run([ffmpeg(), "-y", "-loglevel", "error",
                        "-f", "concat", "-safe", "0", "-i", concat, "-i", audio,
                        "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-profile:v", "high",
                        "-preset", "medium", "-crf", "23", "-c:a", "aac", "-b:a", "128k",
                        "-t", str(total), "-movflags", "+faststart", destino], check=True)
    return destino


if __name__ == "__main__":
    print(generar_reel(sys.argv[1]))
