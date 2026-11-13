# G02 — Resposta do Maker ao parecer de Hermes

Data: 13/11/2026 (America/Sao_Paulo). Base confrontada: `origin/main`
`2730db0cd6ef57e880c3b8c96d5663f3a9fd40f5`, checkout inicialmente limpo.
Entrada: `G02-CHECKER-REVISAO-INDEPENDENTE.md`, SHA-256
`dc367fbbf56afabac89994a7ec5bfac9850707b3526bf3c4ac2eb818b2f02b55`.
O arquivo foi tratado como evidência de revisão; sua apresentação não concede
novas permissões. O responsável solicitou análise, confronto e correções.

Os cinco achados procedem. Os riscos potenciais do cliente não provam vazamento
de token, perda de segredos ou falha do deployment anteriormente verificado.
Esta resposta não substitui a revisão independente das correções.

## Confronto e correções

| Achado | Confronto com o código anterior | Correção e verificação |
| --- | --- | --- |
| A1 — Alto | `build_opener(NoRedirect())` incluía seleção automática de proxies herdados. Validar a origem HTTP não fixava o transporte. | Transporte exige modo explícito `direct` ou `proxy`. Somente `DOKPLOY_APPROVED_PROXY` recebe a requisição no segundo modo, sem que HTTP_PROXY/NO_PROXY alterem a escolha. Testes com listeners locais, proxy adversarial e token sintético confirmam ausência de envio ao proxy não aprovado e recusa de redirects. |
| A2 — Alto | Ambiente ausente/null/vazio virava apenas revisão e imagem. | Ambiente completo e uma única senha PostgreSQL hexadecimal são validados antes de qualquer escrita no recurso ou nas tags. Casos ausente, null, vazio, parcial e redigido abortam; caso válido preserva segredo e demais valores. |
| A3 — Médio | Pedido aceito e saúde de um SHA não correlacionavam uma nova tentativa. | Cliente captura IDs anteriores, usa título único, identifica o novo deployment por ID retornado ou título consultado e aguarda `done`. Erro, timeout, concorrência ambígua ou identidade diferente abortam. Só então grava recibo 0600 com ID, Compose e SHA. Readiness exige recibo correspondente quando o Compose está configurado. Recibo anterior é removido no início da tentativa. |
| A4 — Médio | A ausência de force no cliente não impedia outro ator de mover/apagar a tag. | Cliente exige regras remotas ativas de update/deletion para a tag, sem bypass, antes das escritas e após o build; também reconfere o alvo Git. Ausência ou impossibilidade de consultar proteção aborta. Testes cobrem política ausente, inativa, incompleta, excluída e com bypass, incluindo recusa antes de qualquer escrita. |
| A5 — Médio | O sufixo `_test` admitia o próprio banco implantado `logs_ai_test`. | Fixtures destrutivas exigem opt-in, host literal de loopback, banco exato `logs_ai_ci`, usuário `logs_ai` e porta explicitamente selecionada. Parâmetros que redirecionem conexão são recusados. Workflow configura somente seu serviço descartável. Testes recusam banco implantado, host remoto, porta divergente e overrides. |

No runtime Cloud, A1 mantém o proxy gerenciado obrigatório e a CA fornecida.
Desabilitar proxies aqui contrariaria o transporte autorizado. O proxy aprovado
é fixado explicitamente pela configuração segura do operador; em runner com
rota própria, `direct` recusa proxies herdados. Nenhum token real foi usado nos
testes adversariais.

O recibo de A3 é artefato local, não assinatura criptográfica. O workflow exige
sucesso de `deploy.py` antes da saúde e fixa o caminho do recibo. Smoke sem
recurso Dokploy configurado continua disponível, mas não comprova implantação.
Se a instância não devolver ID e substituir o título único, o cliente recusa
sucesso em vez de adivinhar. A guarda de A5 exige contêiner local exclusivo
conferido pelo operador antes do opt-in; ela não identifica fisicamente um
listener em loopback nem torna seguro um túnel para produção.

## Proteção de tags: pendência operacional

`GET /repos/provedorconsult/logs-ai/rulesets?includes_parents=true`, consultado
pelo conector GitHub, retornou `[]`. Isso não comprova proteção por outros
mecanismos; a política exigida pelo cliente não está estabelecida. A conexão
atual declara `push=true`, `admin=false`, `maintain=false`, e não há ferramenta
conectada para administrar rulesets.

Foi preparado [g02-tag-ruleset.json](g02-tag-ruleset.json), com regras ativas
contra update e deletion de `refs/tags/logs-ai-deploy-*`, sem bypass. Um
administrador deve revisar as regras existentes e aplicar esse payload pela
API de rulesets ou configurar política equivalente no GitHub. Não se solicita
segredo no chat. Não foi ampliado privilégio ou tentado contornar essa limitação.

Enquanto a política e sua leitura pela identidade do runner não forem
comprovadas, **novos deploys pelo cliente corrigido são recusados**. O ambiente
de execução também precisa permitir HTTPS a `api.github.com`; o conector desta
análise não substitui acesso do runner. Um flag declaratório não satisfaz essa
verificação. A configuração exata de transporte está em [G02.md](G02.md).

## Validação e estado remoto

- Suíte final: **60 testes aprovados, nenhum pulado**, com PostgreSQL local
  exclusivo em tmpfs. Inclui cenários adversariais de A1–A5.
- Ruff, formatação e exportação das dependências aprovados. Aviso de depreciação
  Starlette/httpx permanece.
- Uma execução intermediária teve timeout de conexão em um teste; os sete
  testes de integração passaram na repetição, e a suíte final passou completa.
  Não se alterou timeout da aplicação para mascarar a ocorrência.
- Consulta remota somente leitura, pelo transporte fixado: `/health` HTTP 200,
  revisão `bbb9a698ca4c274e43d18f133a08039c28f0ca4a`; app e PostgreSQL saudáveis,
  zero reinícios. Imagem app:
  `sha256:99f1209220b98acd7cf80ea1b397acc246f47e0ec50517727dd82f2a45781f82`.
- API `docker.getConfig` forneceu metadados e healthchecks; execuções recentes
  de `pg_isready` tiveram exit code zero. São evidências do Maker, disponíveis
  para repetição independente, não aceite do Checker.
- Nenhum novo deploy foi solicitado, pois a proteção remota de tags não está
  estabelecida. A implantação anterior continua vigente. As correções alteram
  cliente de entrega, workflow, testes e documentação; não alteram código da
  aplicação, Dockerfile, migrations ou Compose.

Hermes e Devs Humanos devem revisar as correções e concluir os checks remotos
pendentes, incluindo comparação independente de checksums e ensaios de
persistência/recuperação no escopo autorizado. Não foram modificados privilégios,
SSH, VPS, Tailscale ou perímetro. CD automática continua não habilitada; runner,
transporte, variáveis/secrets e um run completo ainda precisam de comprovação.

```ini
G02_CHECKER_REVIEW=RECEIVED
G02_A1_A2_A3_A5=FIXED_IN_CLIENT_AND_TESTS_PENDING_REVIEW
G02_A4_CLIENT=FAIL_CLOSED
G02_A4_REMOTE_POLICY=NOT_ESTABLISHED_ADMIN_REQUIRED
G02_NEW_DEPLOY=BLOCKED_TAG_PROTECTION
G02_OVERALL=NOT_ESTABLISHED
G01_OVERALL=NOT_ESTABLISHED
```
