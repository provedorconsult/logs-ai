# Confronto e correções da auditoria estrutural de 88cd827b

Data: 14/11/2026 (America/Sao_Paulo). Maker: Codex.
Base confrontada: `3882467bdb0cd6f8c5e3a8d595f5d8ceaa9b72e0` e histórico Git.
[Relatório original](REPO-STRUCTURE-AUDIT-88cd827b.md) preservado sem alterações.
O responsável autorizou explicitamente implementação, commit, merge e deploy.

| ID | Confronto com o repositório | Correção / estado |
| --- | --- | --- |
| AUD-01 | Confirmado. Relatórios históricos ocupavam a raiz de docs; faltava índice separando procedimento vigente de evidência por versão. | Nove relatórios/validações movidos para `docs/audits/`, links internos e referências nas skills atualizados. Índices operacional e de auditorias criados. |
| AUD-02 | Parcial. A coexistência não era fonte dupla: `uv.lock` já era canônico e a CI já exigia exportação `--locked` idêntica ao arquivo versionado. Havia, contudo, dependência do arquivo derivado em build direto fora da CI. | O builder agora usa uv 0.13.6 e gera requirements diretamente de `pyproject.toml`/`uv.lock` com `--locked`. `requirements.txt` continua derivado para inspeção/clientes; a CI mantém comparação obrigatória, sem regeneração silenciosa que esconda divergência. |
| AUD-03 | Confirmado como organização; não demonstrava falha de segurança. O helper protege testes destrutivos contra banco indevido. | Movido para `tests/helpers/database_guard.py`, com pacotes/imports explícitos. Lógica dos guards preservada e testes existentes executados. |
| AUD-04 | A ausência é real. Árvore e histórico não contêm parecer final independente pós-reboot. Não há evidência suficiente para consolidar aprovação. | Criado registro `G01-CHECKER-VALIDATION.md` explicitamente pendente, com requisitos e limites. Rastreabilidade corrigida; aceite técnico permanece `NOT_ESTABLISHED`, sem assinatura fictícia de Checker. |
| AUD-05 | A ingestão já tinha autorização humana posterior explícita e foi tratada em AGENTS/README como incremento da G03, não ampliação informal da G02. O plano estava incompleto quanto ao estado entregue. | Plano atualizado com tabela por fase, escopo real, links de evidências e pendências. Ingestão continua G03; IA e aceite integral não foram presumidos. |

## Cuidados preservados

- Mover um relatório não muda os resultados históricos nem dá validade a suas
  premissas. Links relativos de acesso foram ajustados; o parecer original não
  foi reescrito. Permalinks de commits antigos continuam com a árvore antiga.
- Arquivo de ruleset e YAML não comprovam proteção administrativa de tags ou CD
  ativa. O parecer estrutural não retira as pendências técnicas registradas.
- Nenhuma migration foi adicionada ou alterada. Não se altera o MikroTik,
  firewall, SSH ou Tailscale por efeito desta reorganização.
- O deploy autorizado usa o coletor raw com fonte fixada em SHA completo,
  snapshot/journal e ambiente preservado. Não enfraquece gates do CD legado.

## Verificação desta correção

- 191 testes passaram com PostgreSQL 17 descartável, sem casos pulados; Ruff,
  formatação, Actionlint e comparação de requirements aprovados. Um aviso de
  depreciação Starlette/httpx permanece.
- Build Docker gerou requirements do lock com uv 0.13.6; a imagem uv foi fixada
  no digest observado `af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0`.
- Exportação offline com lock atual passou; alteração controlada de dependência
  em diretório descartável foi rejeitada com `--locked`, sem reescrever o lock.
- Smoke do pacote completo passou em Docker/PostgreSQL descartáveis: oito
  verificações de eventos após commit, divididas entre duas origens; atribuição
  correta e descarte do segredo sintético. Persistência sobreviveu à recriação;
  baseline do processo antigo foi rejeitado. Recursos descartáveis removidos.
- Links Markdown locais conferidos e parecer original comparado byte a byte.
  Nenhum resultado histórico foi promovido a aceite atual.

CI e implantação remota serão registradas após observação.
Pendência independente conhecida: parecer final e aceite da G01 pelo Checker e
Devs Humanos; criar um arquivo de acompanhamento não substitui a execução.
