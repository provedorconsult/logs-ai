# G02 — Registro de validação do Maker

Data: 13/11/2026 (America/Sao_Paulo). Os registros abaixo são históricos.
Continuação via Dokploy após autorização de HTTP na Tailnet:
[G02-DOKPLOY.md](G02-DOKPLOY.md). A atualização mais recente determina o estado vigente.
Resposta ao parecer posterior de Hermes e correções A1–A5:
[G02-CHECKER-FIXES.md](G02-CHECKER-FIXES.md).
Resposta à reavaliação de `8fefce0`, achados B1–B6:
[G02-CHECKER-B-FIXES.md](G02-CHECKER-B-FIXES.md).
Correção das lacunas restantes de B6 na revisão de `de83b95`:
[G02-CHECKER-B6-FIXES.md](G02-CHECKER-B6-FIXES.md).
G02 permanece autorizada; este registro não constitui aceite independente.

| Verificação | Resultado observado |
| --- | --- |
| Ruff lint e formatação | Aprovados. |
| Dependências | Lock sincronizado e exportação de requirements conferida. |
| Testes com PostgreSQL real descartável | 17 aprovados, nenhum pulado. |
| Build Docker multi-stage | Concluído com CA de proxy montada como secret, sem desativar TLS. |
| Compose completo | PostgreSQL e aplicação saudáveis; aplicação sem privilégios e filesystem somente leitura. |
| Falha do banco | Banco parado localmente: `/health` retornou HTTP 503. |
| Retomada e volume | Contêineres removidos sem apagar volume e recriados; registro sintético preservado. |
| Migrations após recriação | Uma migration registrada, sem duplicação. |
| Readiness e revisão | HTTP 200 com app e banco saudáveis; `X-App-Revision=g02-local`. |

Os testes cobrem migration idempotente e concorrente, falha transacional sem
schema parcial, checksum alterado, incompatibilidade com release anterior,
restrição de severidade, persistência entre conexões, indisponibilidade do banco,
redação de erros e rejeição de transporte administrativo inadequado.
O TestClient emitiu um aviso de depreciação da combinação Starlette/httpx; os
testes completaram com sucesso. Não foi executado scanner completo de segredos;
foi feita revisão do diff e comparação dirigida com credenciais do ambiente.

## Limites e pendências remotas

Não houve deploy nem acesso à VPS ou ao MikroTik. O ambiente possui token
Dokploy, mas não fornece URL administrativa HTTPS validada, recurso Compose
identificado, `APP_TEST_URL` ou identidade SSH dedicada disponível para estabelecer
o túnel exigido. Não se tentou HTTP administrativo direto pela Tailnet nem
fallback para senha. A configuração foi solicitada ao responsável por canal
seguro; token/chave não devem ser enviados pelo chat.

O workflow de CI/CD foi incluído, mas sua execução no GitHub e o job de deploy
não foram comprovados neste registro. O deploy exige habilitação e configuração
explicadas em [G02.md](G02.md). Não há evidência remota de réplicas `1/1`,
`pg_isready`, readiness, persistência ou rollback da aplicação nesta entrega.
O ensaio local não comprova persistência após reboot da VPS, backup/restauração,
perímetro, carga ou prontidão de produção. Hermes e Devs Humanos ainda precisam
executar o aceite pós-deploy no servidor de testes.

```ini
G02_AUTHORIZED=YES
G02_LOCAL_IMPLEMENTATION=VERIFIED
G02_REMOTE_DEPLOY=BLOCKED_CONFIGURATION
G02_OVERALL=NOT_ESTABLISHED
G01_OVERALL=NOT_ESTABLISHED
CHECKER_INDEPENDENCE=NOT_ESTABLISHED
```

## Continuação — 13/11/2026

A autorização humana foi reiterada para implementar G02 e fazer o primeiro
deploy via Dokploy, mantendo G01 pendente e as restrições sobre MikroTik,
firewall, SSH e configuração base da VPS. Não é necessária nova autorização
para esse deploy; o bloqueio observado é de configuração de acesso.

### Estado do código e validação atual

O checkout estava limpo, na branch local `work`. `git fetch origin main`
confirmou `origin/main=bd2e141b4963d366cb251ea23f692639fd1993b3`, igual ao HEAD.
Foi criada a branch local `main` acompanhando `origin/main`, preservando `work`.
Esta continuação altera apenas documentação; os testes abaixo verificaram o
código de aplicação desse SHA, sem atribuir a ele um deploy remoto.

