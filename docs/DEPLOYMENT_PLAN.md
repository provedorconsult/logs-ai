# Plano de Implantação Acelerada

O fluxo é Continuous Delivery, com autonomia do Maker e revisão pós-deploy pelo
Checker (Hermes) e Devs Humanos. Cada fase entrega incrementos rastreáveis por
commit, com verificação conforme [HARNESS.md](HARNESS.md).

## Fase 0 — Bootstrap (Concluída/Ativa)

Conforme o estado informado pelo responsável: rotação de senha realizada,
acesso SSH via Tailnet validado, tokens Dokploy gerados e `.env` local configurado.
Estas condições são premissas operacionais fornecidas, não verificações realizadas
pela criação deste plano. Mantenha os segredos fora do Git e renove-os quando
necessário. O acesso automatizado usa chave dedicada, OpenSSH não interativo e
`RunSSH=false` no Tailscale.

Infraestrutura de referência informada: Debian 13, Docker 29.9.3 Swarm,
Compose v5.7.1 e Dokploy v0.31.1.

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
