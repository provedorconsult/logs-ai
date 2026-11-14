---
name: logs-ai-web
description: Implantar e validar o console web logs-ai, banco de metadados isolado, clientes MikroTik e HTTPS no projeto Dokploy correto.
---

# Reconstruir o destino

Leia `AGENTS.md`, `docs/WEB.md`, `docs/WEB-DECISIONS.md` e a skill
`logs-ai-stack`. Confirme projeto, ambiente, banco de logs e sua rede privada.
Não copiar IPs/IDs/credenciais da instalação histórica para outro servidor.
Confira OpenAPI e estado remoto antes de criar ou atualizar recursos.

## Preparar e implantar

1. Testar com PostgreSQL descartável, Ruff e navegador desktop/mobile. Publicar
   e conferir a CI do SHA completo usado no build. Registrar snapshot/journal
   protegido antes de alterar artefato e ambiente completos de recurso existente.
2. Gerar quatro senhas hex aleatórias e segredo de sessão no cofre. Executar
   `deploy/web-bootstrap.compose.yml` como job temporário na rede do PostgreSQL
   dedicado; confirmar saída zero. Não usar o banco administrativo do Dokploy.
   Reutilizar credenciais existentes em atualização, sem redefini-las.
3. Criar recurso web separado usando `deploy/web.compose.yml`, SHA completo,
   rede do banco e `dokploy-network`; sem publicação direta da porta 8080.
   Configurar domínio solicitado, serviço `web`, porta 8080 e HTTPS/Let's Encrypt.
4. Banco `logs_ai_web` e migrations `web_migrations` são separados do schema
   compartilhado do core. Bootstrap recebe usuário e hash PBKDF2 protegido,
   codificado como `b64:` para dotenv. Nunca versionar senha ou hash real.
5. Depois do startup inicial, repetir o job com `--grant-registry`. O coletor
   recebe somente SELECT na view de origens e outro papel INSERT-only nos logs,
   `LOGS_SCHEMA_MANAGED_EXTERNALLY=true`. Substituir a credencial superusuária
   legada; apenas adicionar a view não estabelece isolamento.
6. Remover bootstrap do ambiente web e recriar no mesmo SHA, conferindo que a
   conta continua com troca obrigatória. Não trocar a senha real para simular
   um teste. Não recriar cliente apagado nem redefinir contas em restart.

## Conferir e entregar

Correlacionar deployment, Git SHA, digest/label, health/revisão, migrations e
privilégios efetivos. Testar login, troca obrigatória, filtros/paginação, CSV/PDF,
perfis, cadastro e geração RSC. Testes destrutivos usam exclusivamente banco
descartável. No destino real, preservar dados e remover apenas sessões próprias.
Não configurar automaticamente o roteador para testar a interface. Aplicação SSH
é ação explícita do administrador com fingerprint confirmado e senha transitória.

HTTPS configurado não prova certificado válido. Verificar no hostname real com
TLS validado e seguir grants de rede do executor; nunca contornar um bloqueio
do proxy. Registrar verificações pendentes com precisão. Remover job temporário
e seu ambiente administrativo, preservando recuperação no armazenamento privado.
Atualizar `docs/audits/WEB-VALIDATION.md`; aceite independente segue com o Checker.

Antes de declarar domínio operacional, conferir também
`settings.getTraefikOverview`, listener/port bindings efetivos em 80/443 e
certificado instalado para o SAN correto. `versionStatus=not-found` indica
pré-requisito ausente, mesmo com web saudável e labels corretas. No Dokploy
v0.31.2, `reloadTraefik=true` só aceita um reinício assíncrono e não cria proxy
ausente. Consultar implementação/contrato e preservar recursos antes de restaurar
o proxy nativo; não criar outro proxy concorrente nem deixar um job com socket
Docker montado. Usar contato ACME informado, sem inventar endereço de e-mail.
