#!/usr/bin/env bash
# Script to verify master branch protection is in place

echo "🔍 Verificando protección de rama master..."
echo ""

# Check pre-push hook
if [ -x .git/hooks/pre-push ] && grep -q "protected_branch='master'" .git/hooks/pre-push; then
    echo "✅ pre-push hook: ACTIVO"
else
    echo "❌ pre-push hook: FALTA"
fi

# Check commit-msg hook
if [ -x .git/hooks/commit-msg ] && grep -q "pattern=" .git/hooks/commit-msg; then
    echo "✅ commit-msg hook: ACTIVO"
else
    echo "❌ commit-msg hook: FALTA"
fi

# Check pre-commit hooks
if [ -f .pre-commit-config.yaml ]; then
    echo "✅ pre-commit config: EXISTE"
else
    echo "❌ pre-commit config: FALTA"
fi

echo ""
echo "📋 Protección configurada:"
echo "  - Push directo a master: BLOQUEADO"
echo "  - Commits: formato convencional requerido"
echo "  - Pre-commit: linting y formatting"
echo ""
