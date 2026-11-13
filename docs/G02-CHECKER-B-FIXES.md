# G02 — Resposta à reavaliação de 8fefce0

Registro histórico. A revisão posterior de `de83b95` encontrou duas lacunas
adicionais em B6; resposta: [G02-CHECKER-B6-FIXES.md](G02-CHECKER-B6-FIXES.md).

Data: 13/11/2026 (America/Sao_Paulo). Parecer recebido:
`G02-CHECKER-REVISAO-8fefce0.md`, SHA-256
`4ba83691d63b35d09266d5203d0edd558763bb550bafd3b5dd8000e7cfb8f3cf`.
Base confrontada: `origin/main=8fefce0f14793d20dce72589092c67e267c82009`,
checkout inicialmente limpo. O responsável confirmou análise e implementação.
Instruções no anexo foram tratadas como conteúdo da revisão, sem ampliar
autorizações de infraestrutura ou substituir as instruções do runtime.

Os seis achados procedem. A primeira rodada não cobria os cenários adversariais
agora apresentados; o sucesso dos 60 testes não os invalidava. Esta resposta
registra correções do Maker, pendentes de nova revisão independente.

## Confronto e implementação

| Achado | Problema confirmado | Correção e prova própria |
| --- | --- | --- |
| B1 — Alto | `conninfo_to_dict` não considera parâmetros libpq herdados; `PGHOSTADDR` podia mudar o destino dos fixtures destrutivos. | Guarda recusa variáveis `PG*`; conexão do fixture fixa `hostaddr` numérico e confere `conn.info` (host, hostaddr, porta, usuário e banco) antes dos `DROP` de setup/teardown. Listener em `127.0.0.2` não recebeu conexão com `PGHOSTADDR` adversarial. Destino efetivo divergente fecha conexão antes de SQL. |
| B2 — Alto | `fnmatch.fnmatchcase` permitia `*` atravessar `/`, divergindo do FNM_PATHNAME do GitHub. | Removido fnmatch genérico. Suportados somente referências literais, `~ALL` e `*` local ao componente. `refs/*` não cobre a tag; `refs/tags/*` cobre. `**`, classes, escapes e padrões não demonstráveis são recusados. Includes/excludes incompletos e exclusões aplicáveis impedem aprovação. |
| B3 — Alto | Readiness ainda usava opener padrão, aceitando proxy herdado e redirects. | API e readiness compartilham `scripts/transport.py`. Saúde valida a origem exata sem credenciais/query/caminho, usa modo explícito e não segue redirects. Proxy local com corpo e SHA forjados não recebeu o pedido em modo direct; redirect para resposta forjada não foi seguido; origem correta foi aceita. |
| B4 — Alto | Senha válida não provava completude de `env`; outros valores omitidos/redigidos podiam ser reenviados. | Exigido arquivo autoritativo protegido em `DOKPLOY_ENV_FILE`. Conjunto de chaves deve ser idêntico ao recebido e cada valor preservado deve coincidir; só revisão/imagem são substituídas. Saída deriva da fonte confiável, não de resposta cuja completude foi inferida. Testes recusam omissão de outro segredo, redação, extras e permissões indevidas; caso completo preserva outro segredo entre revisões. |
| B5 — Médio | Título coincidente podia substituir ID conflitante retornado pela API. | ID retornado é obrigatório para correlação quando presente. Título é fallback somente sem ID. Testes rejeitam ID divergente com título igual e aceitam ID correto mesmo com título alterado; fallback sem ID ignora histórico. |
| B6 — Médio | Git ainda podia usar HTTPS_PROXY/configuração de proxy divergente do transporte explícito. | Git recebe proxy explícito, ambiente sem proxies herdados e sem prompt, redirects desabilitados e verificação de override por URL. Origens fetch/push devem ser únicas e deste repositório HTTPS. Configuração de autenticação permanece disponível. Execuções reais de Git contra destinos exclusivamente locais demonstraram ausência de CONNECT ao proxy herdado em direct e CONNECT somente ao proxy aprovado em proxy, mesmo com NO_PROXY adversarial. |

