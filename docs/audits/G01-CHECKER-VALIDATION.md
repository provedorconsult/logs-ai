# G01 — registro de validação independente pendente

Data: 14/11/2026 (America/Sao_Paulo). Autor deste registro: Maker/Codex.
**Este arquivo não contém um parecer final do Checker nem aprovação da G01.**

O confronto da auditoria estrutural consultou a árvore e o histórico publicado,
`AGENTS.md`, o plano, o harness e a [revisão Debian 13](G01-DEBIAN13-REVIEW.md).
Não foi localizado no repositório um relatório independente de validação final
pós-reboot com os resultados exigidos. O anexo histórico citado naquela revisão
não está publicado integralmente e não deve ser reconstruído por suposição.

```ini
RECORD_TYPE=PENDING_EVIDENCE_REGISTER
G01_OVERALL=NOT_ESTABLISHED
CHECKER_FINAL_REPORT=NOT_AVAILABLE_IN_REPOSITORY
CHECKER_INDEPENDENCE=NOT_ESTABLISHED
```

## Evidências a consolidar pelo Checker e Devs Humanos

- Identidade/versões do host e transporte administrativo validado, incluindo
  estado efetivo de `RunSSH=false`, sem expor credenciais ou caminhos de chaves.
- Controles de acesso/perímetro IPv4/IPv6 com testes positivos/negativos e
  configuração atual, sem inferir proteção de uma conexão recusada isolada.
- Persistência e retorno dos serviços após reinício controlado autorizado,
  caminho de recuperação administrativa e registro de antes/depois.
- Backup, restauração e rollback demonstrados em destino controlado.
- Resultado independente, autor, data, revisões/recursos avaliados, limitações
  e decisão humana. Um arquivo criado pelo Maker não satisfaz esse item.

Os eventos reais do coletor e a autorização para desenvolver/implantar não
substituem essas evidências. Esta correção resolve a falta de um registro
explícito da pendência; não encerra a pendência técnica apontada em AUD-04.
Quando existir parecer independente, anexá-lo com autoria e evidências próprias,
preservando a trilha deste registro. Não reclassificar G01 por renomear arquivo.
