# Decisões da interface web

Data: 14/11/2026. Responsável pela implementação: Maker/Codex.
Autorização humana: implementar, publicar e implantar serviço web separado no
mesmo servidor/projeto logs-ai, com autonomia até a conclusão. O usuário escolheu
MikroTik RouterOS 7 e solicitou cadastro, geração e opção de aplicação SSH.

| Tema | Decisão e motivo |
| --- | --- |
| Serviço | FastAPI separado, arquivos HTML/CSS/JS locais, sem CDN ou dependência de frontend em runtime. Integra-se ao backend Python já existente. |
| Interface | Mobile first, menu recolhível/drawer, dashboard com dados reais, relatórios paginados, cadastro de clientes e gestão de usuários. Não inserir dados demonstrativos em produção. |
| Domínio | `mutti-log.canaldoprovedor.net.br`, Traefik do Dokploy, HTTPS e certificado Let's Encrypt. Não alterar outros domínios ou DNS da Cloudflare sem necessidade/escopo. |
| Dados | Banco `logs_ai_web` separado no PostgreSQL dedicado do projeto. Migrations próprias em `web_migrations`, sem adicionar versões ao schema do core/coletor. |
| Privilégios | Web lê logs com papel SELECT-only. Papel separado lê apenas a view de IPs ativos; a escrita dos logs usa outro papel INSERT-only e valida checksums sem DDL. O coletor deixa de receber a credencial superusuária legada e não acessa usuários/sessões. Metadados são administrados pelo papel proprietário do banco web. |
| Administração inicial | Conta Clovis conforme solicitação; senha recebida somente como hash PBKDF2 com salt, sem valor literal no código/documentação. Troca obrigatória verificada no backend antes de qualquer página/API funcional. Reinício não redefine senha nem recria cliente apagado. |
| Sessão | Token aleatório, somente hash no banco, cookie Secure/HttpOnly/SameSite Strict, expiração de 8h, CSRF e verificação da origem. Rotação após troca de senha; revogação em reset/desativação/mudança de perfil. |
| Perfis | Administrador gerencia clientes e usuários. Visualizador consulta/exporta. Proibir remover o último administrador ativo. |
| Clientes | Menu denominado clientes rsyslog, especializado em MikroTik RouterOS 7 com TCP/CEF, sem instalar um daemon Linux rsyslog. IPs privados exatos, máximo 32 ativos, aplicados ao coletor via view com cache de 3s e falha fechada. |
| SSH | Host/porta/usuário no cadastro, fingerprint confirmado obrigatório, senha informada por aplicação e nunca persistida. Validar host key antes de autenticar. RSC gerado de templates conhecidos, arquivo remoto exclusivo e limpeza somente do próprio arquivo. Não existe campo de comando arbitrário. |
| Aplicação remota | Ação explícita de administrador com CSRF/confirmacão, limite de concorrência e lock por roteador. Respeitar restrições de escopo: o Maker não aplica configuração automaticamente no MikroTik de referência para testar a interface. Aplicação bem-sucedida não equivale a fluxo de logs comprovado. |
| Relatórios | Filtros parametrizados de data/origem/tipo/severidade/busca, intervalo máximo de 93 dias e ordenação estável. CSV até 10 mil e PDF até 2 mil registros, com aviso explícito de limite. CSV neutraliza fórmulas; PDF escapa textos. Uma exportação por processo. |
| Conteúdo | Exibir somente campos normalizados; não retornar snapshots de reparo ou comandos. O sistema registra eventos, não o before/after dos comentários. |
| Validação | Banco descartável e testes de segurança, navegador desktop/mobile e downloads antes de publicar. Na conta inicial real, testar a obrigatoriedade sem alterar a senha escolhida pelo usuário. |
| Segredos | Não solicitar segredos pelo chat, não versionar valores e não exibir credenciais em logs. Hash de bootstrap codificado em base64 para evitar interpretação de `$` em dotenv. |

## Rede do executor

O ambiente foi temporariamente desconectado e retomado com os arquivos locais
preservados. A API Dokploy permaneceu acessível após a retomada. A política
restrita do proxy recusou a conexão HTTPS ao domínio público com 403. Foi
solicitada a inclusão desse host nas configurações do ambiente; nenhuma rota
alternativa será usada para contornar a política. Implantação/configuração no
Dokploy e testes locais podem prosseguir independentemente dessa liberação.

## Resultado das decisões

Código `3dd5967` publicado e implantado no web e coletor em 14/11/2026, com CI
aprovada. Bootstrap removido após inicialização; conta real preservada com troca
obrigatória, também conferida na API interna. Testes SSH do Maker limitaram-se
à consulta de recurso e chave do roteador, sem aplicar RSC. Evidência de novo
fluxo desta rodada é somente um logout administrativo persistido.

O core histórico foi preservado. A entrega usa deploy manual por SHA; gates
pendentes de CD e aceite independente não foram declarados concluídos.
O host público continua bloqueado pelo proxy do executor: configuração HTTPS
confirmada no Dokploy/Traefik, validação pública TLS/login pendente de grant de
rede. Detalhes e IDs em [WEB-VALIDATION.md](audits/WEB-VALIDATION.md).
