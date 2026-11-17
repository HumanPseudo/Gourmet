# Changelog

## v1.3 (2026-11-17)

### Added — 1.5 Menú mejorado

- Fotos de platos con validación de formato y tamaño (2 MB), storage Supabase-ready.
- Badges de producto con icono SVG obligatorio.
- Variantes y complementos: grupos de opciones, mínimos/máximos, precio delta.
- Opciones condicionales por grupo padre.
- Specials por categoría con reglas de disponibilidad (día/semana, fechas, horas).
- Bandera `requires_preparation` para productos de entrega directa.

### Added — 1.6 Ciclo de vida de orden y cuenta unificada

- Seguimiento público QR con estado en vivo y listado "Mis pedidos".
- Edición/cancelación de items pendientes por el cliente.
- Motor de transiciones por rol con reversa de inventario y registro de merma.
- KDS continuo y panel de mesero "Para entregar" (también como modal en POS).
- Varias cuentas abiertas por mesa con total unificado y cobro individual o total.
- Auto-cierre configurable (`AUTO_CLOSE_MINUTES`) tras pago + todo servido.
- Mesa sticky en POS; reasignación de mesa como acción explícita.

### Changed

- Servir deja de ser acción de cocina: el KDS llega hasta `ready`.
- Cierre de orden bloqueado si quedan items sin servir/cancelar.
- Modales del POS imperativos (cierran con ✕, clic fuera y Escape).

### Fixed

- Colapso de varias órdenes abiertas por mesa en el piso del POS.
- 404 del cliente al reasignar una orden de mesa.
- Pedidos de una mesa apareciendo en el listado de otra.
- Expresiones Alpine CSP sin globals (`parseFloat`) movidas a métodos del componente.
- Orden de carga de scripts: `pos.js` antes de Alpine para registrar el componente.

---

## v1.2 (2026-09-29)

...

---

## v1.1 (2026-07-05)

### Added

- Audit logging (ISO 27001): `AuditLog` model tracks user actions on 12 critical
  endpoints — order create/close/pay/reopen/split, inventory adjust/delete, daily close.
- Audit log browser at `/pos/audit-logs/` (admin only).
- Inventory management: CRUD from UI, stock adjustments, inline edit, delete with
  confirmation.
- Inventory valuation: total stock value card, low-stock count, value column per item.
- Cook-time inventory deduction: stock deducted when kitchen marks item as `preparing`,
  not at order creation.
- "Used today" report at `/pos/inventory/used-today/`.
- Low-stock alerts in POS: "⚠ Bajo stock" badge, products disabled when stock < 1
  portion.
- Colombian peso format filter (`$ 1.250,00`).
- Orders list redesigned as cards with pending balance.
- Kitchen view grouped by table.

### Changed

- Inventory deduction moved from `add_item()` to `set_item_status()` (pending →
  preparing).
- Movement reference changed from `order:auto` to `cocina:preparado`.
- Seed now uses `set_item_status()` for preparing items.

### Fixed

- Seed cleanup handles both `order:auto` and `cocina:preparado` references.
- `.gitignore`: added `.idea/`, `*.log`, `htmlcov/`, `.coverage`,
  `docker-compose.override.yml`.
