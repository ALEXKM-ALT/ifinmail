.PHONY: all icons run dev clean install uninstall deb

all: icons

icons:
	python3 scripts/generate_icons.py

run:
	./run.sh

dev:
	ELECTRON_DEV=1 npx electron . --no-sandbox

clean:
	rm -rf dist/ out/ node_modules/.cache

install:
	@echo "Installing ifinmail desktop..."
	@mkdir -p $(HOME)/.local/share/applications
	@mkdir -p $(HOME)/.local/share/icons/hicolor/{48x48,64x64,128x128,256x256}/apps
	@cp assets/icon-48.png $(HOME)/.local/share/icons/hicolor/48x48/apps/ifinmail.png
	@cp assets/icon-64.png $(HOME)/.local/share/icons/hicolor/64x64/apps/ifinmail.png
	@cp assets/icon-128.png $(HOME)/.local/share/icons/hicolor/128x128/apps/ifinmail.png
	@cp assets/icon-256.png $(HOME)/.local/share/icons/hicolor/256x256/apps/ifinmail.png
	@sed 's|Exec=ifinmail-desktop|Exec=$(PWD)/run.sh|' ifinmail.desktop > $(HOME)/.local/share/applications/ifinmail.desktop
	@update-desktop-database $(HOME)/.local/share/applications 2>/dev/null || true
	@echo "Done. You can now launch ifinmail from your app menu."
	@echo "To set as default mail app: xdg-mime default ifinmail.desktop x-scheme-handler/mailto"

uninstall:
	rm -f $(HOME)/.local/share/applications/ifinmail.desktop
	rm -f $(HOME)/.local/share/icons/hicolor/*/apps/ifinmail.png
	-update-desktop-database $(HOME)/.local/share/applications 2>/dev/null

deb:
	@echo "Building .deb package via electron-builder..."
	npx electron-builder --linux deb
