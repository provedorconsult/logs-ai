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

## Implantação

A execução de CI, recursos Dokploy, domínio/HTTPS, revisão implantada e verificações
remotas serão registradas após observação. No executor, a tentativa de conectar
ao domínio público foi negada pelo proxy com 403 por falta de grant do hostname.
Isso não constitui resposta da aplicação ou evidência de problema no DNS/TLS.
Foi solicitado ajuste do ambiente; a API administrativa permanece acessível.

O Maker não altera a senha inicial da conta real para simular primeiro acesso.
O bootstrap não mantém senha em texto, e a obrigatoriedade de troca será
conferida no registro inicial e no backend. Aplicações SSH reais dependem da
ação explícita de administrador; o roteador de referência não foi reconfigurado
por estes testes. Aceite independente permanece com Hermes/Devs Humanos.
