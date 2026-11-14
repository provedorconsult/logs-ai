---
name: logs-ai-stack
description: Gerar um pacote privado por perfil e implantar core, coletor e PostgreSQL logs-ai no projeto correto do Dokploy com fonte fixada em SHA completo.
---

# Preparar

Leia `AGENTS.md`, `docs/NEW-SERVER.md` e `docs/RUNBOOK.md`.
Escolha instalação nova (`deploy/standalone.compose.yml`) ou coletor anexado a
banco logs-ai existente (`deploy/mikrotik.compose.yml`). Não sobrepor o pacote
novo ao volume já inicializado. Descubra o projeto/ambiente corretos via API.

1. Copiar exemplo de perfil para `work/`, adaptar IPs/portas/roteadores/ações e
   eventos exigidos. Manter credenciais fora do perfil. Confirmar rota e origem
   real, sem wildcard ou faixas na allowlist. Até 32 IPs distintos.
2. Validar checkout/remoto/CI. Rodar `scripts/prepare_installation.py --profile
   work/site.json --revision <SHA-completo-publicado> --output work/site01`.
   Saída nova, diretório 700/arquivos 600. `.env` tem senha aleatória; não imprimir.
3. Preservar `.env`, manifesto e scripts correspondentes. Não gerar nova senha
   para atualizar um volume. Use skill `logs-ai-postgres` para o estado do banco.

## Dokploy

- Validar transporte/token e OpenAPI efetivo; não supor contrato de outra versão.
- Ler projeto/ambiente/recursos antes de criar; não reutilizar recurso alheio ou
  duplicar um deploy após timeout sem consultar o resultado anterior.
- Criar Compose raw dentro do ambiente certo (`compose.create`, se presente
  no contrato), usando o artefato gerado. Deixar comando nativo vazio; não injetar
  shell no comando de Compose. `autoDeploy=false`; conferir nome Docker/volume.
- Salvar ambiente **completo** do recurso novo via `compose.saveEnvironment`
  com arquivo protegido; conferir `compose.one` em memória sem expor env.
  Confirmar origem raw, artefato, SHA, bindings e ausência de alterações alheias.
- Capturar deployments anteriores; usar título único em `compose.deploy` e
  correlacionar exatamente o novo ID/título. Esperar `done`; API 200 não basta.
- Conferir no build checkout do Git SHA, digest/label OCI, `/health` de core e
  coletor com `X-App-Revision` igual, PostgreSQL/schema e estado sem reinícios.
  Guardar recibo e APP_TEST_URLs reais no armazenamento operacional privado.

## Atualizar ou recuperar

Antes de qualquer atualização, snapshot autoritativo completo do Compose/env e
journal durável de intenção/etapas. Não substituir env parcial nem apagar arquivo
preexistente num cleanup sem prova de propriedade. Se update e saveEnvironment
divergirem, reconciliar ambos com o snapshot antes de novo deploy/rollback.
Preservar nome do projeto, volume, credenciais e compatibilidade de migrations.

Este caminho raw usa Git SHA completo. `scripts/deploy.py` e o workflow legado
implementam outro contrato, baseado em tag protegida/snapshot/runner; não usar
esse cliente em recurso novo sem validar suas precondições nem enfraquecer gates.
GitHub integrado não comprova CD ativa. Seguir `logs-ai-validation` para aceite
funcional e `logs-ai-mikrotik` para entrega à equipe de redes.
