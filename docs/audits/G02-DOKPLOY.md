# G02 — Primeiro deploy via Dokploy

Registro histórico. Correções posteriores ao parecer de Hermes:
[G02-CHECKER-FIXES.md](G02-CHECKER-FIXES.md).

Data: 13/11/2026 (America/Sao_Paulo). Registro do Maker; aceite independente
permanece com Hermes e Devs Humanos. G01 continua `NOT_ESTABLISHED`.

## Autorização e transporte

Após o diagnóstico anterior, o responsável autorizou explicitamente HTTP
administrativo direto na Tailnet e confirmou a integração GitHub. A API aceitou
`dokploy_token` no header `x-api-key`, sem redirects. OpenAPI da própria
instância e consulta de versão confirmaram Dokploy v0.31.1 e os contratos
usados pelo cliente de deploy. A ausência de chave SSH ainda limita os checks
por OpenSSH, mas deixou de bloquear a API autorizada.

Não foram alterados SSH, Tailscale, firewall, MikroTik ou configuração base da
VPS. Não se verificou `RunSSH=false` remotamente nem se atribui aprovação à G01.

## Recursos dedicados

| Recurso | Identificação |
| --- | --- |
| Projeto | `logs-ai`, `GUdmAuLYi0KG3PQ9RTC3l` |
| Ambiente | `homologacao`, `pD5ynNkqEh6XX4fcRXBn2` |
| Compose | `logs-ai-core`, `N0U066dwxG4Y-nFp1Zkoe` |
| appName | `logs-ai-g02-homologacao-slfhbn` |
| Fonte | GitHub integrado, `provedorconsult/logs-ai`; commits de `main` promovidos por tag SHA; `docker-compose.yml` |
| Modo | `docker-compose`; `autoDeploy=false`; volumes não isolados por deployment |
| URL de teste | `http://${tailscale_full_domain}:18000`, expandir no ambiente seguro |

O único projeto preexistente não foi reutilizado ou alterado. O segredo
PostgreSQL aleatório foi salvo no ambiente do Compose no Dokploy, sem ser
versionado. A aplicação foi configurada para bind no IP Tailnet, porta 18000;
PostgreSQL não tem porta publicada. Os endereços internos não são publicados
neste repositório.

## Código e CI

O conector GitHub permitiu consultar Actions apesar do bloqueio da CLI. O run
`43442053833`, SHA `aa400f076c7771310b0597188d54c56d14998abc`, concluiu `verify`
com sucesso; `deploy` foi `skipped`. O run anterior `43399900032`, SHA
`bd2e141b4963d366cb251ea23f692639fd1993b3`, também concluiu com sucesso.
Essas observações substituem a pendência de confirmação de CI desses commits;
não comprovam CD ativa.

O cliente aceita HTTP somente para origem Tailnet exata explicitamente
habilitada, valida projeto e origem Git/GitHub e exige SHA completo. Preserva
segredos e atualiza revisão/imagem. Publica uma tag exclusiva por SHA, sem força,
e configura essa referência na fonte do Dokploy para impedir troca de código
se `main` avançar. Os contratos adicionais foram conferidos no OpenAPI desta
instância. Ruff e os testes com PostgreSQL real passaram (resultado final abaixo).
Uma execução inicial ocorreu antes da prontidão do banco descartável
e falhou na conexão; após `pg_isready`, a suíte passou integralmente.

## Estado desta publicação

O SHA `08de04d6f4f20d18dfe7acdc1eccadbb7519c7b9` foi publicado; o run
`43453074099` aprovou `verify` e pulou `deploy`. O pedido manual
`4OMs8W7EKtwdZvQ4RuzKF` clonou o repositório, mas falhou antes do build:
`Invalid characters in compose command: shell control characters are not allowed`.
Nenhum contêiner da aplicação foi criado nesse pedido. A estratégia inicial de
comando com verificação de HEAD foi substituída pela tag Git por SHA e comando
Compose padrão, respeitando a validação da instância.

O SHA `257f575311758281e8ae7327dc48372534262cc1` passou no run `43453648186`.
O pedido `IjgYfjn-GwJdGXxey8vEx` confirmou busca da tag, mas falhou antes do
build porque o preview `docker compose ...` não pode ser copiado integralmente
para o campo de override: a instância acrescenta `docker`, resultando em
`docker docker compose ...`. O cliente foi corrigido para deixar `command`
vazio, selecionando o padrão nativo. Nenhuma tentativa anterior criou serviços
da aplicação. Pedido aceito não constitui aplicação saudável.

## Resultado remoto final

