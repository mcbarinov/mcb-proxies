set dotenv-load
project_name := `grep APP_NAME .env | cut -d '=' -f 2-`
version := `uv run python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])'`
docker_registry := `grep DOCKER_REGISTRY .env | cut -d '=' -f2`
docker_build_platform := env_var_or_default("DOCKER_BUILD_PLATFORM", "linux/amd64")
project_image := docker_registry+"/"+project_name

default: dev

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist src/*.egg-info

sync:
    uv sync --all-extras

build: clean lint audit test
    uv build

format:
    uv run ruff check --select I --fix src tests
    uv run ruff format src tests

lint: format
    uv run ruff check src tests
    uv run mypy src

audit:
    uv export --no-dev --all-extras --format requirements-txt --no-emit-project > requirements.txt
    uv run pip-audit -r requirements.txt --disable-pip
    rm requirements.txt
    uv run bandit --silent --recursive --configfile "pyproject.toml" src

test:
    uv run pytest tests

docker-lint:
    hadolint docker/Dockerfile

docker-build:
	docker build --build-arg python_version=${PYTHON_VERSION} --build-arg uv_version=${UV_VERSION} --platform {{docker_build_platform}} -t {{project_name}}:{{version}} --file docker/Dockerfile .
	docker tag {{project_name}}:{{version}} {{project_name}}:latest

docker-compose:
	cd docker && docker compose up --build

docker-upload: docker-build
	docker tag {{project_name}}:{{version}} {{project_image}}:{{version}}
	docker push {{project_image}}:{{version}}

publish: docker-upload
	cd ansible;	ansible-playbook -i hosts.yml --extra-vars="app_version={{version}}" -t publish playbook.yml
	git tag -a 'v{{version}}' -m 'v{{version}}'
	git push origin v{{version}}

dev:
    uv run python -m watchfiles --sigint-timeout=5 --grace-period=5  --sigkill-timeout=5 "python -m app.main" src
