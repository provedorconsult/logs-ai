---
name: logs-ai-validation
description: Comissionar e testar ponta a ponta uma instalação logs-ai MikroTik, exigindo revisão correta e eventos novos persistidos por origem antes de emitir aceite funcional.
---

# Preparação

Leia `AGENTS.md`, `docs/NEW-SERVER.md`, `docs/RUNBOOK.md` e o manifesto privado do
pacote. Registrar versão/escopo; não repetir evidências históricas como atuais.
A verificação automática nova exige métricas por origem e identidade de processo;
o serviço histórico 827fa14 não tem esse contrato e precisa de atualização
planejada para usar o novo verificador. Não fazer fallback que declare PASS.

## Testes do código

Executar Ruff, formatação e pytest. Usar PostgreSQL 17 **descartável** com
`TEST_DATABASE_DISPOSABLE=true`, porta esperada explícita e nome terminado em
`_ci`/`_test`; ler `tests/database_guard.py` antes. Sem banco, testes pulados não
comprovam integração. CI precisa testar/buildar a revisão efetivamente implantada.

## Evidência remota

1. Correlacionar deployment específico terminado em `done`, SHA Git do build,
   digest/label e `X-App-Revision` nos dois `/health`. Conferir bindings, DB,
   migrations/checksum, logs sanitizados, volumes e reinícios. Não comparar só
   abreviação de SHA nem confundir 200 antigo com release nova.
2. Selecionar transporte explícito do runtime. Executar `verify_installation.py
   baseline --manifest <manifest> --output <arquivo-novo-privado>` antes dos
   eventos. `DOKPLOY_TRANSPORT=direct` ou proxy aprovado; não alterar TLS/rotas.
3. A equipe gera os tipos exigidos em **cada** roteador, usando contas de teste.
   `/user` atualizado não satisfaz `ppp.user.updated`; criação PPP não comprova
   edição/remoção PPP. Gerar precisamente os casos que se pretende aceitar.
4. Executar `verify_installation.py verify --manifest <manifest> --baseline
   <baseline> --output <recibo-novo>`. Exigir PASS: deltas após commit por fonte e
   tipo, mesmo manifesto/SHA/processo, fila drenada. Reinício exige repetir o
   baseline e os testes. Eventos antigos ou de outro roteador não satisfazem.
5. Confirmar por SQL somente leitura quando for necessário atribuir à conta
   exata do teste; o verificador compara contadores, não identifica clientes.
   Não publicar usernames/ator/comentários. O evento não contém before/after de
   campos nem comando bruto; não afirmar validação do valor de um comentário.
6. Verificar persistência/recuperação em ambiente apropriado. Testes sintéticos,
   readiness e fluxo real são evidências distintas. Limpeza remove só recursos
   próprios e apaga apenas snapshots cuja criação própria foi comprovada.

## Entrega e pendências

Relatar commit do código e de evidências, revisão/digest implantados, tipos e
origens realmente observados, contadores de ignorados/rejeitados/erros e limites
de fila em memória/syslog sem ACK transacional. Não prometer exatamente uma
entrega ou replay. Explicar qualquer reparo histórico e preservar originais.

Não chamar CD de ativa sem runner/segredos/variáveis/snapshot/proteções e execução
real comprovados. Esta skill é executada pelo Maker; o aceite independente segue
com Hermes/Devs Humanos. Pendências de G01/G02/G03 não desaparecem por PASS local.