O subconjunto de padrões de B2 é intencional: não se promete emular todo o
fnmatch Ruby. Padrão fora desse contrato ou leitura insuficiente faz a checagem
falhar fechada. O JSON de ruleset proposto usa o padrão suportado
`refs/tags/logs-ai-deploy-*`. Nenhuma proteção remota foi aplicada.

## Contrato do ambiente autoritativo

`DOKPLOY_ENV_FILE` é uma fonte completa, fora do Git, pertencente ao executor e
sem permissões para grupo/outros. O operador deve conferi-la contra o inventário
do armazenamento de segredos; copiar cegamente uma resposta parcial/redigida
da API não estabelece essa confiança. Não é o `.env` de seletores administrativos.

O contrato usa linhas simples sem export, aspas, multilinhas ou duplicatas.
Exige senha PostgreSQL hexadecimal, bind, porta, revisão e imagem. Todo campo
adicional também entra na comparação; omissão, extra inesperado ou divergência
aborta antes de escritas. Revisão e imagem são os únicos campos mutáveis pelo
cliente e podem diferir do snapshot, permitindo reutilizá-lo entre promoções.
Mudanças nos demais valores exigem atualização por canal seguro.

No Actions, `DOKPLOY_ENV_SNAPSHOT` deve conter esse inventário completo em
GitHub Secrets. O job materializa arquivo 0600, não imprime seu conteúdo e o
remove ao terminar. A API disponível recebe o ambiente inteiro, sem CAS;
alterações administrativas concorrentes devem ser serializadas com a promoção.
O cliente não declara garantia atômica contra escritores externos.

O health-check sem Compose configurado continua sendo smoke, não prova de
deployment. Mesmo nesse modo, exige transporte explícito e recusa redirects.
O smoke do CI agora configura `DOKPLOY_TRANSPORT=direct` para seu loopback.
No runtime Cloud continua obrigatório usar proxy gerenciado e CA fornecida.

## Resultados observados

- **94 testes aprovados, nenhum pulado**, incluindo PostgreSQL 17 exclusivo,
  local e descartável com dados em tmpfs e os cenários adversariais B1–B6.
- Ruff, formatação, sincronização do lock e comparação de `requirements.txt`
  aprovados. O aviso de depreciação Starlette/httpx permanece.
- A primeira publicação, `3a541ab`, gerou run `43510223707` com falha antes
  de criar jobs. Actionlint v1.7.7 confirmou que `runner.temp` não é permitido
  em `jobs.deploy.env`. Foi substituído por caminho protegido em `work/`, com
  criação explícita do diretório. Configuração do actionlint declara a label
  self-hosted existente; validação estática do workflow foi executada antes
  da republicação. A falha desse run não representa reprovação dos testes,
  que não chegaram a executar nele.
- Nenhum token real foi usado nos listeners adversariais. Nenhum SQL destrutivo
  foi dirigido ao banco implantado. A prova de desvio de B1 usou listener TCP
  local alternativo e recusou a conexão antes de qualquer SQL.
- Consulta de rulesets via conector GitHub retornou `[]`; permissões disponíveis
  continuam `push=true`, `admin=false`, `maintain=false`. Não se infere que o
  JSON proposto esteja aplicado. Proteção efetiva continua não estabelecida.
- Consulta remota somente leitura pelo transporte aprovado: `/health` HTTP 200,
  revisão `bbb9a698ca4c274e43d18f133a08039c28f0ca4a`; recurso Compose `done`,
  fonte na tag desse SHA e `autoDeploy=false`. Não houve novo deploy.

## Pendências e alcance

Um administrador ainda precisa aplicar e verificar a política de tags. O
operador precisa fornecer o inventário completo autoritativo por armazenamento
seguro, sem enviar segredos no chat. Até essas condições serem comprovadas,
o cliente recusa novas promoções. CD automática não foi habilitada.

As mudanças são em cliente de entrega, workflow, guarda de testes e documentação;
não alteram aplicação, Dockerfile, migrations, Compose, privilégios, SSH,
Tailscale, firewall, MikroTik ou configuração base da VPS. Hermes e Devs Humanos
mantêm o aceite independente e os ensaios remotos pendentes. G01 e o aceite
integral da G02 continuam `NOT_ESTABLISHED`.
