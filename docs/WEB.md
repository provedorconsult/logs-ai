# Interface web logs-ai

Serviço separado no projeto logs-ai. Origem pública solicitada:
`https://mutti-log.canaldoprovedor.net.br`. Escopo autorizado de interface da G04,
sem equivaler ao aceite integral da fase ou à implementação de IA.
Decisões: [WEB-DECISIONS.md](WEB-DECISIONS.md).

## Páginas e acesso

- Dashboard com dados reais, volume por período, origens e atividade recente.
- Relatórios com intervalo, origem, tipo, severidade, busca literal, paginação
  e download CSV/PDF. CSV neutraliza fórmulas; PDF inclui filtros e paginação.
- Clientes rsyslog: origens **MikroTik RouterOS 7**, geração de RSC de instalação/
  reversão e aplicação SSH explícita. Não há provisionamento de daemon Linux.
- Usuários: administradores e visualizadores, criação, edição, desativação e
  reset de senha. Pelo menos um administrador ativo é preservado.

A conta inicial solicitada exige troca de senha antes de acessar dados ou ações.
A senha inicial não é publicada neste documento. O backend bloqueia APIs até a
troca, não somente a navegação. Senhas pessoais: 12–128 caracteres e três classes
entre maiúsculas, minúsculas, números/símbolos. Reset também exige nova troca.
Cookie Secure/HttpOnly/SameSite Strict, CSRF, origem fixa e rate limit de login.
O primeiro acesso recebe credenciais pelo canal humano já utilizado, não pelo Git.

## Dados e permissões

`web_migrations/001_web.sql` aplica-se somente ao banco **logs_ai_web**, com
histórico próprio e advisory lock. O banco de logs conserva `001_initial.sql`.
Nunca adicionar migrations web ao diretório compartilhado `migrations/`.

| Papel | Acesso |
| --- | --- |
| logs_ai_web | Proprietário dos metadados web, sem privilégios globais. |
| logs_ai_web_reader | SELECT somente em log_events do banco dedicado logs-ai. |
| logs_ai_ingest | INSERT em log_events, uso da sequence e leitura dos checksums do schema; sem DDL ou acesso ao banco web. |
| logs_ai_clients_reader | SELECT somente na view web_client_sources do banco web. |

`scripts/provision_web_db.py` é executado na rede privada do PostgreSQL dedicado,
com URL administrativa no ambiente protegido. Recusa bancos administrativos do
Dokploy, outro proprietário ou papéis já existentes com privilégios amplos.
Credenciais novas devem ser hexadecimais aleatórias de 64 caracteres; o libpq
produz verificadores SCRAM antes do DDL, sem senha literal no comando SQL.
Não redefine a senha de um papel existente: autentica o valor configurado.

O artefato `deploy/web-bootstrap.compose.yml` executa esse comando em job
temporário sem portas. Executar uma vez para criar papéis/banco. Depois do primeiro startup web, repetir
com `--grant-registry` no comando do job para conceder somente a view já criada.
Depois, sanear/remover o job e sua cópia temporária de credenciais administrativas. Nunca conceder
SELECT em todas as tabelas web ao coletor, pois isso incluiria usuários/sessões.
Variáveis administrativas: `WEB_DATABASE_ADMIN_URL`, `WEB_DB_PASSWORD`,
`WEB_READER_PASSWORD`, `WEB_REGISTRY_PASSWORD`, `WEB_INGEST_PASSWORD`. Não são argumentos de CLI.

## Deploy

Usar `deploy/web.compose.yml` como Compose raw no **mesmo projeto/ambiente**,
novo recurso `logs-ai-web`, comando nativo vazio e source fixada em SHA completo.
Anexar a rede dedicada do PostgreSQL e `dokploy-network` para Traefik; não
publicar 8080 no host. Domínio Dokploy deve selecionar serviço `web`, porta 8080,
HTTPS e certificado Let's Encrypt. Conferir DNS/validação do certificado no
hostname real; não usar `-k` nem declarar HTTPS validado só por configuração.

Ambiente protegido do web:

