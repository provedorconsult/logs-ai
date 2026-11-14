---
name: logs-ai-dokploy
description: Instalar ou inspecionar Dokploy em uma VPS nova para logs-ai, usando instalador oficial revisado, acesso validado e preservação de infraestrutura existente.
---

# Pré-condições

Leia `AGENTS.md`, `docs/NEW-SERVER.md` e a skill `logs-ai-project`.
Instalar Dokploy modifica Docker/Swarm e serviços do host. Execute somente no
destino e escopo autorizados; uma tarefa de documentação não autoriza executar
bootstrap em um host não identificado. Não repetir aprovação já concedida.

## Inventário e preparação

- Confirmar sistema/arquitetura, privilégios, disco, RAM, DNS/rota e portas
  80/443/3000 conforme a versão oficial. Referência histórica Debian 13 e
  Dokploy 0.31.1 não garante compatibilidade em outra versão.
- Ler Docker/Compose, estado Swarm e serviços/volumes já existentes. Se Dokploy
  já existe, inspecionar/usar a instalação; não rodar instalador como atualização.
- SSH VPS por chave dedicada, host key independente, BatchMode/IdentitiesOnly,
  sem senha fallback. Tailscale SSH `RunSSH=false`; respeitar transporte do runtime.
- Definir antes o acesso administrativo privado/HTTPS/túnel e o perímetro.
  O instalador pode publicar portas do host; não iniciar sem saber se serão
  expostas à WAN. Ajustes de firewall/base precisam caber no escopo vigente.

## Instalação nova

1. Consultar documentação oficial `https://docs.dokploy.com/` e instalador
   `https://dokploy.com/install.sh` por HTTPS validado. Baixar para arquivo
   privado no host/executor; nunca usar curl com `-k` nem pipe direto para shell.
2. Revisar conteúdo/efeitos, integridade/hash e forma de selecionar versão na
   **versão efetivamente baixada**. Fixar release suportada quando disponível e
   registrar versão, origem e hash. Não inventar flags ou variável de versão.
   Se download der 403, usar fonte oficial documentada e conferir o conteúdo;
   não executar HTML de erro nem buscar mirror aleatório.
3. Executar o arquivo revisado com privilégio necessário no host autorizado.
   Não apagar/reinicializar Swarm, volumes ou redes existentes para fazê-lo passar.
4. Conferir serviços Dokploy/Traefik e dependências administrativas, versão
   real, armazenamento e bindings. Concluir cadastro inicial pelo canal seguro
   apropriado; credenciais/tokens ficam no cofre/armazenamento protegido.
5. Ler OpenAPI da instância autenticada pelo canal autorizado. Token somente
   em header, origem fixada, sem redirects. Verificar chamadas de projeto,
   ambiente, Compose/env/deployment e leitura de logs antes de automatizar.

## Evidências e recuperação

Guardar log sanitizado, versões/hashes e endpoint seguro, nunca token ou senha.
Instalação parcial exige comparar serviços/volumes criados com o inventário:
remover somente recursos comprovadamente próprios quando a recuperação exigir.
Não desinstalar Dokploy existente nem remover volumes como limpeza genérica.
Depois, seguir `logs-ai-stack`; o banco interno do Dokploy não é o banco logs-ai.
O bootstrap desta skill não foi validado em uma VPS nova nesta padronização;
precisa ser observado no destino. Não transformar instruções em evidência.
