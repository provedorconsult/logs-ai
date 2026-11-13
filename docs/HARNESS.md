# Harness de verificação pós-deploy

Protocolo para Checker (Hermes) e Devs Humanos. Executar na homologação após
cada deploy e repetir após correção ou rollback. Registrar commit, identificação
da implantação, horário, resultado esperado/obtido e evidências sanitizadas.

## Preparação e variáveis

Criar `.env` local a partir de `.env.example`, preencher por canal seguro e
restringir permissões (`chmod 600 .env`). Ler por um carregador dotenv confiável;
não executar um `.env` de origem desconhecida como script shell.

Variáveis obrigatórias: `TEST_SERVER_HOST`, `DOKPLOY_URL`, `DOKPLOY_API_TOKEN`,
`APP_TEST_URL` e `DATABASE_URL`. Para SSH, usar `TEST_SERVER_USER` e
`TEST_SERVER_SSH_KEY_PATH`; para localizar o projeto, `DOKPLOY_PROJECT_ID`.
Validar presença sem imprimir valores. Tokens, senhas e a URL autenticada do
banco não devem aparecer em argumentos de processo, relatórios ou logs.

Acessar via OpenSSH pela Tailnet com chave dedicada, `BatchMode=yes`,
`IdentitiesOnly=yes` e verificação da chave do host; Tailscale `RunSSH=false`.
Não usar prompt de senha nem desabilitar verificação de host.

## Gates e transporte administrativo antes de operar

Confirmar os gates de [AGENTS.md](../AGENTS.md). G01 permanece
`NOT_ESTABLISHED` e G02 não está autorizada. Não executar alterações remotas ou
rollback fora do escopo aprovado; obter aprovação prévia para o plano concreto.
A revisão independente deve ser realizada por quem não atuou como Maker.

Para a API administrativa, usar túnel SSH validado ou HTTPS com certificado e
hostname validados, dentro do caminho aprovado pelo responsável. HTTP direto
no IP da Tailnet não é o padrão autorizado. A Tailnet não substitui esse gate.
O exemplo local pressupõe este túnel (expandir a chave com segurança no cliente):

```sh
ssh -N -T -o BatchMode=yes -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes \
  -i "$TEST_SERVER_SSH_KEY_PATH" \
  -L 127.0.0.1:13000:127.0.0.1:3000 \
  "$TEST_SERVER_USER@$TEST_SERVER_HOST"
```

O carregador deve expandir `~/` no caminho da chave; o shell não faz isso em
uma variável entre aspas. Executar o túnel em sessão dedicada e verificar sua
identidade, destino e disponibilidade antes de enviar tokens. Usar
`DOKPLOY_URL=http://127.0.0.1:13000` somente enquanto o túnel estiver ativo.
Para HTTPS, rejeitar certificados inválidos; nunca usar `-k` ou equivalente.
O cliente deve rejeitar redirecionamentos e destinos fora do caminho aprovado,
ler o token do ambiente e enviá-lo apenas no header exigido pela API, sem
colocá-lo na URL, argumentos ou logs. Desativar tracing e logs de headers.

## Checklist pós-deploy

- [ ] Conferir se o commit e a imagem implantados correspondem à entrega.
- [ ] No manager Swarm, executar `docker service ls` e inspecionar as tarefas
      com `docker service ps <servico> --no-trunc`. Conferir também o estado no
      Dokploy: serviços de réplica única devem indicar `1/1`; serviços escalados,
      `N/N`. Investigar tarefas rejeitadas, falhas e reinícios recorrentes.
- [ ] Executar `pg_isready` no contêiner PostgreSQL usando usuário e banco
      configurados, sem senha na linha de comando. Exigir código de saída zero
      e confirmação de aceitação de conexões. Complementar com consulta simples
      pela aplicação usando `DATABASE_URL` para validar autenticação e schema.
- [ ] Requisitar `${APP_TEST_URL%/}/health` por HTTP com timeout e exigir sucesso
      HTTP 200 e o corpo definido pelo contrato da aplicação. Exemplo, após
      carregar a variável local: `curl --fail --silent --show-error --max-time 15
      "${APP_TEST_URL%/}/health"`. Não divulgar respostas com dados sensíveis.
- [ ] Rodar testes de integração e E2E aplicáveis: ingestão, consulta, autorização,
      análise por IA, dashboard e alertas. Usar dados controlados de homologação.
- [ ] Ler logs da aplicação, do banco e do deploy; verificar erros, migrations,
      timeouts e vazamentos de dados, removendo informações sensíveis das evidências.
- [ ] Auditar segredos no diff do commit (`git show --format= --patch <commit>`)
      e, antes do commit, em `git diff --cached`. Usar scanner de segredos quando
      disponível e revisão estática de tokens, senhas, URLs autenticadas e chaves
      privadas; distinguir placeholders do `.env.example`. Conferir `git status`
      e regras com `git check-ignore`. Arquivos já rastreados não são protegidos
      retroativamente pelo `.gitignore`.

## Rollback rápido via Dokploy

1. Registrar o commit e o deployment com falha, impacto e evidências sanitizadas.
   Localizar a última implantação saudável e sua imagem/commit imutável.
2. No painel Dokploy, abrir o projeto e aplicação/Compose correspondentes e
   executar o rollback disponível para esse recurso ou reimplantar a versão
   saudável registrada. Pela API, consultar a documentação da instância
   v0.31.1 e usar a operação suportada pelo tipo de recurso; não presumir uma
   rota genérica de rollback. Usar cliente que leia `DOKPLOY_API_TOKEN` do
   ambiente e envie o header de autenticação sem token em argumentos ou logs.
3. Conferir compatibilidade das migrations antes de voltar a imagem. Se o
   schema for incompatível, seguir a recuperação de banco previamente testada;
   não executar migrations destrutivas nem restaurar backup automaticamente.
   Respeitar a autorização prévia e o escopo do procedimento de recuperação.
4. Acompanhar o deployment até concluir e repetir réplicas, `pg_isready`,
   `/health` e testes funcionais. Confirmar a versão efetivamente restaurada.
5. Abrir issue bloqueante com commits afetados, sintomas e resultado do rollback.
   Se o rollback falhar, manter o incidente aberto e acionar os responsáveis.

Aprovar a verificação apenas quando os checks aplicáveis passarem. Documentar
checks indisponíveis e suas causas; não registrar uma verificação não executada
como aprovada.