| Verificação repetida nesta sessão | Resultado observado |
| --- | --- |
| Dependências | `uv sync --locked --python 3.12` e comparação da exportação com `requirements.txt` aprovados. |
| Ruff | Lint e formatação aprovados. |
| PostgreSQL descartável e pytest | 17 testes aprovados, nenhum pulado; um aviso de depreciação Starlette/httpx. |
| Docker local | Engine 29.9.2; Compose v2.40.3. Não são versões verificadas da VPS. |
| Build multi-stage | Concluído com CA montada como secret e TLS validado. |
| Imagem local | `sha256:306b7e1bc9e15adffb980bd4e59075bea7a037a31faea74a60f04522a8ec6e30`; revisão de build igual ao SHA acima. |
| Compose descartável | App e PostgreSQL saudáveis; usuário `10001:10001`, filesystem da aplicação somente leitura. |
| Readiness | HTTP 200, contrato app/banco e `X-App-Revision` conferidos para o SHA acima. |
| Banco indisponível | PostgreSQL parado: `/health` retornou HTTP 503. |
| Recriação e volume local | Contêineres removidos sem apagar volume e recriados; registro sintético preservado e uma única migration registrada. |
| Retomada | `pg_isready` aprovado, readiness e revisão novamente conferidas; logs da aplicação indicaram migration concluída e startup normal. |

O diff documental foi revisado, incluindo verificação de whitespace e comparação
dirigida com valores sensíveis do ambiente, sem ocorrência. Não foi executado
scanner completo de segredos. Os recursos descartáveis criados para esta
revalidação foram removidos ao final; nenhum volume preexistente foi removido.

### Acesso remoto e entrega contínua

A configuração ativa indicou política aplicada, observações atuais e
`automatic_tailscale_access=true`. Um probe limitado pelo CONNECT autorizado
em `proxy:8088`, no executor externo, para o hostname Tailnet configurado na
porta 22 recebeu `HTTP/1.1 200 OK` e banner `SSH-2.0`. Nenhuma variável de porta
da interface pública foi usada. Isso comprova somente transporte TCP e protocolo;
não valida chave do host, login SSH, versão do servidor ou `RunSSH=false`.

Não foram encontrados agente SSH, identidade dedicada, `known_hosts` ou bindings
de chave SSH nos locais acessíveis do ambiente e nos metadados de secrets.
O status não declarou secret de arquivo montado. Os bindings de runtime
disponíveis não incluíram origem HTTPS do Dokploy, recurso Compose ou URL de
homologação. Não se tentou fallback para senha, aceitação automática de chave
de host, HTTP administrativo direto na Tailnet ou alteração da configuração
Tailscale. Nenhum recurso remoto foi criado, alterado ou implantado.

A consulta de Actions e runners com `gh` foi bloqueada com `Forbidden` pelo
caminho de rede atual: `api.github.com` não consta na allowlist efetiva.
O conector GitHub retornou `statuses=[]` na consulta de status combinado do SHA;
esse resultado não comprova execução de Actions nem disponibilidade de runner.
CI e CD continuam não comprovadas. Não foram habilitados auto-deploy ou
`ENABLE_DOKPLOY_CD` sem verificar recurso, runner e transporte.

### Configuração necessária para retomar

Disponibilizar pelo armazenamento seguro do ambiente, sem enviar segredos no
chat, a identidade SSH dedicada e referência confiável da chave do host
(`known_hosts` ou fingerprint obtido por canal independente), associadas aos
seletores `TEST_SERVER_SSH_KEY_PATH`, `TEST_SERVER_HOST` e `TEST_SERVER_USER`.
O relatório não registra o caminho da chave. O cliente deve exigir
`BatchMode=yes`, `IdentitiesOnly=yes`, `StrictHostKeyChecking=yes` e
autenticação somente por chave. Para raw TCP, usar o encaminhamento CONNECT
documentado no runtime, com cliente e forward no mesmo namespace autorizado.

Com o SSH validado, estabelecer o túnel para o listener administrativo local;
alternativamente configurar `DOKPLOY_URL` HTTPS com certificado e hostname
validáveis. Só então consultar o contrato da instância, identificar o projeto
`logs-ai` e seu Compose, provisionar exclusivamente os recursos dessa aplicação
se ausentes e configurar o segredo PostgreSQL no armazenamento do Dokploy.
Não presumir nem reutilizar IDs ou bancos administrativos de outros projetos.

Ainda dependem desse acesso: inventário remoto, contrato da API, recurso Compose,
build/deploy, `APP_REVISION` do SHA efetivamente implantado, `APP_TEST_URL`,
`pg_isready`, migrations, logs, saúde e persistência remotas, última versão
saudável e recuperação. Nenhuma revisão implantada foi determinada.
Para CD, verificar acesso à API GitHub por caminho permitido, runner dedicado
`self-hosted, logs-ai-deploy`, ambiente `homologacao`, variáveis e secret
documentados; habilitar somente depois de observar CI aprovada e deploy correto.
O aceite pós-deploy permanece com Hermes e Devs Humanos.

```ini
G02_AUTHORIZED=YES
G02_LOCAL_IMPLEMENTATION=VERIFIED
TAILNET_SSH_TCP=REACHABLE
SSH_HOST_IDENTITY=NOT_VERIFIED
SSH_KEY_AUTH=BLOCKED_MISSING_CONFIGURATION
G02_REMOTE_DEPLOY=BLOCKED_CONFIGURATION
GITHUB_CI=NOT_ESTABLISHED
CONTINUOUS_DELIVERY=NOT_ESTABLISHED
G02_OVERALL=NOT_ESTABLISHED
G01_OVERALL=NOT_ESTABLISHED
CHECKER_INDEPENDENCE=NOT_ESTABLISHED
```
