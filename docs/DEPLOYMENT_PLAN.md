# Plano de Implantação Acelerada

O fluxo é Continuous Delivery sujeito aos gates pré-deploy de
[AGENTS.md](../AGENTS.md), com revisão pós-deploy pelo Checker e Devs Humanos.
Cada fase entrega incrementos rastreáveis por
commit, com verificação conforme [HARNESS.md](HARNESS.md).

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

## Fase 0 — Bootstrap informado; G01 não aprovada

Conforme o estado informado pelo responsável: rotação de senha realizada,
acesso SSH via Tailnet validado, tokens Dokploy gerados e `.env` local configurado.
Estas condições são premissas operacionais fornecidas, não verificações realizadas
pela criação deste plano. O bootstrap foi informado como concluído/ativo, mas
`G01_OVERALL=NOT_ESTABLISHED`: persistência, recuperação e validações funcionais
ainda dependem de evidências revisadas e aprovação integral.
`G02_AUTHORIZED=YES` por decisão humana explícita de 13/11/2026. Essa decisão
permite iniciar G02 sem aprovação integral prévia da G01; não aprova os testes
pendentes. G02 corresponde à Fase 1 conforme a matriz oficial. A decisão humana
prevalece sobre os gates documentais no escopo autorizado. Mudanças remotas
continuam sujeitas ao escopo e às restrições humanas aplicáveis. Mantenha os segredos fora do Git e renove-os quando
necessário. O acesso automatizado usa chave dedicada, OpenSSH não interativo e
`RunSSH=false` no Tailscale.

Atualização humana de 13/11/2026: acesso HTTP administrativo direto na Tailnet
autorizado para o Dokploy e primeiro deploy G02, usando o token do ambiente.
A exceção não autoriza alterações na configuração SSH, Tailscale ou perímetro.
O cliente fixa a origem exata e recusa redirects; ver [G02.md](G02.md).

Infraestrutura de referência informada: Debian 13, Docker 29.9.3 Swarm,
Compose v5.7.1 e Dokploy v0.31.1.

A consolidação da evidência e as pendências para Debian 13 estão em
[G01-DEBIAN13-REVIEW.md](audits/G01-DEBIAN13-REVIEW.md). A próxima etapa é preparar
a validação final da G01 em paralelo ao avanço autorizado de G02.

## Fase 1 — Fundação & Core Pipeline

Implementação e configuração operacional: [G02.md](G02.md). A equipe humana
confirmou a execução imediata da G02; aceite remoto continua dependente da
validação pós-deploy, sem aprovação implícita de G01.

Criar estrutura base, gerenciamento de dependências e linter, `Dockerfile`
multi-stage, `docker-compose.yml` de homologação,
PostgreSQL, migrations automatizadas e endpoint `/health` que verifica ativamente
a aplicação e a conectividade com o banco. Configurar build e deploy ativo no Dokploy,
com variáveis protegidas, volumes persistentes e imagem vinculada ao commit.
Critério de saída: deploy reproduzível, migrations aplicadas, banco saudável,
serviços nas réplicas desejadas e `/health` respondendo com sucesso.

## Fase 2 — Motor de Ingestão e IA

Implementar parsing de logs, integração com provedores de LLM e detecção de
anomalias com deploy contínuo. Proteger tokens e dados sensíveis dos logs.
Critério de saída: testes de ingestão, formatos inválidos, falhas do provedor e
detecção com dados controlados aprovados na homologação.

## Fase 3 — Interface, Alertas e API

Entregar dashboard, API e webhooks de alerta. Executar testes E2E no servidor
de testes definido por `APP_TEST_URL`.
Critério de saída: jornadas de consulta e alerta validadas, incluindo autorização,
falhas de webhook e regressões de integração.

## Fase 4 — Hardening & Go-Live

Restringir a porta `3000` do Dokploy à rede administrativa autorizada e aplicar
regras de perímetro no MikroTik/firewall. Desativar `PasswordAuthentication` no
SSH após validar a chave dedicada e o caminho de recuperação administrativa.
Validar persistência de dados, retorno dos serviços e healthchecks após reinício.
Critério de saída: revisão de segurança, restauração de backup, rollback e
persistência aprovados pelo Checker e Devs Humanos.

## Regra de promoção e rollback

Registrar hash, imagem, implantação, migrations, resultado dos testes e última
versão saudável. Regressões bloqueantes exigem rollback ou correção imediata,
com nova execução do harness. O rollback deve respeitar a compatibilidade do
schema e o procedimento de restauração do banco.

## Estado entregue e escopo autorizado — 14/11/2026

A matriz de fases acima permanece válida. A autorização humana posterior para
integração MikroTik permitiu antecipar **um incremento da G03**, sem renomeá-lo
como G02 nem conceder aceite integral de uma fase.

| Fase | Implementação/evidência atual | Pendência |
| --- | --- | --- |
| G01 | Bootstrap relatado e revisão documental histórica. | [Parecer independente final](audits/G01-CHECKER-VALIDATION.md), persistência/recuperação e controles completos não estabelecidos. |
| G02 | Core FastAPI/PostgreSQL/migrations, build, health e primeiro deploy; [evidências](audits/G02-VALIDATION.md). | Aceite independente integral e CD efetiva, incluindo gates técnicos do caminho legado. |
| G03 — incremento de ingestão | Coletor TCP/CEF, normalização PPPoE/auditoria e eventos reais de `/user` e `/ppp secret`; [histórico](audits/MIKROTIK-VALIDATION.md). | IA/LLM, detecção de anomalias e aceite integral da fase não implementados/estabelecidos. |
| Padronização operacional | Perfis, pacote novo completo, scripts por roteador, skills e verificador; [testes](audits/NEW-SERVER-VALIDATION.md). | Bootstrap em nova VPS e comissionamento de cada novo destino precisam de evidências próprias. |

A reorganização dos relatórios está no [índice de auditorias](audits/README.md).
O [índice ativo](README.md) distingue procedimentos vigentes de resultados
históricos. O sucesso funcional da ingestão não fecha G01/G02/G03 ou CD.


## Incremento de interface G04 autorizado — 14/11/2026

Dashboard, relatórios filtrados/paginados com CSV/PDF, gestão de clientes MikroTik
e usuários foram autorizados em novo serviço do mesmo projeto Dokploy, com
domínio/HTTPS e primeiro acesso protegido por troca obrigatória de senha.
O escopo e as escolhas estão em [WEB.md](WEB.md) e [WEB-DECISIONS.md](WEB-DECISIONS.md);
resultados observados em [WEB-VALIDATION.md](audits/WEB-VALIDATION.md).
Isso não constitui implementação de IA nem aceite integral de G04/G05.
