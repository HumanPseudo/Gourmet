# 🐱 Flujo de Desarrollo - Gourmet

## Ramas

```
master ← producción (protegida, no se puede push directo)
  ↑
staging ← integración (PRs aquí primero)
  ↑
feat/*, fix/* ← desarrollo (branches individuales)
```

## Flujo paso a paso

### 1. Crear una feature branch desde staging

```bash
bash scripts/dev-flow.sh feat "agregar categoría de postres"
```

Esto crea `feat/agregar-categoria-de-postres` desde `staging`.

### 2. Hacer cambios

```bash
# Editar archivos...
git add .
git commit -m "feat(menu): agregar categoría de postres"
```

### 3. Push y PR hacia staging

```bash
git push -u origin feat/agregar-categoria-de-postres
gh pr create --base staging --title "feat(menu): agregar categoría de postres"
```

### 4. Code review y merge a staging

- Revisar el PR
- Merge cuando esté listo

### 5. Deploy a producción

Cuando staging esté estable:
```bash
gh pr create --base master --title "release: v1.x.x" --body "Deploy staging → master"
```

## Commits

Formato convencional (requerido):
```
tipo(ámbito): descripción
```

Tipos:
- `feat` — nueva funcionalidad
- `fix` — corrección de bug
- `docs` — documentación
- `style` — formato (no afecta código)
- `refactor` — reestructurar código
- `test` — agregar/corregir tests
- `chore` — tareas de mantenimiento

Ejemplos:
```
feat(orders): agregar descuentos
fix(tax): corregir cálculo INC 8%
docs: actualizar guía de instalación
```

## Comandos útiles

```bash
# Verificar protección de master
bash scripts/protect-master.sh

# Ver PRs abiertos
gh pr list

# Ver diff de un PR
gh pr diff <number>

# Merge PR
gh pr merge <number> --squash
```

## Reglas

1. ❌ **NUNCA** hacer push directo a `master`
2. ✅ Siempre crear PR hacia `staging` primero
3. ✅ Usar formato convencional en commits
4. ✅ Pasar linting antes de commitear (pre-commit hooks)
5. ✅ Tests deben pasar antes de merge
