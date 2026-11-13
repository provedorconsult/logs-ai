# G02 — Primeiro deploy via Dokploy

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
| Fonte | GitHub integrado, `provedorconsult/logs-ai`, `main`, `docker-compose.yml` |
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

Publicar a correção, observar seu CI e repetir o deploy. Pedido aceito pela API
não constitui aplicação saudável; resultados remotos serão registrados abaixo.

CD automática ainda depende de runner e variáveis/secret no GitHub. A conexão
GitHub disponível declara `push=true`, `admin=false`; isso não estabelece
permissão para administrar runner e armazenamento de secrets do repositório.
Manter auto-deploy desligado para não contornar CI.
