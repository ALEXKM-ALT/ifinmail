.PHONY: migrate makemigrations run shell shell_plus dbshell check test coverage lint lint-fix \
        format fmt format-check collectstatic deploy createsuperuser audit clean \
        provision reload rebuild up down build restart pull logs ps shell-api migrate-api manage \
        health backup restore-test firewall makemessages compilemessages

# --- Django targets (local development) ---
PORT ?= 8000

migrate:
	python manage.py migrate

makemigrations:
	python manage.py makemigrations

run:
	python manage.py runserver 0.0.0.0:$(PORT)

shell:
	python manage.py shell

shell_plus:
	python manage.py shell_plus

dbshell:
	python manage.py dbshell

check:
	python manage.py check

TEST_ARGS ?=

test:
	python -m pytest --reuse-db -n auto $(TEST_ARGS)

coverage:
	python -m pytest --reuse-db -n auto --cov=backend --cov-report=term --cov-report=html $(TEST_ARGS)

TARGET ?= .

lint:
	ruff check $(TARGET)

lint-fix:
	ruff check --fix $(TARGET)

format: fmt

fmt:
	ruff format $(TARGET)

format-check:
	ruff format --check $(TARGET)

collectstatic:
	python manage.py collectstatic --noinput --clear

createsuperuser:
	python manage.py createsuperuser

audit:
	python manage.py audit_structure

deploy:
	@if python -c "import os; exit(0 if os.environ.get('DJANGO_SETTINGS_MODULE','').endswith('production') else 1)" 2>/dev/null; then \
		echo "Deploying..."; \
	else \
		echo "ERROR: DJANGO_SETTINGS_MODULE is not set to a production settings file. Aborting."; \
		exit 1; \
	fi
	python manage.py check --deploy
	python manage.py collectstatic --noinput --clear
	python manage.py compilemessages
	python manage.py migrate

clean:
	find . \( -name .venv -o -name .git -o -name .ruff_cache -o -name .pytest_cache \) -prune -o \
		-type d -name __pycache__ -exec rm -rf {} + -prune
	find . \( -name .venv -o -name .git \) -prune -o -type f -name '*.pyc' -delete
	rm -rf ./staticfiles/

# --- Docker targets (provisioning) ---
DOMAIN ?=
COMPOSE_BIN := $(shell if docker compose version >/dev/null 2>&1; then printf 'docker compose'; else printf 'docker-compose'; fi)
DOCKER_COMPOSE = $(COMPOSE_BIN) --env-file provisioning/.env -f provisioning/docker/docker-compose.yml

provision:
	@if [ -z "$(DOMAIN)" ]; then echo "ERROR: DOMAIN is required. Usage: make provision DOMAIN=example.com"; exit 1; fi
	DOMAIN="$(DOMAIN)" provisioning/scripts/provision.sh

reload:
	$(DOCKER_COMPOSE) build --pull
	$(DOCKER_COMPOSE) down --remove-orphans
	$(DOCKER_COMPOSE) up -d --remove-orphans
	@echo ""
	$(DOCKER_COMPOSE) ps

rebuild:
	make reload

up:
	$(DOCKER_COMPOSE) up -d

down:
	$(DOCKER_COMPOSE) down

restart:
	$(DOCKER_COMPOSE) restart

build:
	$(DOCKER_COMPOSE) build --pull

pull:
	$(DOCKER_COMPOSE) pull

logs:
	$(DOCKER_COMPOSE) logs -f --tail=100

ps:
	$(DOCKER_COMPOSE) ps

shell-api:
	$(DOCKER_COMPOSE) exec -it api python manage.py shell

migrate-api:
	$(DOCKER_COMPOSE) exec api python manage.py migrate

manage:
	$(DOCKER_COMPOSE) exec api python manage.py "$(CMD)"

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

# --- i18n ---
LOCALE ?= en

makemessages:
	python manage.py makemessages -l $(LOCALE) --ignore=.venv --ignore=staticfiles --ignore=media --ignore=node_modules

compilemessages:
	python manage.py compilemessages
