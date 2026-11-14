# Skills do projeto para agentes sem contexto

Ponto de entrada: [logs-ai-project](../.agents/skills/logs-ai-project/SKILL.md).
As skills ficam em `.agents/skills/<nome>/SKILL.md`, com frontmatter `name` e
`description`. Runtimes que descobrem essa convenção podem invocá-las pelo nome.
Nos demais, abrir explicitamente o arquivo; não pressupor instalação global.

| Skill | Quando usar |
| --- | --- |
| [logs-ai-project](../.agents/skills/logs-ai-project/SKILL.md) | Reconstruir contexto, inventariar destino e coordenar a instalação. |
| [logs-ai-dokploy](../.agents/skills/logs-ai-dokploy/SKILL.md) | Instalar ou avaliar Dokploy em VPS nova, com acesso e perímetro definidos. |
| [logs-ai-stack](../.agents/skills/logs-ai-stack/SKILL.md) | Gerar perfil e implantar core/coletor/banco pelo Dokploy. |
| [logs-ai-postgres](../.agents/skills/logs-ai-postgres/SKILL.md) | Provisionar/validar PostgreSQL dedicado, persistência, migrations e backup. |
| [logs-ai-mikrotik](../.agents/skills/logs-ai-mikrotik/SKILL.md) | Adaptar e entregar scripts, conferir RouterOS e acompanhar a equipe. |
| [logs-ai-validation](../.agents/skills/logs-ai-validation/SKILL.md) | Testar ponta a ponta, registrar limitações e preparar revisão independente. |
| [logs-ai-web](../.agents/skills/logs-ai-web/SKILL.md) | Implantar console web, banco isolado, clientes MikroTik e domínio HTTPS. |

Exemplo de solicitação a um agente novo:

> Leia AGENTS.md e use a skill logs-ai-project. Prepare a implantação de um novo
> logs-ai a partir de deploy/profiles/example.json. Inspecione recursos existentes,
> use as credenciais somente pelo armazenamento seguro, gere o pacote privado,
> implante no projeto correto e valide eventos novos por roteador. Respeite o
> escopo humano vigente para VPS/Dokploy/MikroTik; não reaproveite os IPs ou IDs da
> instalação histórica. Entregue revisão/digest, recibo e pendências observadas.

Cada skill separa pré-condições, execução, evidências e recuperação. Elas não
concedem autorização por si e não substituem instruções humanas vigentes.
O trabalho atual padroniza o repositório: não instala outro servidor nem altera
o MikroTik de referência automaticamente.
