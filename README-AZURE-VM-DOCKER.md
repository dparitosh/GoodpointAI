# Azure VM deploy (Docker)

This repo can be deployed on an Azure Linux VM without installing Node/Python dependencies on the VM. You only need Docker.

## Prereqs

- Azure VM with inbound ports opened:
  - `8080` (web UI)
  - `7474` (Neo4j browser, optional)
  - `7687` (Neo4j bolt, optional)
  - `8011` (backend API, optional; UI proxies via `8080`)
- Docker + Docker Compose installed.

## Deploy

```bash
git clone https://github.com/dparitosh/graphTrace.git
cd graphTrace/agentic-restored

docker compose up -d --build
```

Open:
- UI: `http://<vm-public-ip>:8080`
- API (optional): `http://<vm-public-ip>:8011/health`
- Neo4j browser (optional): `http://<vm-public-ip>:7474` (default user `neo4j`, password `neo4jpassword`)

## Config

Defaults are set in `docker-compose.yml` for a quick start (Postgres + Neo4j + backend + UI).
For production, change passwords and move secrets into your Azure configuration.

## Stop

```bash
docker compose down
```

To remove volumes too:

```bash
docker compose down -v
```