| Verificação | Resultado observado |
| --- | --- |
| Código implantado | `bbb9a698ca4c274e43d18f133a08039c28f0ca4a` |
| Fonte imutável por SHA | `logs-ai-deploy-bbb9a698ca4c274e43d18f133a08039c28f0ca4a`; `git ls-remote` confirmou o alvo |
| CI do código implantado | Run `43454062691`: `verify=success`, `deploy=skipped` |
| Deploy Dokploy | `dGYOooJx9BweTiYUkarul`, `done` |
| Horário do deploy | 13/11/2026, 12:37:01 a 12:37:17 (-03); API registrou 15:37:01Z a 15:37:17Z |
| Imagem da aplicação | `logs-ai:bbb9a698ca4c274e43d18f133a08039c28f0ca4a` |
| ID da imagem no servidor | `sha256:99f1209220b98acd7cf80ea1b397acc246f47e0ec50517727dd82f2a45781f82` |
| HTTP remoto | `/health` HTTP 200, `{"status":"ok","database":"ok"}` |
| Revisão remota | `X-App-Revision` e label OCI iguais ao SHA implantado |
| App | Um contêiner `running`, `healthy`, zero reinícios; usuário `10001:10001`, filesystem somente leitura |
| PostgreSQL | Um contêiner `running`, `healthy`, zero reinícios; imagem `postgres:17-bookworm` |
| `pg_isready` remoto | Últimas cinco execuções do healthcheck com exit code zero e `accepting connections` |
| Autenticação e schema | `/health` executou consulta autenticada exigindo migration `001_initial.sql` e tabela `log_events` |
| Logs remotos | App: migrations concluídas e startup normal; PostgreSQL pronto para conexões; nenhum `ERROR`, `FATAL` ou traceback na amostra de 50 linhas por contêiner |
| Volume | Mesmo mount PostgreSQL entre os dois deploys saudáveis; banco não foi recriado na promoção final |
| Publicação de portas | Bind da aplicação somente no IP Tailnet configurado, porta 18000; PostgreSQL sem porta publicada |
| Cliente final | `scripts/deploy.py` executou com sucesso no SHA final; readiness remoto confirmado por `scripts/check_health.py` |
| Checks locais finais | Ruff, formatação, exportação do lock e 26 testes com PostgreSQL real aprovados; aviso Starlette/httpx permanece |

A origem administrativa e `APP_TEST_URL` expandidas estão no `.env` local
ignorado, com modo 0600. O token continua vindo do ambiente e o segredo do
banco está no Dokploy. Evidências completas de API foram mantidas em arquivos
locais protegidos de trabalho; apenas projeções sem segredos são publicadas.
O diff foi auditado com comparação dirigida de valores sensíveis e verificação
de whitespace; não se executou scanner completo de segredos.

O primeiro deploy saudável foi `A81f0ujvJxBZYenswww2f`, SHA
`257f575311758281e8ae7327dc48372534262cc1`, concluído às 12:36:08 (-03).
Sua imagem, `sha256:45879cec7ff09cce985a671aca8edad562e6721ec6a15096fe4de746c8a7d93a`,
é a referência anterior saudável. As migrations não mudaram entre essas
versões. Para recuperação, reconfigurar somente este Compose para a tag
`logs-ai-deploy-257f575311758281e8ae7327dc48372534262cc1`, revisão/imagem
correspondentes, preservando segredo, volume e comando nativo; solicitar deploy
e verificar o SHA retornado. Esse rollback não foi executado nem comprova
restauração de backup.

## Entrega contínua e aceite pendente

O caminho compatível está implementado: CI GitHub, job de deploy após `verify`,
runner Tailnet dedicado, token em GitHub Secrets, variáveis no ambiente
`homologacao`, tag por SHA e verificação remota de revisão. `autoDeploy=false`
foi conferido na instância para não contornar CI. A promoção manual desta sessão
foi realizada depois de observar o sucesso de CI de cada revisão promovida.

CD automática **não está ativa**: o job remoto foi pulado. Ainda é necessário
provisionar/verificar runner `self-hosted, logs-ai-deploy` com Git, Python e
acesso Tailnet; configurar `DOKPLOY_URL`, `DOKPLOY_PROJECT_ID`,
`DOKPLOY_COMPOSE_ID`, `DOKPLOY_API_CONTRACT_VERIFIED=true`, `APP_TEST_URL` e,
para a exceção vigente, `DOKPLOY_ALLOW_TAILNET_HTTP=true` e
`DOKPLOY_TAILNET_HTTP_ORIGIN`; salvar `DOKPLOY_API_TOKEN` em GitHub Secrets;
depois habilitar `ENABLE_DOKPLOY_CD=true` e observar uma execução completa.
O checkout do job usa permissão `contents: write` somente no deploy para criar
a tag, sem sobrescrever referências existentes.

A conexão GitHub disponível declara `push=true`, `admin=false`; as ferramentas
conectadas não oferecem administração de runners/variáveis/secrets. A integração
GitHub do Dokploy permite buscar o código, mas não comprova essa configuração
do GitHub Actions. Não foram extraídos tokens da integração nem instalado
runner por alterações na configuração base da VPS.

Persistência de dado sintético após recriar o banco remoto, indisponibilidade
remota do banco, backup/restauração, rollback, reboot e perímetro não foram
ensaiados nesta sessão. O mount preservado não substitui esses testes.
Debian, Engine, Compose e `RunSSH=false` da VPS não foram verificados por SSH;
somente a versão Dokploy foi confirmada remotamente. Resultados locais não
preenchem essas lacunas. Hermes e Devs Humanos mantêm o aceite pós-deploy
independente; o Maker não declara aprovação integral da G02 ou da G01.

```ini
G02_AUTHORIZED=YES
G02_LOCAL_IMPLEMENTATION=VERIFIED
G02_REMOTE_DEPLOY=VERIFIED_BY_MAKER
G02_REMOTE_READINESS=VERIFIED_BY_MAKER
GITHUB_CI=VERIFIED
CONTINUOUS_DELIVERY=NOT_ENABLED_CONFIGURATION_PENDING
G02_OVERALL=NOT_ESTABLISHED
G01_OVERALL=NOT_ESTABLISHED
CHECKER_INDEPENDENCE=NOT_ESTABLISHED
```
