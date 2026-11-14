# Evidências da integração MikroTik

Data: 14/11/2026 UTC. Maker: Codex; revisão independente pendente.

## Implementação e testes

- 150 testes aprovados com PostgreSQL 17 descartável, incluindo persistência
  transacional de eventos TCP/CEF e legados, rejeição de origem não permitida,
  framing limitado, descarte de comandos/segredos e retry de falha do banco.
- Ruff e formatação aprovados. Um aviso de depreciação Starlette/httpx permanece.
- Monitor SSH valida a chave antes de autenticar; comandos são fixos e de leitura.
- Não há migration adicional nem alteração do core G02 ou do seu volume.

## Roteador observado

Após confirmação humana do fingerprint, autenticação SSH e consultas de leitura
confirmaram RouterOS 7.24.5, fuso America/Bahia e propriedades de logging TCP/CEF.
Na inspeção inicial, ação e regras desta integração ainda não existiam.
Não foram consultadas senhas PPP nem alterada configuração do roteador.
Contagens operacionais e credenciais não são publicadas neste relatório.

## Deploy e aceite

Coletor implantado: `0d4e729fb88bf39f019ce39cfcc54bc215985e47`.
CI [43535488453](https://github.com/provedorconsult/logs-ai/actions/runs/43535488453):
`verify=success`, `deploy=skipped`. O deploy foi executado pelo Maker via API.

- Recurso `logs-ai-mikrotik` no projeto `logs-ai`, ambiente `homologacao`.
- Deployment `4qPC4EOTuW3WTph3_heyU`: `done`; logs de build confirmaram fetch
  do objeto Git completo. Imagem:
  `sha256:3585bf5e52fe9d56f868af09ec8f1f844e5a1b997a15cb56cf470e8232e99ad9`.
- Contêiner saudável, UID `10001:10001`, filesystem somente leitura, zero
  reinícios na inspeção. Label OCI e `X-App-Revision` iguais ao SHA implantado.
- `/health`: HTTP 200, `status=ok`, `database=ok`. Saúde administrativa usa
  a porta 18002 no IP Tailnet configurado (`APP_TEST_URL` registrado no recibo
  operacional protegido); recepção somente `192.168.15.25:5514/tcp`.
- Consulta remota de leitura confirmou somente `001_initial.sql`, checksum
  `e749720863762629d83a527ccfc9adc5755a48c87d185e7319cdc51553a6dfe2`.
- Conexão sintética originada da VPS foi encerrada pelo filtro; nenhum evento
  desse teste foi persistido. Zero eventos reais na primeira consulta do banco.

O artefato raw Compose fixa o contexto de build no SHA completo, sem depender
de criação/recriação de tags. O CD anterior baseado em tags continua pendente;
esta entrega não comprova proteção administrativa de tags ou CD automático.

Aplicação dos scripts pela equipe de redes e recebimento real dos eventos
PPPoE/administrativos ainda pendentes. Testes sintéticos não comprovam esse
recebimento. Aceite independente permanece com Hermes e Devs Humanos.

## Correção após primeira tentativa de importação

A equipe informou `duplicate owned prefix` na importação. Consultas SSH somente
leitura no RouterOS 7.24.5 reproduziram a colisão de nomes: usando variável
`prefix`, a expressão `find where prefix=$prefix` selecionou cinco regras;
consultas literais dos dois prefixos retornaram zero. Usando `rulePrefix`, a
mesma busca retornou zero corretamente. A ação da integração também não existia.
Logo, o erro informado não demonstrava duplicidade real e ocorreu antes das
adições do script. Nenhuma configuração foi removida ou alterada pelo Maker.

Instalação e reversão corrigidas para usar `rulePrefix`, preservando as
validações de colisão real. O filtro corrigido foi validado por leitura no
roteador; a importação completa continua pertencendo à equipe de redes.
Não houve alteração no código/imagem do coletor, que permanece em `0d4e729`.


## Nome da ação compatível com RouterOS

Na segunda tentativa, a equipe observou rejeição de `logs-ai-private` em
`/system logging action add`: o RouterOS exige somente letras e números no
nome da ação. Instalação, reversão e monitor foram alinhados para `logsaiPrivate`.
Os prefixos de mensagens permanecem iguais. A falha informada ocorreu na
criação da ação, antes das adições de regras; não indica configuração completa.
Esta correção não requer novo deploy do coletor. A importação completa ainda
precisa ser confirmada pela equipe; não foi executada pelo Maker.

## Primeira aplicação bem-sucedida e compatibilidade CEF

A equipe confirmou importação concluída. Inspeção SSH somente leitura confirmou
`logsaiPrivate` e exatamente uma regra para cada prefixo. A conexão TCP ficou
ativa, mas os primeiros eventos foram ignorados, sem erro de banco: o cabeçalho
nativo usa o modelo `CCR2116-12G-4S+` como Device Product e `7.24.5 (stable)` como
versão; o parser original aceitava somente `RouterOS` como produto.

Diagnóstico passivo temporário, restrito ao namespace de rede do coletor e ao
fluxo do roteador para TCP/5514, extraiu somente estrutura/cabeçalho e indicadores
de tipos de evento; não publicou mensagens, usuários, comandos ou credenciais.
Parser ajustado para modelos CCR/CRS/RB, mantendo validação do fabricante e
normalização sem persistir mensagens brutas. Sete casos de regressão adicionais
cobrem cabeçalho nativo e rejeição de fabricante/produto desconhecido.
157 testes passaram com PostgreSQL 17 descartável; Ruff passou. O teste de
pipeline TCP/PostgreSQL também usa o cabeçalho nativo com identidades sintéticas.
Novo deploy e evidência de eventos reais serão registrados após a implantação.

## Separador adicional de prefixo RouterOS

O primeiro deploy de compatibilidade CEF (`e9cba0d`, CI 43543015457 aprovada)
recebeu eventos reais e gravou início/fim de sessão. A inspeção adicional mostrou
que RouterOS acrescenta `: ` ao prefixo configurado, produzindo
`logs-ai-admin: : user ...` e `logs-ai-ppp: : ...`. Isso impedia autenticação e
mudanças administrativas e podia classificar login/logout administrativo como
PPP, além de manter `: ` no identificador PPP. Essa implantação não valida todos
os tipos solicitados e não deve servir como evidência de classificação correta.

Parser corrigido para aceitar o separador nativo, sem exigir mudança no roteador;
classificação PPP exige tópico PPP/PPPoE. Regressões cobrem os dois formatos de
prefixo e impedem classificar mensagens system como PPP. Registros produzidos
antes da correção precisam de reconciliação identificável; não apagar eventos.

## Deploy com separador corrigido e reconciliação

Revisão implantada: `827fa14a29d52598fdc967699887acd1f127146e`.
CI [43543735059](https://github.com/provedorconsult/logs-ai/actions/runs/43543735059):
`verify=success`, `deploy=skipped`. 163 testes locais passaram com PostgreSQL 17.
Deployment `1fm0EbxwkwfcGpt3SppeN`: `done`; build fixado no objeto Git completo.
Imagem `sha256:dbbfe60e6245b2d2e761dde44234ad8f9c839e50c4f043e025cf2454c8132d52`.
`/health` retornou 200, banco OK e header igual à revisão. O contêiner ficou
saudável sem reinícios, com recepção privada e o core anterior preservados.

Reconciliação transacional dos registros da versão intermediária:

- Fonte exata `mikrotik:192.168.15.1`, intervalo entre criação do deployment
  `e9cba0d` e início do contêiner `827fa14`, username começando com `: `,
  mensagem/tipo anterior iguais a `pppoe.session.started` ou `ended`.
- Para tópicos system/account sem PPP e username `: user <ator>`, tipo corrigido
  para login/logout administrativo e ator extraído. Para tópicos PPP/PPPoE,
  somente o separador indevido do username foi retirado.
- Valores anteriores de mensagem/atributos foram preservados em
  `normalization_previous`; `normalization_repaired_by` registra a revisão.
  Fonte, ID e horário de recepção foram preservados. Nenhum evento foi apagado.
- 16 registros corrigidos: cinco inícios PPP, cinco términos PPP, três logins
  e três logouts administrativos. Zero casos desconhecidos e zero candidatos
  restantes. A auditoria inicial tinha 14 registros; mais dois chegaram antes
  da troca de versão. Plano e recibo completos ficam no armazenamento protegido.
- Procedimento validado em PostgreSQL descartável para dry-run sem escrita,
  aplicação, idempotência, preservação de originais e isolamento de outra fonte.

Após o novo deploy, logout administrativo nativo foi recebido e gravado com
classificação correta. A equipe foi solicitada a repetir a alteração de usuário
após a correção. Eventos anteriores ignorados não foram recuperados: não havia
replay nem persistência de mensagem bruta. Contadores `/metrics` representam o
processo atual e não incluem reparos históricos executados diretamente no banco.

## Eventos reais confirmados após repetição pela equipe

A equipe informou nova autenticação/desconexão PPPoE e alteração de comentário
em uma conta de teste de `/user`. Consulta remota em transação somente leitura
confirmou os seguintes eventos posteriores ao início do contêiner `827fa14`
(`2026-11-14T02:01:51.28990822Z`, 13/11/2026 às 23h01 em São Paulo):

| Tipo | Eventos persistidos na consulta |
| --- | ---: |
| `pppoe.authenticated` | 3 |
| `pppoe.session.started` | 3 |
| `pppoe.session.ended` | 6 |
| `routeros.admin.login` | 1 |
| `routeros.admin.logout` | 1 |
| `routeros.admin_user.updated` | 1 |

A busca restrita ao identificador de teste informado pela equipe confirmou uma
atualização administrativa. Identificadores de clientes/operadores e valores de
comentário não são publicados. O coletor registra o evento de alteração e o
ator/usuário disponíveis, sem guardar comandos nem conteúdo anterior/novo dos
campos; portanto o valor exato do comentário não foi comprovado pelo banco.

Contadores do processo: 24 recebidos, 15 persistidos, nove ignorados, zero erros
de banco, zero rejeições, fila vazia e conexão TCP ativa. Mensagens de estado
intermediário não reconhecidas podem ser ignoradas; as contagens são de eventos,
não de sessões únicas. Uma desconexão pode gerar mais de uma mensagem nativa.
Os eventos acima foram observados na versão corrigida, sem depender dos reparos
históricos. Migration/checksum permaneceram iguais; saúde HTTP 200, revisão
conferida, contêiner saudável sem reinícios. Core G02 preservado em `bbb9a69`.

Validação funcional observada: autenticação PPPoE, início/fim de sessão e
alteração de conta administrativa `/user`. Alterações de clientes em
`/ppp secret` têm testes sintéticos, mas ainda não foram demonstradas com evento
real nesta rodada. Esses dois menus não são equivalentes. Revisão independente
Hermes/Devs Humanos e aceite integral dos gates/CD continuam pendentes.
