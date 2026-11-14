# Interface web — evidências do Maker

Data: 14/11/2026. Código da interface G04 autorizado pela equipe humana,
com decisões em [WEB-DECISIONS.md](../WEB-DECISIONS.md).

## Testes locais

- 202 testes passaram com PostgreSQL 17 descartável, sem casos pulados; Ruff,
  formatação, Node syntax check e Actionlint aprovados. Permanece um aviso de
  depreciação Starlette/httpx já existente.
- Primeiro login bloqueia dashboard, relatórios, clientes e usuários até trocar
  senha. Troca rotaciona sessão; senha antiga, CSRF ausente e origem divergente
  são recusados. Desativação revoga acesso e último admin é preservado.
- Perfis admin/viewer, filtros literais, paginação, CSV com neutralização de
  fórmula e PDF real foram exercitados em PostgreSQL real. Hashes/snapshots de
  reparo não são retornados pelos relatórios.
- Cadastro e geração de RSC validados; senha SSH não persiste. Chave divergente
  é recusada antes da autenticação; import/SFTP e limpeza exclusiva foram
  exercitados com transporte simulado, sem escrever no roteador real.
- Registro de origens é autoritativo; revogação fecha o fluxo existente na próxima
  leitura, respeitando o cache. Falha do registro torna o coletor indisponível.
- Provisionamento real em PostgreSQL descartável criou quatro papéis e banco
  separado. SELECT-only de logs, leitura somente da view e ausência de acesso
  a web_users foram conferidos. O papel de ingestão inseriu evento, validou schema
  sem DDL e teve conexão ao banco web negada. Senhas de papéis existentes não
  foram redefinidas.
- Teste de navegador versionado passou em Chromium desktop 1440px e mobile 390px,
  sem erros de console: login/troca obrigatória, dashboard, paginação, downloads,
  criação de cliente/usuário, menu recolhível e ausência de overflow horizontal.
  Dados/senhas usados no fixture são sintéticos e não foram inseridos em produção.
- Build Docker local e imagem empacotada passaram; HTML/JS/CSS, PDF e templates
  RSC estão presentes no wheel/imagem e funcionaram por HTTP autenticado local.

## Implantação observada

Revisão de código implantada: `3dd59677b411577d9bf6a45cf5646d4107c26157`.
CI [43588338787](https://github.com/provedorconsult/logs-ai/actions/runs/43588338787):
`verify=success`, incluindo navegador, Docker e instalação descartável;
`deploy=skipped`. A implantação desta entrega foi manual pela API Dokploy
v0.31.2, contrato consultado na instância, com fonte Git fixada no SHA completo.
Isso não estabelece CD automática.

Mesmo projeto logs-ai, ambiente homologacao; novo recurso `logs-ai-web`
(`qqNBrfLNwjLCa_19TfxKP`). Deployment final do web:
`AkYyhG83_xx_PyvctrTjA`, terminado em `done`. O coletor existente foi atualizado
no deployment `T2jaW570hcUXNaKpGJxhj`, também `done`. Build logs contêm URL Git
e SHA completo; label OCI e `X-App-Revision` coincidem com a revisão acima.

| Componente | Imagem local efetivamente executada | Estado observado |
| --- | --- | --- |
| Web | `sha256:d941834ed30b5b6895da76ef57bc0af5c8d0adb16b2941b1b6d58ded49e6e212` | healthy, zero reinícios |
| Coletor | `sha256:f0deacdb716255b2b572d8cf85c81c5930032c6239d8839ada5d6f649489b322` | healthy, zero reinícios |

Os valores são IDs de imagens Docker locais, não digests de manifesto de registry.
`/health` interno do web e endpoint administrativo do coletor responderam 200,
banco `ok` e revisão exata. Logs de ambos mostram startup completo, sem traceback.
Core preexistente permanece saudável em
`bbb9a698ca4c274e43d18f133a08039c28f0ca4a`, sem recriação nesta entrega.

Banco `logs_ai_web` inicializado, checksum da migration própria conferido.
Quatro papéis efetivamente provisionados; SELECT-only nos logs, SELECT somente
na view de origens e INSERT-only na ingestão conferidos remotamente. O papel do
coletor não tem CONNECT no banco web. A credencial superusuária antiga foi
substituída, preservando as demais configurações e snapshots/journal privados.
Schema compartilhado foi validado sem DDL pelo papel de ingestão.

Conta Clovis única, ativa, admin e com troca obrigatória. Hash confere com o
bootstrap protegido; nenhuma senha em texto foi armazenada. Bootstrap removido
do ambiente persistente e web recriado no mesmo SHA sem redefinir a conta.
Uma sessão temporária própria confirmou `/api/auth/me` e HTTP 403 com
`password_change_required` em dashboard, relatórios, clientes e usuários. A sessão
foi removida por seu hash exclusivo, sem trocar a senha da conta real.

Cliente privado de referência habilitado e fingerprint conferido em leitura.
Consulta real de 153 eventos existentes, paginação de 10 itens e geração de CSV/
PDF com os dados reais passaram. Após a atualização, uma consulta SSH somente
leitura (`/system resource print without-paging`) produziu **um novo evento
`routeros.admin.logout`**, persistido para a origem cadastrada, no mesmo processo
do coletor: received +1, persisted +1, ignored/rejected/db_errors +0, fila zero.
Não foram reproduzidos novos login PPP, desconexão PPP ou alteração de usuário
PPP nesta rodada; os tipos presentes no histórico não são prova de novo fluxo.

## Domínio e limitação de validação pública

`APP_TEST_URL=https://mutti-log.canaldoprovedor.net.br` (origem pública configurada).
Dokploy associa esse host ao serviço web, porta 8080, rede `dokploy-network`,
redirect HTTP→HTTPS e resolver Let's Encrypt. Nenhuma porta web foi publicada
diretamente no host. Labels Traefik efetivas foram conferidas.

Em 14/11/2026, a tentativa HTTPS normal com validação TLS ativa foi recusada pelo
proxy do executor: `Tunnel connection failed: 403 Forbidden`, antes de alcançar
o domínio. Portanto **certificado público, acesso externo e fluxo de login pelo
hostname ainda não foram validados pelo Maker**. Não é resposta da aplicação nem
evidência de problema DNS/TLS. A política permanece restrita sem esse host na
allowlist; incluir `mutti-log.canaldoprovedor.net.br` nas configurações de rede do
ambiente permite concluir a verificação. Nenhuma rota alternativa foi usada.

O job administrativo temporário foi sanitizado/removido após os testes, sem
remover volumes. Configurações completas anteriores, intenções e recibos ficam
no armazenamento operacional protegido; não são publicados neste relatório.

O Maker não altera a senha inicial da conta real para simular primeiro acesso.
O bootstrap não mantém senha em texto, e a obrigatoriedade de troca será
conferida no registro inicial e no backend. Aplicações SSH reais dependem da
ação explícita de administrador; o roteador de referência não foi reconfigurado
por estes testes. Aceite independente permanece com Hermes/Devs Humanos.
