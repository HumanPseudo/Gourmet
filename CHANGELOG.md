# Changelog

## v1.1 (2026-07-05)

### Added
- Audit logging (ISO 27001): `AuditLog` model tracks user actions on 12 critical endpoints — order create/close/pay/reopen/split, inventory adjust/delete, daily close.
- Audit log browser at `/pos/audit-logs/` (admin only).
- Inventory management: CRUD from UI, stock adjustments, inline edit, delete with confirmation.
- Inventory valuation: total stock value card, low-stock count, value column per item.
- Cook-time inventory deduction: stock deducted when kitchen marks item as `preparing`, not at order creation.
- "Used today" report at `/pos/inventory/used-today/`.
- Low-stock alerts in POS: "⚠ Bajo stock" badge, products disabled when stock < 1 portion.
- Colombian peso format filter (`$ 1.250,00`).
- Orders list redesigned as cards with pending balance.
- Kitchen view grouped by table.

### Changed
- Inventory deduction moved from `add_item()` to `set_item_status()` (pending → preparing).
- Movement reference changed from `order:auto` to `cocina:preparado`.
- Seed now uses `set_item_status()` for preparing items.

### Fixed
- Seed cleanup handles both `order:auto` and `cocina:preparado` references.
- `.gitignore`: added `.idea/`, `*.log`, `htmlcov/`, `.coverage`, `docker-compose.override.yml`.
