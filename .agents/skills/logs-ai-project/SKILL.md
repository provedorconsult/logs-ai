---
name: logs-ai-project
description: Reconstruir o contexto do logs-ai e coordenar instalação de um servidor de logs integrado com MikroTik, sem presumir acesso ou estado de entregas anteriores.
---

# Entrada e contexto

Trabalhe a partir da raiz do repositório. Leia `AGENTS.md`, `README.md`,
`docs/NEW-SERVER.md`, `docs/RUNBOOK.md` e `docs/DEPLOYMENT_PLAN.md`.
Este projeto tem core FastAPI, coletor privado TCP/CEF, PostgreSQL 17,
migrations transacionais e scripts RouterOS. Não há IA/dashboard nesta entrega.
G02 é Fase 1; ingestão é incremento de G03. Autorização não é aceite técnico.

## Reconstruir antes de agir

1. Inspecione checkout, diff e remoto; preserve trabalho alheio. Consulte estado
   publicado e evidências, mas confira novamente o destino real. Não usar IPs,
   IDs, tokens, senhas, host keys ou exceções HTTP de outra instalação.
2. Descubra ferramentas, credenciais por **nomes**, rede/proxy do runtime e
   instruções locais. Não imprimir valores nem solicitar segredos pelo chat.
3. Registre escopo humano vigente para host, Dokploy e roteadores. Reutilize a
   autorização existente aplicável; pergunte somente lacunas concretas que
   impeçam a execução. Preparar artefatos é independente do acesso remoto.
4. Obtenha instância, IP receptor, bind administrativo, portas, origens reais,
   RouterOS/SSH/host key e equipe aplicadora. Perfil em `work/`; exemplo em
   `deploy/profiles/example.json`. Não ler senhas de `/ppp secret`.

## Executar por etapas

- Host sem Dokploy: skill `logs-ai-dokploy`.
- Banco/volume/migrations: skill `logs-ai-postgres`.
- Pacote e deploy: skill `logs-ai-stack`.
- Scripts e leitura RouterOS: skill `logs-ai-mikrotik`.
- Comissionamento por origem: skill `logs-ai-validation`.

Abra os outros `SKILL.md` no diretório irmão, conforme a etapa; a menção aqui não
executa instalação nem delega a outro agente. Não criar subagentes implicitamente.

## Entregar

Publicar código após checks/diff/auditoria de segredos no escopo autorizado.
Registrar commit implantado, digest, projeto/ambiente/recurso, health, schema,
fluxos realmente observados, recuperação e pendências. Recibos com IPs reais e
snapshots/env ficam privados; relatório público não contém clientes/credenciais.
Não declarar CD ou aceite integral por YAML, API aceita ou testes locais.
Remover diagnósticos temporários próprios. Revisão independente pertence ao
Checker/Humanos; o Maker não se apresenta como Checker de si mesmo.
