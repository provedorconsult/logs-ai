# G02 — Reconciliação e ciclo de vida dos artefatos de CD

Data: 13/11/2026 (America/Sao_Paulo). Parecer sobre `6335f02` transcrito no
chat pelo responsável; base local/remota conferida:
`6335f02410626374381cec587cd967cd378cc051`, checkout inicialmente limpo.
O arquivo completo indicado na máquina do Checker não foi acessado.

O parecer aprovou B6 somente nos cenários revisados e levantou três achados
médios novos. Todos procedem. O responsável autorizou explicitamente commit,
merge, deploy e alterações de VPS/Dokploy; decisão registrada em `AGENTS.md`.
Não é necessário repetir essa autorização. Ela não substitui aceite técnico
nem amplia permissões efetivas da conexão GitHub.

## Correções e provas

| Achado | Correção | Verificação própria |
| --- | --- | --- |
| Limpeza apaga snapshot preexistente após falha de `O_EXCL` | Snapshot agora nasce em diretório único no `RUNNER_TEMP`. Caminho e identidade são exportados somente após criação; limpeza não usa fallback e verifica diretório, inode e proprietário. O workflow inicia o comprovante vazio, evitando herança de outro job. Não há remoção recursiva. | Falha de criação preserva arquivo preexistente; cleanup sem comprovante não o remove. Arquivo substituído é preservado. Falha na exportação remove só o artefato próprio. Teste positivo verifica 0600 e que o export não contém o segredo. |
| Rechecagem pós-deploy pode recriar tag ausente | Publicação inicial e verificação final são operações distintas. `verify_deployment_ref` usa caminho somente leitura; ausência/alvo divergente abortam sem push. | Simulação: primeira leitura encontra a tag; segunda leitura vazia gera erro e nenhum push adicional. |
| Falha entre `compose.update` e `compose.saveEnvironment` deixa configuração parcial | Registro protegido é criado antes das escritas, com configuração anterior/planejada e histórico de deployments. Falha mantém o registro e bloqueia nova promoção. `--reconcile` restaura somente configuração pré-disparo em estado reconhecido. | Testes cobrem save rejeitado e save aplicado antes do erro; restauração confirma estado anterior. Mudança externa, novo deployment ou pedido de deploy ambíguo são recusados sem escrita. Falha parcial da restauração mantém registro e permite retry. Registro preexistente e campos de recurso indevidos são recusados. |

## Reconciliação segura

O procedimento completo está em [G02.md](G02.md). Configurar
`DOKPLOY_RECOVERY_FILE` em armazenamento privado durável fora do checkout e
de `RUNNER_TEMP` no runner. O cliente recusa esses locais descartáveis no
Actions. O arquivo é 0600 e contém ambiente completo, inclusive segredos:
não versionar, imprimir, compartilhar no chat ou publicar como artifact.
O snapshot temporário é limpo; o registro de reconciliação nunca é limpo pelo
workflow em caso de falha.

Antes de solicitar deploy, o registro fica em fase `prepared`. Em falha de
configuração, serializar todos os escritores deste Compose e executar:

```sh
python3 scripts/deploy.py --reconcile
```

O comando exige mesmo projeto, recurso e origem administrativa, invariantes da
fonte intactos, mesma lista de deployments e apenas valores anteriores ou
planejados nos campos alterados. Restaura ambiente/metadados, verifica a leitura
final e só então remove seu registro. Não executa deploy, não publica tags,
não altera dados do banco e não é rollback da aplicação.

A fase `deployment_requested` é persistida antes da chamada de deploy.
Se o pedido falhar ou expirar, pode ter sido aceito; nessa fase o comando
recusa restauração automática da configuração, mesmo sem ID retornado.
Investigar estado, imagem e saúde pelo harness. Não apagar o registro apenas
para liberar novas promoções. A API não oferece CAS; edições administrativas
concorrentes precisam ser serializadas. Estes testes usam API simulada;
nenhuma reconciliação foi executada contra o recurso implantado nesta rodada.

## Validação e pendências

- **125 testes aprovados, nenhum pulado**, incluindo PostgreSQL 17 local
  exclusivo e descartável em tmpfs. Ruff, formatação, lock, exportação de
  dependências e actionlint aprovados. Aviso Starlette/httpx permanece.
- Consulta GitHub nesta rodada: `admin=false`, `maintain=false`, `push=true`;
  endpoint de rulesets retornou `[]`. A autorização humana não elimina essa
  limitação de acesso. O JSON proposto ainda depende de aplicação e comprovação
  por identidade administrativa apropriada.
- Snapshot autoritativo completo, runner e variáveis/secrets de CD ainda
  precisam de configuração/comprovação. O workflow requer também a variável
  de caminho durável para o registro de reconciliação.
- Nenhuma tag, ruleset, aplicação ou configuração de VPS foi alterada nesta
  rodada. A publicação de código em `main` não comprova implantação.
- O deploy conhecido continua `bbb9a698ca4c274e43d18f133a08039c28f0ca4a`;
  leitura remota nesta rodada confirmou `/health` HTTP 200 com esse SHA;
  nenhuma correção nova foi promovida sem os pré-requisitos técnicos.

As correções aguardam Checker independente. CD e aceite integral G02 continuam
não estabelecidos; G01 permanece `NOT_ESTABLISHED`.
