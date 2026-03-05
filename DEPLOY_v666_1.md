# DEPLOY v666.1 — Distributed Architecture

## ARCHITECTURE
```
LOB Service (Curitiba)     --- WebSocket @depth@100ms + @aggTrade --> Binance
       | (shared memory)
       v
Scanner (Curitiba)         --- reads LOB memory (0ms) --> ConfluenceEngine (7 modules)
       |                        + Dynamic Fees (real-time API + BNB discount)
       v Redis Pub/Sub (orjson + nanosecond timestamps)
       +--> Singapore Executor (AWS ap-southeast-1) -> Binance API (<10ms)
       +--> Tokyo Executor (AWS ap-northeast-1)     -> Binance API (<15ms)
                     |
              Atomic State Machine (rollback on partial fill)
                     |
              Robin Hood Risk ($22 capital) + Auto-Earn (Simple Earn)
```

## QUICK START
```bash
cp .env.example .env
nano .env                              # fill API keys
docker compose build --no-cache        # auto-compiles Rust extension
docker compose up -d redis lob_service scanner
docker compose logs -f scanner
```

## DEPLOY EXECUTORS (AWS)
```bash
docker compose up -d singapore_executor tokyo_executor
```

## DOCKER SWARM (PRODUCTION)
```bash
docker swarm init
docker node update --label-add region=curitiba $(hostname)
docker stack deploy -c docker-compose.yml apex666
```

## MONITORING
```bash
docker compose logs lob_service | grep "LOB health"
docker compose logs scanner | grep "Fees refreshed"
docker exec apex666_redis redis-cli subscribe apex:v666:executions
docker compose logs | grep "ROLLBACK"
```

## RUST EXTENSION (OPTIONAL)
```bash
cd native/apex_lob && pip install maturin && maturin develop --release
```
