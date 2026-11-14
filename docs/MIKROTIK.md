# Integração MikroTik — PPPoE e auditoria administrativa

## Escopo confirmado

- RouterOS 7.24.5 e usuários locais `/ppp secret`.
- MikroTik privado `192.168.15.1`; VPS privada `192.168.15.25`.
- Recepção nativa TCP/CEF, porta 5514, somente pela rede privada e somente da
  origem configurada do roteador. A autenticação aqui é a fronteira da rede/IP,
  não uma identidade criptográfica do remetente; não publicar a porta na WAN.
- Equipe de redes aplica os scripts. O Codex acompanha com SSH somente leitura,
  usuário/senha do ambiente e fingerprint verificado antes de autenticar.
- Ingestão é o incremento autorizado da G03; não inclui IA nem aceite integral
  de G01/G02/G03.

## Serviço Dokploy

`deploy/mikrotik.compose.yml` configura um componente `collector` separado do
core G02. Ele compartilha somente a rede e o PostgreSQL já dedicados ao projeto
`logs-ai`. Não reutiliza banco administrativo do Dokploy ou de outro projeto.
O core, seu volume e a publicação anterior são preservados.

O Compose é fornecido ao Dokploy no modo raw, com contexto de build Git
`https://github.com/provedorconsult/logs-ai.git#<SHA completo>`. O BuildKit busca
diretamente o objeto do commit; o argumento/label `APP_REVISION` usa o mesmo SHA.
Essa implantação não depende de tag móvel nem habilita CD do fluxo de tags.
É necessário verificar logs de build, deployment específico, imagem e header;
pedido aceito pela API não comprova prontidão.

Variáveis protegidas do componente:

| Variável | Finalidade |
| --- | --- |
| `APP_REVISION` | SHA completo do código construído. |
| `DATABASE_URL` | Conexão protegida com o PostgreSQL dedicado existente. Não imprimir. |
| `LOGS_AI_DATABASE_NETWORK` | Rede Docker compartilhada exclusivamente com o core/banco logs-ai. |
| `MIKROTIK_ALLOWED_SOURCE` | Origem permitida: IP privado do MikroTik. |
| `MIKROTIK_BIND_HOST` | IP privado da VPS; publicação TCP/5514. |
| `COLLECTOR_HEALTH_BIND` | IP administrativo autorizado ou loopback; não usar wildcard público. |
| `COLLECTOR_HEALTH_PORT` | Porta HTTP de saúde, padrão 18002. |

O coletor usa UID 10001, filesystem somente leitura, sem capabilities e com
memória/CPU limitadas. Não há novas migrations: a mesma migration `001_initial.sql`
é conferida transacionalmente e os eventos usam `log_events`. O core anterior
permanece compatível com o schema. Migrações futuras devem coordenar os dois
componentes que compartilham esse banco.

## Aplicação pela equipe de redes

1. Conferir o receptor saudável e a rota privada TCP/5514.
2. Revisar [install-logging.rsc](../scripts/mikrotik/install-logging.rsc). Ele
   cria uma ação `logs-ai-private` e duas regras com prefixos próprios para
   `ppp,info` e `system,info,!ppp`. Não modifica perfis PPP, scripts on-up/on-down,
   clientes, senhas, firewall ou as regras de logging anteriores.
3. Importar o arquivo pelo método habitual da equipe no RouterOS 7.24.5.
   Colisões com configuração diferente/ambígua ou regra desativada abortam para
   inspeção, em vez de sobrescrever recursos alheios. Uma falha de importação
   pode exigir remover somente os recursos deste script antes de repetir.
4. Validar com sessão PPPoE controlada (login e término) e alteração administrativa
   autorizada em conta de teste. Um login SSH de leitura também gera auditoria
   administrativa nativa, sem exigir alteração de configuração.
5. Conferir `/metrics`: `persisted` e `persisted_by_kind` sobem somente após
   commit PostgreSQL. Conferir no banco por consulta de leitura autorizada;
   zero eventos não comprova integração funcional.

Reversão: [remove-logging.rsc](../scripts/mikrotik/remove-logging.rsc) remove
somente as regras com os prefixos desta integração e ação de destino conferida.
A ação é preservada se outras regras ainda a utilizarem. O script não foi
executado automaticamente pelo Codex.

## Dados e limites

Tipos normalizados: autenticação PPPoE, início/fim de sessão, criação/edição/
remoção/ativação/desativação de usuário PPP quando indicado no log, alterações
de contas administrativas, login/logout administrativo e mudanças genéricas
de configuração. Capturam usuário/ator e IP/MAC quando o formato os informa.
Algumas mudanças do RouterOS aparecem apenas como `changed`; não se inventa
qual campo foi alterado. Mensagens desconhecidas são ignoradas e contadas.

Comandos e mensagens brutas não são persistidos. Parênteses com comandos,
senhas/tokens de configuração não entram nos atributos. `received_at` é o
horário de recepção do banco; `router_time`, quando presente, preserva o horário
informado no log sem inventar ano/fuso ausente. A leitura do roteador confirmou
`America/Bahia`; não se assume fuso a partir do nome do diretório ou da VPS.

TCP oferece controle de fluxo, mas syslog nativo não confirma commit por evento.
A fila é limitada e em memória; não há promessa de exatamente uma entrega nem
replay após reboot. Falha do banco retém o evento para retry enquanto o processo
vive, aplica backpressure e deixa saúde indisponível. Shutdown/falha prolongada
podem perder itens ainda não gravados. Backup, retenção e garantia durável de
origem exigem um escopo adicional; sucesso deve ser observado no banco.

## Acompanhamento somente leitura

`scripts/mikrotik/readonly_monitor.py` usa Paramiko 4.0.0 em ambiente de ferramentas
isolado. Credenciais vêm de `mikrotik_username`/`mikrotik_password`; destino e
fingerprint de `MIKROTIK_PRIVATE_HOST`, `MIKROTIK_PRIVATE_SSH_PORT` e
`MIKROTIK_HOST_FINGERPRINT`. Não enviar segredos como argumentos.
O programa valida o fingerprint antes de autenticar e executa somente consultas
fixas de versão, relógio, logging e contagens PPP. Não lê senhas de clientes.
Se a LAN não estiver acessível diretamente do executor Cloud, a inspeção pode
rodar em contêiner temporário não privilegiado na VPS, removido ao final.

## Validação desta entrega

Registro de implementação, build, deploy e verificações observadas será mantido
em [MIKROTIK-VALIDATION.md](MIKROTIK-VALIDATION.md). Aplicação dos scripts e
validação de eventos reais pertencem ao acompanhamento com a equipe de redes;
testes sintéticos não substituem esse passo.
