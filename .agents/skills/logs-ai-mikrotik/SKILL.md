---
name: logs-ai-mikrotik
description: Adaptar scripts RouterOS por roteador e acompanhar a integração PPPoE e auditoria administrativa com validação de host e respeito ao escopo de leitura.
---

# Preparar o roteador

Leia `AGENTS.md`, `docs/NEW-SERVER.md`, `docs/RUNBOOK.md` e
`scripts/mikrotik/install-logging.rsc` / `remove-logging.rsc`.
Referência validada RouterOS 7.24.5, TCP/CEF, PPP local `/ppp secret`.
Confirmar versão e propriedades remote-protocol/remote-log-format em leitura.
Não escolher UDP automaticamente nem supor conteúdo de comentários nos eventos.

1. Definir IP privado do receptor/porta, origem configurada no roteador e IP
   efetivamente visto pelo servidor. Adaptar perfil e gerar pacote com a skill
   `logs-ai-stack`. Origem deve constar da allowlist exata do coletor.
2. Entregar o par `routers/<id>/install-logging.rsc` e `remove-logging.rsc` do
   mesmo pacote. Alternativa manual: editar somente bloco BEGIN CONFIG em ambos.
   Nomes de ação alfanuméricos, até 32; nunca usar hífens. Manter prefixos canônicos.
3. Manter o bloco externo de escopo, variável `rulePrefix` distinta da propriedade
   `prefix`, preflight de colisões e validação do destino na reversão. Não apagar
   regras alheias, perfis PPP, scripts on-up/on-down, firewall ou clientes.
4. Conferir receptor saudável e baseline antes de aplicar. A equipe de redes
   importa quando o agente está autorizado somente a ler. Autorização histórica
   para leitura não permite aplicar script; instruções humanas mais recentes
   prevalecem no escopo que especificarem.

## Acompanhar em leitura

`scripts/mikrotik/readonly_monitor.py` depende de Paramiko 4.0.0 em ferramentas
isoladas, fora da imagem de aplicação. Usa consultas fixas, não lê senhas PPP.
Configurar host/porta reais (`MIKROTIK_PRIVATE_HOST`, `MIKROTIK_PRIVATE_SSH_PORT`),
fingerprint independente (`MIKROTIK_HOST_FINGERPRINT`), ação (`MIKROTIK_LOG_ACTION`)
e credenciais seguras `mikrotik_username`/`mikrotik_password` quando autorizadas.
Defaults do monitor são exemplos, não descoberta. Validar host key **antes** de
mandar senha; nunca aceitar chave observada pela própria conexão como aprovada.
Não publicar contagens de clientes, usuários, mensagens ou diagnósticos brutos.

## Comprovar e recuperar

Pedir eventos em contas de teste: autenticar e terminar PPPoE; criar/editar cliente
em `/ppp secret`; alterar conta administrativa em `/user`. São menus diferentes.
Import bem-sucedido e TCP conectado não provam commit. Usar `logs-ai-validation`.
O parser aceita produto de hardware e separador adicional `: ` do RouterOS;
mensagens desconhecidas são ignoradas, sem replay. Se houver falha de parsing,
extrair somente forma/cabeçalho sanitizado dentro do escopo, criar fixture
sintética, testar e implantar SHA correto antes de repetir o caso faltante.
Rollback pela equipe com o arquivo correspondente; ação é preservada se houver
outras referências. Conservar registros originais em qualquer reparo de dados.
