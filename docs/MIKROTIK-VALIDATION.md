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
