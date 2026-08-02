#!/usr/bin/env bash
# Flujo de desarrollo para Gourmet
# Uso: bash scripts/dev-flow.sh <tipo> <descripcion>

set -e

TYPE=$1
DESCRIPTION=$2

if [ -z "$TYPE" ] || [ -z "$DESCRIPTION" ]; then
    echo ""
    echo "🐱 Flujo de Desarrollo - Gourmet"
    echo ""
    echo "Uso: bash scripts/dev-flow.sh <tipo> <descripcion>"
    echo ""
    echo "Tipos: feat, fix, docs, style, refactor, test, chore"
    echo ""
    echo "Ejemplo:"
    echo "  bash scripts/dev-flow.sh feat 'agregar categoría de postres'"
    echo ""
    echo "Flujo:"
    echo "  1. Crea branch desde staging"
    echo "  2. Hace commit con formato convencional"
    echo "  3. Push a origin"
    echo "  4. Abre PR hacia staging"
    echo ""
    exit 1
fi

# Validate type
VALID_TYPES="feat fix docs style refactor test chore build ci perf revert"
if ! echo "$VALID_TYPES" | grep -qw "$TYPE"; then
    echo "❌ Tipo inválido: $TYPE"
    echo "Tipos válidos: $VALID_TYPES"
    exit 1
fi

# Sanitize branch name
BRANCH_NAME=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
BRANCH_NAME="${TYPE}/${BRANCH_NAME}"

echo "🐱 Creando rama: $BRANCH_NAME"
echo ""

# Make sure we're on staging and up to date
git checkout staging
git pull origin staging

# Create feature branch
git checkout -b "$BRANCH_NAME"

echo ""
echo "✅ Rama '$BRANCH_NAME' creada desde staging"
echo ""
echo "📝 Siguiente paso:"
echo "  1. Haz tus cambios"
echo "  2. Ejecuta: git add . && git commit -m '$TYPE: $DESCRIPTION'"
echo "  3. Push:     git push -u origin $BRANCH_NAME"
echo "  4. PR:       gh pr create --base staging --title '$TYPE: $DESCRIPTION'"
echo ""
echo "O ejecuta todo junto:"
echo "  # ... editar archivos ..."
echo "  git add . && git commit -m '$TYPE: $DESCRIPTION' && git push -u origin $BRANCH_NAME"
echo "  gh pr create --base staging --title '$TYPE: $DESCRIPTION' --body 'Cambios en $DESCRIPTION'"
