# ─────────────────────────────────────────────────────────────────────────────
# Makefile BAGO — empaquetado, instalación y validación
# Uso desde la carpeta que contiene .bago/ y el script bago
# ─────────────────────────────────────────────────────────────────────────────

BAGO_DIR   := .bago
TOOLS      := $(BAGO_DIR)/tools
DIST       := dist
VERSION    := $(shell python3 -c "import json; print(json.loads(open('$(BAGO_DIR)/pack.json').read())['version'])" 2>/dev/null || echo "unknown")
TIMESTAMP  := $(shell date +%Y%m%d_%H%M%S)
PACK_NAME  := BAGO_$(VERSION)_$(TIMESTAMP)

# Shell (detecta zsh o bash)
SHELL_RC   := $(shell [ -f ~/.zshrc ] && echo ~/.zshrc || echo ~/.bashrc)
BAGO_PATH  := $(shell pwd)/bago

.PHONY: help banner validate pre-push install-hooks pack deploy install uninstall clean

# ─── Ayuda ────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  BAGO · Sistema de empaquetado"
	@echo "  ─────────────────────────────"
	@echo "  make banner     → muestra el cartel BAGO ACTIVO"
	@echo "  make validate   → valida manifest + state + pack"
	@echo "  make pre-push   → ejecuta gate antes de publicar a remoto"
	@echo "  make install-hooks → activa hooks versionados .githooks"
	@echo "  make pack       → crea zip limpio en dist/ (excluye dist/, state/, .git, __pycache__)"
	@echo "  make deploy     → crea zip limpio sin historial (para nuevos proyectos)"
	@echo "  make install    → instala alias 'bago' en $(SHELL_RC)"
	@echo "  make uninstall  → elimina alias 'bago' de $(SHELL_RC)"
	@echo "  make clean      → limpia __pycache__ del pack"
	@echo ""

# ─── Banner ───────────────────────────────────────────────────────────────────
banner:
	@python3 $(TOOLS)/bago_banner.py

# ─── Validación ───────────────────────────────────────────────────────────────
validate:
	@python3 $(TOOLS)/validate_pack.py

pre-push:
	@python3 bago pre-push --remote

install-hooks:
	@git config core.hooksPath .githooks
	@echo "  ✅ hooks Git activados: .githooks"
# ─── Pack: build_pack.py — clean, reproducible, no recursive dist ─────────────
pack:
	@echo ""
	@echo "  📋 Paso 1/2: validando pack..."
	@python3 $(TOOLS)/validate_pack.py
	@echo "  📦 Paso 2/2: creando zip limpio (excluye dist/, state/, __pycache__, .git)..."
	@python3 $(TOOLS)/build_pack.py --out $(DIST)
	@echo ""

# ─── Instalar alias global ────────────────────────────────────────────────────
install:
	@echo ""
	@echo "  📌 Instalando alias 'bago' en $(SHELL_RC) ..."
	@grep -q "alias bago=" $(SHELL_RC) && \
		echo "  ⚠️  Alias ya existe. Actualizado." && \
		sed -i.bak '/alias bago=/d' $(SHELL_RC) || true
	@echo "alias bago='python3 $(BAGO_PATH)'" >> $(SHELL_RC)
	@echo "  ✅ Añadido: alias bago='python3 $(BAGO_PATH)'"
	@echo "  ℹ️  Ejecuta: source $(SHELL_RC)"
	@echo "  ℹ️  Luego: bago  (desde cualquier carpeta)"
	@echo ""

# ─── Desinstalar alias ────────────────────────────────────────────────────────
uninstall:
	@echo ""
	@sed -i.bak '/alias bago=/d' $(SHELL_RC) && \
		echo "  ✅ Alias eliminado de $(SHELL_RC)" || \
		echo "  ⚠️  No se encontró alias bago en $(SHELL_RC)"
	@echo ""

# ─── Limpiar __pycache__ ──────────────────────────────────────────────────────
clean:
	@find $(BAGO_DIR) -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@echo "  ✅ __pycache__ limpiado"

# ─── Deploy: zip limpio sin historial ─────────────────────────────────────────
deploy:
	@echo ""
	@echo "  🚀 Generando ZIP de arranque limpio (sin historial)..."
	@python3 $(DIST)/source/make_clean_pack.py
	@echo ""
