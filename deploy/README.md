# deploy

```powershell
cp deploy/.env.example deploy/.env      # MEILI_MASTER_KEY üret: openssl rand -hex 24
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
cd pipeline; uv run vadibook build --push --meili-key $env:MEILI_MASTER_KEY
```

Web uygulaması Meilisearch'e **sadece-arama** anahtarıyla bağlanır (master key asla web'e girmez):

```bash
curl -H "Authorization: Bearer $MEILI_MASTER_KEY" -H "Content-Type: application/json" -X POST localhost:7700/keys \
  -d '{"name":"vadibook-web-search","actions":["search"],"indexes":["utterances"],"expiresAt":null}'
```

Dönen `key` → `web/.env.local` içinde `MEILI_SEARCH_KEY`. Meilisearch portu yalnız 127.0.0.1'e bağlıdır; dışarıya
sadece Next.js'in `/api/search` proxy'si açılır.
