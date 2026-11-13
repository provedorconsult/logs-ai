# Governança Maker–Checker

## Modelo operacional: Continuous Delivery

Entregas pequenas e frequentes seguem o fluxo: desenvolver, testar localmente,
auditar o diff, versionar, integrar, implantar e verificar após o deploy.
Cada implantação deve ser rastreável ao hash do commit e à imagem implantada.

## Maker (Codex)

O Maker tem autonomia total para desenvolver código, executar testes locais,
realizar `git commit` e `git merge`, publicar alterações e disparar deploy contínuo
via Dokploy, sem aprovação manual por entrega. A revisão ocorre após o deploy.
Antes de publicar, execute os testes aplicáveis e audite os arquivos staged para
impedir inclusão de credenciais ou alterações alheias à entrega.

A infraestrutura de referência informada é Debian 13, Docker 29.9.3 em Swarm,
Docker Compose v5.7.1 e Dokploy v0.31.1. Confirme as versões no ambiente quando
executar uma implantação; este documento não constitui inventário verificado.

O acesso ao servidor deve ser exclusivamente não interativo, por chave SSH
dedicada na Tailnet e tokens de API. Mantenha o Tailscale SSH desativado
(`RunSSH=false`); use o OpenSSH do servidor pela Tailnet. Use `BatchMode=yes`,
`IdentitiesOnly=yes`, autenticação por chave e validação de host conhecido.
Não use senhas em argumentos de processo, URLs, logs ou arquivos versionados.
Não desative a validação da chave do host. Tokens devem ser lidos do ambiente
local protegido e enviados por cliente de API sem expô-los na linha de comando.

O `.env` local e as chaves privadas nunca são versionados. O `.env.example`
contém apenas placeholders. Não imprima variáveis sensíveis, não ative shell
tracing durante operações autenticadas e não inclua segredos em issues.

## Checker (Hermes) e Devs Humanos

Atuam em revisão pós-deploy diretamente no código versionado e no servidor de
testes configurado no `.env` local. Executam testes de integração e segurança,
leitura de logs e validação funcional conforme [o harness](docs/HARNESS.md).
Registram commit, implantação, resultados e evidências com dados sensíveis
removidos. Em caso de regressão, podem acionar rollback no Dokploy ou abrir
issues bloqueantes. Uma regressão bloqueante deve ser resolvida ou revertida
antes de novas entregas dependentes.

## Planejamento e recuperação

Siga [o plano de implantação](docs/DEPLOYMENT_PLAN.md). Antes de cada deploy,
identifique a última versão saudável e a compatibilidade das migrations.
Rollback da aplicação não desfaz automaticamente mudanças no banco; preserve
backups e um caminho de recuperação testável.
