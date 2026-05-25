.PHONY: migrate run shell collectstatic deploy provision reload up down build logs ps shell-api migrate-api health backup restore-test firewall

# --- Django targets (local development) ---
migrate:
	python manage.py migrate

run:
	python manage.py runserver 0.0.0.0:8000

shell:
	python manage.py shell

collectstatic:
	python manage.py collectstatic --noinput

deploy:
	python manage.py check --deploy
	python manage.py collectstatic --noinput
	python manage.py migrate

# --- Docker targets (provisioning) ---
DOMAIN ?= $(or $(DOMAIN),)
COMPOSE_BIN := $(shell if docker compose version >/dev/null 2>&1; then printf 'docker compose'; else printf 'docker-compose'; fi)
DOCKER_COMPOSE = $(COMPOSE_BIN) --env-file provisioning/.env -f provisioning/docker/docker-compose.yml

provision:
	DOMAIN="$(DOMAIN)" provisioning/scripts/provision.sh

reload:
	$(DOCKER_COMPOSE) build --pull
	$(DOCKER_COMPOSE) up -d --remove-orphans
	@echo ""
	$(DOCKER_COMPOSE) ps

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

build:
	$(DOCKER_COMPOSE) build --pull

logs:
	$(DOCKER_COMPOSE) logs -f --tail=100

ps:
	$(DOCKER_COMPOSE) ps

shell-api:
	$(DOCKER_COMPOSE) exec api python manage.py shell

migrate-api:
	$(DOCKER_COMPOSE) exec api python manage.py migrate

health:
	$(DOCKER_COMPOSE) ps
	@echo ""
	@echo "=== API Health Check ==="
	@curl -s http://localhost:8000/health/ | python3 -m json.tool 2>/dev/null || echo "API not reachable"

backup:
	provisioning/scripts/backup_full.sh

restore-test:
	provisioning/scripts/restore_test.sh

firewall:
	provisioning/scripts/firewall.sh
