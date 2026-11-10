# Hallazgos de arquitectura

Documento vivo con problemas detectados durante la refactorización del
issue #11. No son parte del alcance de ese issue (que cubre reorganización
de plantillas, eliminación de emojis y visibilidad de enlaces por rol),
sino deuda técnica a abordar en próximos alcances.

## 1. `audit_logs.html` extiende una base inexistente

`gourmet/templates/pos/reports/audit_logs.html:1` hace
`{% extends "pos/base.html" %}`, pero esa plantilla no existe. Abrir
`pos/audit-logs/` lanza `TemplateDoesNotExist` (500). Además usa
`{% block title %}`, mientras que `base.html` define `head_title`.

**Propuesta:** cambiar a `{% extends "base.html" %}` y renombrar el bloque
a `head_title`. Conviene un test que renderice la vista `audit_logs`.

## 2. Inconsistencia de autorización en inventario

Las vistas de inventario usan `@staff_member_required`
(`gourmet/apps/inventory/views.py`), que deja entrar a **cualquier**
usuario `is_staff` (incluidos `waiter` y `kitchen`) por URL directa,
aunque el enlace "Inventario" solo se muestra a `admin`. La UI y el
backend no coinciden.

**Propuesta:** reemplazar por `@role_required("admin")` para alinear la
restricción con lo que muestra el navbar.

## 3. Nombres de rol como strings mágicos

`"waiter"`, `"kitchen"` y `"admin"` se repiten en decoradores
(`role_required(...)`), plantillas, seeds y las nuevas propiedades de
`User`. Un typo no se detecta hasta runtime.

**Propuesta:** centralizar en constantes o un `TextChoices`/enum
(p. ej. `Role.ADMIN`) y referenciarlo desde decoradores y seeds.

## 4. Estilos inline en todas las plantillas

Las plantillas usan `style="..."` inline en lugar de clases. Tailwind
está configurado (`static/bundles/main.css`) pero apenas se usa. Esto
dificulta el mantenimiento, el theming y la consistencia visual.

**Propuesta:** migrar progresivamente a clases utilitarias/components y
extraer el navbar a un parcial reutilizable.

## 5. El bundle CSS no se genera en test/dev

`tests/server/test_server.py::test_static_css_bundle` falla porque
`static/bundles/main.css` no existe cuando Tailwind no se ha compilado.
Es un fallo de entorno, no de código, pero ensucia la señal de la suite.

**Propuesta:** compilar el bundle en el setup de los server-tests, o
marcar el test para que dependa explícitamente del paso de build.

## 6. `gourmet/urls.py` monolítico

Define ~60 rutas planas en un solo archivo. Mezcla POS, órdenes,
inventario, reservas, mesas, QR y menú público.

**Propuesta:** dividir por app con `include()` (p. ej.
`path("pos/inventory/", include("gourmet.apps.inventory.urls"))`) para
mejorar la legibilidad y la cohesión por dominio.

## 7. Síntoma no reproducible: "el cocinero se loguea como admin"

El issue menciona que el cocinero "se loguea como admin automáticamente"
tras un 403. No existe ningún código que escale privilegios tras el
login (sin middleware de auto-login ni de impersonación, un único backend
de autenticación). Lo más probable es una sesión previa de admin cacheada
en el navegador durante las pruebas. El 403 en sí ya está corregido en el
issue #11 (los enlaces ahora se filtran por rol). Se deja documentado
para descartarlo; si se reproduce, adjuntar pasos y cookies de sesión.
