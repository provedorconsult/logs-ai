# Auditorias e evidências históricas

A documentação ativa está no [índice operacional](../README.md). Os relatórios
abaixo mantêm os resultados e limites de cada revisão. Não inferir estado atual
pela última data no nome nem tratar resposta do Maker como revisão independente.

| Documento | Natureza |
| --- | --- |
| [Auditoria estrutural 88cd827b](REPO-STRUCTURE-AUDIT-88cd827b.md) | Parecer original de Auditor Gemini, preservado sem alteração. |
| [Confronto e correções estruturais](REPO-STRUCTURE-REMEDIATION.md) | Resposta do Maker por achado e evidências da correção. |
| [G01 — parecer final pendente](G01-CHECKER-VALIDATION.md) | Registro explícito da ausência de aceite independente; não é parecer de aprovação. |
| [G01 — revisão documental Debian 13](G01-DEBIAN13-REVIEW.md) | Consolidação histórica de evidências relatadas e limites. |
| [G02 — primeiro deploy](G02-DOKPLOY.md) | Primeira implantação e transporte autorizado. |
| [G02 — validação](G02-VALIDATION.md) | Testes e pendências, com cadeia de respostas posteriores. |
| [Correções iniciais](G02-CHECKER-FIXES.md) | Resposta do Maker ao Checker. |
| [Correções B](G02-CHECKER-B-FIXES.md) | Resposta do Maker. |
| [Correções B6](G02-CHECKER-B6-FIXES.md) | Transporte Git/proxy/TLS. |
| [Correções CD](G02-CHECKER-CD-FIXES.md) | Snapshots, verificação de tags e reconciliação. |
| [Integração MikroTik](MIKROTIK-VALIDATION.md) | Deploy, erros de importação/parsing e eventos reais. |
| [Pacote para novos servidores](NEW-SERVER-VALIDATION.md) | Testes das ferramentas/skills e limitações de bootstrap. |

Os relatórios antes na raiz de `docs/` foram movidos para este diretório mantendo
seus nomes. Links internos ativos foram atualizados; URLs de commits antigos
continuam apontando para a estrutura existente naquele commit. Não criar cópias
concorrentes dos relatórios na raiz. Novos pareceres e recibos públicos ficam
neste diretório, sem credenciais, usuários de clientes ou payloads brutos.
