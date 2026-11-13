# Governança Maker–Checker

## Modelo operacional: Continuous Delivery

Entregas pequenas e frequentes seguem o fluxo: desenvolver, testar localmente,
auditar o diff, versionar, validar os gates, integrar, implantar e verificar após o deploy.
Cada implantação deve ser rastreável ao hash do commit e à imagem implantada.

## Regra principal: decisão da equipe humana

As decisões explícitas da equipe humana responsável são a regra principal
desta governança e prevalecem sobre planos, gates e recomendações operacionais
do repositório. A decisão humana mais recente substitui regras anteriores no
escopo indicado, sem exigir nova aprovação do que já foi autorizado. Registrar
a decisão, data, escopo e exceções na documentação para manter rastreabilidade.
Autorização humana é uma decisão operacional; não transforma evidência ausente
em teste aprovado nem elimina o dever de relatar riscos e resultados com precisão.

## Maker (Codex)

O Maker tem autonomia para desenvolver código, executar testes locais e realizar
commits. Merge, publicação e deploy devem respeitar o escopo autorizado e os
gates abaixo e as decisões humanas vigentes. G02 está autorizada para implementação e primeiro deploy da aplicação via
Dokploy por confirmação humana, mantendo as restrições de perímetro e a G01
pendente. Não alterar MikroTik ou configuração base da VPS nesta entrega.
Antes de publicar, execute os testes aplicáveis e audite os arquivos staged para
impedir inclusão de credenciais ou alterações alheias à entrega.

A infraestrutura de referência informada é Debian 13, Docker 29.9.3 em Swarm,
Docker Compose v5.7.1 e Dokploy v0.31.1. Confirme as versões no ambiente quando
executar uma implantação; este documento não constitui inventário verificado.

O acesso ao servidor deve ser exclusivamente não interativo, por chave SSH
dedicada na Tailnet e tokens de API. Mantenha o Tailscale SSH desativado
(`RunSSH=false`); use o OpenSSH do servidor pela Tailnet. Use `BatchMode=yes`,
`IdentitiesOnly=yes`, autenticação por chave e validação de host conhecido.
Não use senhas em argumentos de processo, URLs, logs ou arquivos versionados.
Não desative a validação da chave do host. Tokens devem ser lidos do ambiente
local protegido e enviados por cliente de API sem expô-los na linha de comando.

O `.env` local e as chaves privadas nunca são versionados. O `.env.example`
contém apenas placeholders. Não imprima variáveis sensíveis, não ative shell
tracing durante operações autenticadas e não inclua segredos em issues.

Em 13/11/2026, o responsável autorizou explicitamente acesso administrativo
HTTP direto pela Tailnet para usar `dokploy_token` no primeiro deploy G02.
Essa decisão substitui a exigência de HTTPS/túnel apenas nesse caminho e escopo.
Fixar a origem exata autorizada, recusar redirects e não enviar o token a outros
hosts. Não altera as restrições sobre SSH, MikroTik ou configuração base da VPS.

## Checker (Hermes) e Devs Humanos

Atuam em revisão pós-deploy diretamente no código versionado e no servidor de
testes configurado no `.env` local. Executam testes de integração e segurança,
leitura de logs e validação funcional conforme [o harness](docs/HARNESS.md).
Registram commit, implantação, resultados e evidências com dados sensíveis
removidos. Em caso de regressão, podem acionar rollback no Dokploy ou abrir
issues bloqueantes. Uma regressão bloqueante deve ser resolvida ou revertida
antes de novas entregas dependentes.

## Planejamento e recuperação

Siga [o plano de implantação](docs/DEPLOYMENT_PLAN.md). Antes de cada deploy,
identifique a última versão saudável e a compatibilidade das migrations.
Rollback da aplicação não desfaz automaticamente mudanças no banco; preserve
backups e um caminho de recuperação testável.

## Correspondência oficial entre gates e fases

| Gate | Fase | Escopo principal |
| --- | --- | --- |
| G01 | Fase 0 — Setup & Bootstrap | Debian 13, Tailscale com `RunSSH=false`, Docker Swarm, Dokploy, rotação de credenciais e auditoria independente (`G01_FINAL_VALIDATION`). |
| G02 | Fase 1 — Fundação & Core Pipeline | Estrutura, dependências/linter, Dockerfile multi-stage, Compose de homologação, PostgreSQL, migrations, `/health` ativo para app e banco e primeiro deploy no Dokploy. |
| G03 | Fase 2 — Motor de Ingestão e IA | Coleta/parsing, análise por LLM e classificação de anomalias. |
| G04 | Fase 3 — Interface, Alertas e API | Dashboard, API de consulta, webhooks, controle de acesso e testes E2E de homologação. |
| G05 | Fase 4 — Hardening & Go-Live | Perímetro/MikroTik/firewall, porta 3000 restrita à Tailnet, desativação de senha SSH, backups e auditoria final. |

O mapeamento define escopo; não constitui aprovação técnica dos gates. Os dados
de infraestrutura fornecidos continuam sujeitos à validação independente.
Para G02, o ciclo de entrega inclui commit, integração/merge quando houver branch
de trabalho, deploy pelo Codex via Dokploy e validação pós-deploy pelo Hermes e
Devs Humanos no servidor de testes. Deploy não equivale a aceite do Checker.

## Gates G01/G02 e decisão de governança

Estado vigente após autorização explícita do responsável humano em 13/11/2026:

```ini
G01_OVERALL=NOT_ESTABLISHED
G02_AUTHORIZED=YES
CHECKER_INDEPENDENCE=NOT_ESTABLISHED
```

Para G01, apresentar diagnóstico e plano concreto com escopo, riscos, transporte
administrativo, evidências esperadas e recuperação. Obter aprovação explícita do
responsável antes de alterações remotas; validar o resultado antes de avançar.
A aprovação integral depende de revisão das evidências de persistência,
recuperação e funcionamento pelo Checker independente e responsável humano.
Bootstrap informado e publicação de documentação não satisfazem esse gate.

Para G02, a decisão humana de 13/11/2026, “G02 autorizada”, autoriza o avanço
e substitui a exigência anterior de aprovação integral da G01 como condição
para iniciar G02. As pendências de G01 continuam registradas e devem ser
acompanhadas; não constituem bloqueio automático ao início autorizado.
G02 corresponde oficialmente à Fase 1 — Fundação & Core Pipeline.
A execução deve respeitar o escopo solicitado, os testes aplicáveis, transporte
administrativo validado e recuperação compatível com migrations. A autorização
de G02 não implica autorização irrestrita para VPS, MikroTik ou ações destrutivas;
instruções humanas específicas sobre esses recursos continuam vigentes.

A revisão pós-deploy complementa a decisão humana e os controles aplicáveis.
Um agente que atuou como Maker não comprova independência como Checker da
própria entrega. Mudanças futuras de modelo devem registrar a decisão humana
e seu escopo, mantendo a distinção entre autorização e aprovação técnica.