- `APP_REVISION`, `LOGS_AI_DATABASE_NETWORK`;
- `WEB_DATABASE_URL` (papel proprietário), `LOG_DATABASE_URL` (papel SELECT-only);
- `WEB_SESSION_SECRET` (32 bytes aleatórios em hexadecimal), `WEB_PUBLIC_ORIGIN`;
- `WEB_RECEIVER_HOST`, `WEB_SYSLOG_PORT`, `WEB_SSH_DENY_HOSTS`;
- no primeiro startup: `WEB_BOOTSTRAP_USERNAME`, `WEB_BOOTSTRAP_PASSWORD_HASH`.
  O hash PBKDF2 pode ser codificado como `b64:<base64>` para proteger `$` do dotenv.
- seed opcional: `WEB_INITIAL_CLIENT_IP`, `WEB_INITIAL_CLIENT_SSH_PORT`,
  `WEB_INITIAL_CLIENT_FINGERPRINT`. É usado somente na criação inicial da conta.

Após inicialização, remover as variáveis de bootstrap e recriar o web mantendo
banco/sessões/segredo. Não persistir senha inicial em texto. Reinício não deve
recriar usuários, redefinir senhas ou restaurar um cliente excluído pelo admin.

Para tornar o cadastro autoritativo no coletor, adicionar `CLIENTS_DATABASE_URL`
com o papel da view e substituir `DATABASE_URL` pelo papel `logs_ai_ingest`,
com `LOGS_SCHEMA_MANAGED_EXTERNALLY=true`, preservando o ambiente completo e
um snapshot. Esse modo confere os checksums sem DDL; migrations novas precisam
ser aplicadas pelo proprietário antes de atualizar o worker.
Primeiro inicializar/grantar a view; só então atualizar o coletor. Sem essa
variável o modo histórico de allowlist estática continua funcionando. Com ela,
o banco é autoritativo, sem fallback aberto se houver erro; cache de três
segundos, validação por conexão/leitura e saúde indisponível em falha do registro.
Dados já aceitos na fila continuam a ser persistidos quando a origem é revogada.

## Aplicação SSH

Administrador cadastra IPv4 privado literal, porta, usuário, fingerprint e ação
alfanumérica. A senha é pedida **a cada aplicação**, não fica no cadastro/cofre do
produto. Não há campo de comando arbitrário nem aceitação automática de chave.
O serviço valida a chave antes de enviar senha, usa arquivo RSC exclusivo, importa
com comando fixo e remove somente seu arquivo. Aplicações concorrentes ao mesmo
roteador são bloqueadas. Rotas de infraestrutura são negadas via configuração.

Os scripts recusam colisões com ações/regras divergentes e não alteram usuários
PPP, perfis, firewall ou SSH. Uma aplicação recusada pode ter estado parcial;
consultar o roteador e a versão do script antes de repetir. Sucesso de importação
não é prova de recebimento: gerar eventos de teste e conferir sua persistência.
A exclusão do cadastro não remove as regras no roteador; usar script de reversão.

## Limites e testes

Relatórios aceitam até 93 dias. CSV exporta até 10.000 e PDF até 2.000 eventos,
com aviso explícito de truncamento. Fila do coletor continua em memória, sem
replay/exatamente uma entrega. Comentários/comandos brutos não são armazenados;
a interface mostra a ocorrência de alteração, não os valores anteriores/novos.

Testes Python usam PostgreSQL descartável e os guards existentes. Para navegador:

```sh
# Banco de testes configurado via TEST_DATABASE_*; nunca usar produção.
uv run --no-sync python tests/browser/serve.py
# Em outro terminal:
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm ci --prefix tests/browser
node tests/browser/web.mjs
```

O fixture valida o banco descartável e apaga seu schema antes de criar dados
sintéticos. Executa somente em loopback. O navegador usa Chromium/Chrome local,
ou `E2E_CHROMIUM_BIN`, e salva artefatos em `work/web-browser`.
Não executar esse teste contra a conta inicial de produção, pois ele troca a
senha sintética para testar o primeiro acesso.

Evidências e limitações: [WEB-VALIDATION.md](audits/WEB-VALIDATION.md).
