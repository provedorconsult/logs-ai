# logs-ai

Fundação do coletor de logs: API Python/FastAPI, PostgreSQL 17, migrations SQL e
homologação com Docker Compose. G02 corresponde à Fase 1. A ingestão MikroTik TCP/CEF é um incremento da G03;
IA ainda não está implementada. A interface web autenticada tem dashboard, relatórios
e gestão de clientes/usuários; ver [guia web](docs/WEB.md).

A documentação vigente está no [índice operacional](docs/README.md);
auditorias e resultados por versão estão em [docs/audits](docs/audits/README.md).

## Instalar outro servidor ou MikroTik

Comece pelo [guia de novo servidor](docs/NEW-SERVER.md) e pelo
[catálogo de skills para agentes](docs/SKILLS.md). Um perfil gera Compose com
PostgreSQL dedicado, core/coletor e scripts RouterOS por roteador, com senha
aleatória privada e fonte fixada em SHA completo. O verificador exige eventos
novos por origem e tipo. Há também um [runbook das falhas corrigidas](docs/RUNBOOK.md).

## Desenvolvimento

Requisitos: Python 3.12+, uv 0.13.6 e Docker com Compose.

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Os testes de integração exigem `TEST_DATABASE_URL` apontando para banco
**descartável**, com nome terminado em `_ci` ou `_test`; eles apagam o schema
`public`. Sem essa variável, esses testes são explicitamente pulados.
As dependências estão fixadas em `uv.lock`; `requirements.txt` é exportado do lock
com hashes como artefato derivado. O Docker usa uv 0.13.6 e exporta diretamente
de `uv.lock` com `--locked` durante o build; a CI verifica a exportação versionada.
Não editar `requirements.txt` manualmente. Após atualização intencional de dependências:

```sh
uv lock
uv export --locked --no-dev --no-emit-project --format requirements-txt > requirements.txt
```

## Homologação local

Copie `.env.example` para `.env`, proteja-o com modo 600 e configure
`POSTGRES_PASSWORD` com valor aleatório hexadecimal (sem caracteres reservados
em URL). O Compose injeta a conexão interna; o `DATABASE_URL` do arquivo é para
clientes executados fora do Compose e deve corresponder ao banco acessível.

```sh
docker compose up --build -d --wait
docker compose ps
curl --fail http://127.0.0.1:8000/health
```

O banco não publica porta no host. A aplicação publica apenas em loopback por
padrão. Para acesso pela Tailnet, configure endereço específico aprovado ou use
o proxy reverso do Dokploy; não abra firewall automaticamente.
Em ambientes com CA de proxy, passe o bundle confiável como secret BuildKit
`proxy_ca` ao build; a imagem não incorpora esse bundle.

`GET /health` retorna HTTP 200 com `{"status":"ok","database":"ok"}` somente
quando uma consulta PostgreSQL valida conectividade e schema inicial. Retorna
503 sem diagnósticos sensíveis se o banco ou schema não estiver disponível.
O core G02 mantém `/health`. O incremento autorizado de ingestão MikroTik usa
um coletor separado no mesmo projeto Dokploy e banco exclusivo de `logs-ai`:
[integração MikroTik](docs/MIKROTIK.md). O receptor TCP/CEF não expõe escrita HTTP.

## Banco e migrations

O processo de entrada aplica migrations antes do Uvicorn. Todas as migrations
pendentes executam em uma transação, sob advisory lock PostgreSQL. O histórico
guarda SHA-256 e rejeita alteração de migration aplicada ou retorno a release que
não contém migrations já registradas. Não editar SQL aplicado; criar novo arquivo
numerado. Falha de migration impede o início da aplicação. Backups/restauração
exigem procedimento próprio: voltar a imagem não desfaz schema.
O volume `postgres_data` persiste entre recriações. Nunca usar `down -v` em
homologação com dados a preservar. Em Swarm de múltiplos nós, fixe PostgreSQL no
nó que possui o volume ou use armazenamento externo; não depender apenas de
`node.role == manager` em um cluster com vários managers.

## Entrega contínua

Veja [docs/G02.md](docs/G02.md) para configurar Dokploy, CI/CD, execução e aceite.
A governança está em [AGENTS.md](AGENTS.md); a decisão humana autoriza G02 sem
converter as pendências técnicas da G01 em aprovações.
