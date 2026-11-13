# Plano de Implantação Acelerada

O fluxo é Continuous Delivery sujeito aos gates pré-deploy de
[AGENTS.md](../AGENTS.md), com revisão pós-deploy pelo Checker e Devs Humanos.
Cada fase entrega incrementos rastreáveis por
commit, com verificação conforme [HARNESS.md](HARNESS.md).

## Fase 0 — Bootstrap informado; G01 não aprovada

Conforme o estado informado pelo responsável: rotação de senha realizada,
acesso SSH via Tailnet validado, tokens Dokploy gerados e `.env` local configurado.
Estas condições são premissas operacionais fornecidas, não verificações realizadas
pela criação deste plano. O bootstrap foi informado como concluído/ativo, mas
`G01_OVERALL=NOT_ESTABLISHED`: persistência, recuperação e validações funcionais
ainda dependem de evidências revisadas e aprovação integral.
`G02_AUTHORIZED=YES` por decisão humana explícita de 13/11/2026. Essa decisão
permite iniciar G02 sem aprovação integral prévia da G01; não aprova os testes
pendentes nem associa automaticamente G02 à Fase 2. A decisão da equipe humana
prevalece sobre os gates documentais no escopo autorizado. Mudanças remotas
continuam sujeitas ao escopo e às restrições humanas aplicáveis. Mantenha os segredos fora do Git e renove-os quando
necessário. O acesso automatizado usa chave dedicada, OpenSSH não interativo e
`RunSSH=false` no Tailscale.

Infraestrutura de referência informada: Debian 13, Docker 29.9.3 Swarm,
Compose v5.7.1 e Dokploy v0.31.1.

A consolidação da evidência e as pendências para Debian 13 estão em
[G01-DEBIAN13-REVIEW.md](G01-DEBIAN13-REVIEW.md). A próxima etapa é preparar
a validação final da G01 em paralelo ao avanço autorizado de G02.

## Fase 1 — Fundação & Core Pipeline

Criar estrutura base, `Dockerfile`, `docker-compose.yml` de homologação,
migrations e endpoint `/health`. Configurar build e deploy ativo no Dokploy,
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
