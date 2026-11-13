# G02 — Registro de validação do Maker

Data: 13/11/2026 (America/Sao_Paulo). Escopo: executor local desta implementação.
G02 permanece autorizada; este registro não constitui aceite independente.

| Verificação | Resultado observado |
| --- | --- |
| Ruff lint e formatação | Aprovados. |
| Dependências | Lock sincronizado e exportação de requirements conferida. |
| Testes com PostgreSQL real descartável | 17 aprovados, nenhum pulado. |
| Build Docker multi-stage | Concluído com CA de proxy montada como secret, sem desativar TLS. |
| Compose completo | PostgreSQL e aplicação saudáveis; aplicação sem privilégios e filesystem somente leitura. |
| Falha do banco | Banco parado localmente: `/health` retornou HTTP 503. |
| Retomada e volume | Contêineres removidos sem apagar volume e recriados; registro sintético preservado. |
| Migrations após recriação | Uma migration registrada, sem duplicação. |
| Readiness e revisão | HTTP 200 com app e banco saudáveis; `X-App-Revision=g02-local`. |

Os testes cobrem migration idempotente e concorrente, falha transacional sem
schema parcial, checksum alterado, incompatibilidade com release anterior,
restrição de severidade, persistência entre conexões, indisponibilidade do banco,
redação de erros e rejeição de transporte administrativo inadequado.
O TestClient emitiu um aviso de depreciação da combinação Starlette/httpx; os
testes completaram com sucesso. Não foi executado scanner completo de segredos;
foi feita revisão do diff e comparação dirigida com credenciais do ambiente.

## Limites e pendências remotas

Não houve deploy nem acesso à VPS ou ao MikroTik. O ambiente possui token
Dokploy, mas não fornece URL administrativa HTTPS validada, recurso Compose
identificado, `APP_TEST_URL` ou identidade SSH dedicada disponível para estabelecer
o túnel exigido. Não se tentou HTTP administrativo direto pela Tailnet nem
fallback para senha. A configuração foi solicitada ao responsável por canal
seguro; token/chave não devem ser enviados pelo chat.

O workflow de CI/CD foi incluído, mas sua execução no GitHub e o job de deploy
não foram comprovados neste registro. O deploy exige habilitação e configuração
explicadas em [G02.md](G02.md). Não há evidência remota de réplicas `1/1`,
`pg_isready`, readiness, persistência ou rollback da aplicação nesta entrega.
O ensaio local não comprova persistência após reboot da VPS, backup/restauração,
perímetro, carga ou prontidão de produção. Hermes e Devs Humanos ainda precisam
executar o aceite pós-deploy no servidor de testes.

```ini
G02_AUTHORIZED=YES
G02_LOCAL_IMPLEMENTATION=VERIFIED
G02_REMOTE_DEPLOY=BLOCKED_CONFIGURATION
G02_OVERALL=NOT_ESTABLISHED
G01_OVERALL=NOT_ESTABLISHED
CHECKER_INDEPENDENCE=NOT_ESTABLISHED
```
