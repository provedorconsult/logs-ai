---
name: logs-ai-postgres
description: Provisionar e validar PostgreSQL 17 dedicado ao logs-ai, migrations, persistência, backup e recuperação sem tocar no banco administrativo do Dokploy.
---

# Contrato de dados

Leia `AGENTS.md`, `docs/NEW-SERVER.md`, `src/logs_ai/migrate.py` e migrations.
`deploy/standalone.compose.yml` provisiona PostgreSQL 17, banco/usuário `logs_ai`,
volume `postgres_data` e nenhuma porta publicada. O projeto Docker identifica o
volume físico; registrar o nome real, nó e montagem. Não confundir com o Compose
histórico de core, cujo banco é `logs_ai_test`, nem com PostgreSQL do Dokploy.

## Provisionar

1. Projeto novo: senha hex aleatória do pacote privado, volume novo do projeto,
   rede exclusiva. Core/coletor dependem da saúde do PostgreSQL. Não expor 5432.
2. Banco existente: identificar app e banco no mesmo projeto, rede compartilhada
   própria e URL esperada. Ler credencial somente em memória/armazenamento
   protegido. Nunca imprimir Config.Env, URL ou senha. Não criar outro volume
   para contornar erro de autenticação e perder acesso aos dados existentes.
3. Confirmar volume inicializado e credencial efetiva. `POSTGRES_PASSWORD` é de
   bootstrap; alterar env não muda senha do banco já inicializado. Rotação deve
   atualizar banco/clientes de forma coordenada, com recuperação preparada.

## Validar

- `/health` consulta conexão/schema e deve falhar com banco indisponível; realizar
  teste negativo em instalação descartável ou janela autorizada, não interromper
  banco com dados sem considerar dependentes.
- Migration atual `001_initial.sql`, advisory lock transacional e checksum.
  Conferir `schema_migrations` por leitura; não editar SQL aplicado. Não introduzir
  migrations desconhecidas para algum core/coletor que compartilhe o banco.
- Conferir eventos normalizados em `log_events` por fonte/janela/tipo e, quando
  necessário, identificador de teste sem publicá-lo. Não guardar payload bruto.
- Provar persistência por recriação controlada **sem remover volume**, com dado
  sintético próprio e comparação antes/depois. Não usar `down -v` no ambiente real.

## Backup e recuperação

Antes de evolução de schema, estabelecer pg_dump custom no armazenamento
protegido, integridade e restauração num banco descartável separado. Um dump
existente não prova restauração. Credenciais por env/cofre, não argumentos ou logs.
Voltar imagem não desfaz migrations; restauração apaga/sobrescreve dados apenas
no destino explicitamente planejado. Preservar banco atual e dependentes.
Em mais de um nó, volume local precisa de afinidade explícita; o pacote novo é
single-node Compose. Nunca testar contra produção com `TEST_DATABASE_URL`:
os testes de integração removem o schema e exigem guard de banco descartável.
