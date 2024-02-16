start:
    docker compose up -d

start-oz:
    docker compose up -d ozon

start-wb:
    docker compose up -d wildberries

stop:
    docker compose down

restart:
    docker compose down
    docker compose up -d

logs:
    docker compose logs -f

build:
    docker compose build