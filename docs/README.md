# Documentação ativa

Use esta página para operação atual. Relatórios descrevem versões e datas;
não substituem o estado observado da implantação.

| Necessidade | Referência ativa |
| --- | --- |
| Governança e autorização | [AGENTS.md](../AGENTS.md) |
| Fases, escopo entregue e pendências | [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md) |
| Novo servidor ou outro MikroTik | [NEW-SERVER.md](NEW-SERVER.md) |
| Interface web, domínio e autenticação | [WEB.md](WEB.md) |
| Procedimento e limites MikroTik | [MIKROTIK.md](MIKROTIK.md) |
| Skills para agentes | [SKILLS.md](SKILLS.md) |
| Erros conhecidos | [RUNBOOK.md](RUNBOOK.md) |
| Contrato operacional G02/CD legado | [G02.md](G02.md) |
| Validação e revisão | [HARNESS.md](HARNESS.md) |
| Histórico, auditorias e respostas | [audits/README.md](audits/README.md) |

`uv.lock` é a fonte das dependências; `requirements.txt` é exportação derivada,
conferida na CI. O Docker gera sua exportação do lock durante o próprio build.
A existência do workflow e do arquivo de ruleset não comprova CD ou proteção
administrativa ativa. Autorização humana, evidência técnica e aceite independente
são estados distintos.
