# Instagram automático · @administrativo_local_andalucia

Publica cada día a las 20:30 (19:30 en invierno) un carrusel generado a partir de los Excel corregidos.

```
PC (cada lunes)                                    GitHub Actions (cada día)
Excel → filtro de calidad → carruseles → cola/  →  publicador → API de Instagram
```

## Calendario

| L | M | X | J | V | S | D |
|---|---|---|---|---|---|---|
| Test | Test | Supuesto | Test | Test | Supuesto | Test |

Formatos:
- **Test oficial**: pregunta · solución + artículo literal · la trampa · llamada a la app.
- **Supuesto tipo test**: el caso · pregunta · solución · trampa · llamada.
- **Supuesto de desarrollo**: el caso · pregunta · respuesta modelo · lo que dice la ley · llamada.

## Carpetas

| Carpeta | Qué es |
|---|---|
| `generador/datos.py` | Lee los Excel y aplica el filtro de calidad. `python datos.py` muestra el informe. |
| `generador/carrusel.py` | Dibuja las diapositivas. |
| `generador/caption.py` | Escribe el texto de cada publicación. |
| `generador/generar_cola.py` | Rellena `cola/` hasta tener 30 días preparados. |
| `cola/AAAA-MM-DD/` | Lo que se publicará ese día: imágenes, `caption.txt`, `meta.json`. |
| `estado/usadas.json` | Preguntas ya usadas: nunca se repiten. |
| `estado/publicadas.json` | Registro de lo publicado, con el enlace a cada post. |
| `publicador/publicar.py` | Publica en Instagram (se ejecuta en GitHub). |

## Tareas habituales

- **Quitar o cambiar una publicación** antes de que salga: borra o edita la carpeta de ese día en `cola/` y sube el cambio. Para regenerarla, borra la carpeta y ejecuta `actualizar_cola.bat`.
- **Que una pregunta no salga nunca**: corrígela en el Excel, o añade su id (está en `meta.json`) a `estado/usadas.json`.
- **Ver qué se descarta y por qué**: `python generador/datos.py`.
- **Probar sin publicar**: GitHub > Actions > Publicar en Instagram > Run workflow, con el modo `simular` o `comprobar`.

## Configuración inicial (una sola vez)

1. **Cuenta profesional**: en la app de Instagram, Configuración > Tipo de cuenta > Cambiar a cuenta profesional (Empresa).
2. **Página de Facebook**: crea una página "Administrativo Local Andalucía" y vincúlala a la cuenta de Instagram (Configuración de la página > Cuentas vinculadas > Instagram).
3. **App de Meta**: en developers.facebook.com > Mis apps > Crear app > tipo *Empresa*. Añade el producto **Instagram** (API con inicio de sesión de Facebook).
4. **Token**: en developers.facebook.com/tools/explorer, elige tu app y genera un token de usuario con los permisos `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement` y `business_management`.
5. **Guardar el token en GitHub**: ejecuta `python publicador/configurar_token.py`. Te pide el App ID, el App Secret y el token sin mostrarlos en pantalla, y los guarda como secretos del repositorio. El token que guarda es de página y no caduca.
6. **Comprobar**: GitHub > Actions > Publicar en Instagram > Run workflow > modo `comprobar`. Debe mostrar `Token correcto. Cuenta: @administrativo_local_andalucia`.

Mientras la app de Meta esté en modo desarrollo, solo puede publicar en cuentas cuyo dueño sea administrador de la app, que es tu caso. No hace falta pasar la revisión de Meta para publicar en tu propia cuenta.

## Si algo falla

GitHub te manda un email cuando una ejecución falla. Los errores más comunes:
- **Token caducado o revocado** (por ejemplo, si cambias la contraseña de Facebook): repite el paso 5.
- **Queda poca cola**: el aviso aparece en Actions. Ejecuta `actualizar_cola.bat`.
