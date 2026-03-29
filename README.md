# Telegram × GPT Researcher (Docker, ARM64)

Orchestration Docker pour **GPT Researcher** et un **bot Telegram** (liste blanche, appels HTTP asynchrones, envoi Markdown + PDF).

## Prérequis

- Docker et Docker Compose sur l’Orange Pi 5 (ARM64)
- Clés API configurées (voir `.env.example`)

## Démarrage

1. Copier l’environnement : `cp .env.example .env` puis éditer les secrets.
2. Construire et lancer : `docker compose up -d --build`
3. Sur Telegram : `/research votre question`

Le service `gpt-researcher` clone le dépôt officiel au build (`GPT_RESEARCHER_REF`, défaut `main`). L’image applique **Chromium** depuis Debian (pas de dépôt Google Chrome) et expose l’API sur le port `GPTR_HOST_PORT` (défaut `8000`).

## Licence du moteur

GPT Researcher : [assafelovic/gpt-researcher](https://github.com/assafelovic/gpt-researcher) (licence du projet amont).
