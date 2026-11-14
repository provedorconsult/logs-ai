# G01 — Debian 13: evidências e validação pendente

## Sistema e origem da evidência

A documentação adota Debian 13. O anexo fornecido como
`G01-DEBIAN12-DOKPLOY-TAILSCALE-SSH.md` tem nome histórico: seu conteúdo registra
Debian 13. O nome não constitui evidência de Debian 12 em execução.
Esta consolidação documental de 13/11/2026 não realizou novas consultas à VPS
ou ao MikroTik e não publica o anexo integral, credenciais ou caminhos de chaves.

## Resultados registrados pelo Maker no anexo

- Nova conexão SSH pela Tailnet com identidade fixada, autenticação por chave
  e comando remoto com saída zero; leitura de `RunSSH=false` e `WantRunning=true`.
- Administração por sudo funcionou com senha; isso não comprova automação
  administrativa integral por chave e token.
- Docker respondeu, Swarm estava ativo e Compose retornou sua versão.
- Dokploy apresentava réplica `1/1` e HTTP local 200; PostgreSQL estava `1/1`.
  Volumes estavam listados, sem comprovação de persistência ou recuperação.
- Houve consulta de regras MikroTik e tentativas públicas recusadas após remoção
  de origem informada pelo operador. A recusa não identifica a regra responsável.

São resultados históricos relatados, não testes reproduzidos nesta revisão.
Não foram fornecidas transcrições completas para reprodução de todos os testes.

## Confirmações do operador

A ordem final das regras IPv4, desativação de regras de desbloqueio, alinhamento
IPv6, suficiência do firewall, acesso ao painel e disponibilidade de recuperação
via Proxmox foram informados pelo operador. O teste final a partir do ambiente
Codex também foi confirmado pelo operador, sem comando e código de saída exatos.
Essas confirmações não equivalem a testes independentes dos controles.

## Próxima etapa: preparar G01_FINAL_VALIDATION

Antes de qualquer alteração remota, apresentar plano concreto e obter aprovação
conforme [AGENTS.md](../../AGENTS.md). A sequência proposta para esse plano é:

1. Validar transporte administrativo por túnel SSH ou HTTPS validado, operação
   autenticada do Dokploy e saúde/autenticação do PostgreSQL.
2. Executar um projeto Compose controlado e registrar seus resultados.
3. Conferir configuração vigente e novas conexões autorizadas/não autorizadas,
   incluindo porta 3000 e IPv6, sem inferir proteção apenas de uma recusa TCP.
4. Demonstrar backup, restauração, rollback e persistência após reinício controlado,
   com acesso alternativo de recuperação previamente validado.
5. Confirmar tratamento da exposição anterior de senha e estado atual da
   autenticação SSH; submeter evidências sanitizadas a Checker independente.

A ordem de execução final deve respeitar dependências, riscos e escopo aprovado;
esta lista não autoriza reinícios, mudanças de firewall ou restaurações.
Consultar também [HARNESS.md](../HARNESS.md).

## Atualização de governança — 13/11/2026

Após este parecer, o responsável declarou “G02 autorizada”. A decisão humana
prevalece sobre o bloqueio anterior e permite avançar G02 com as pendências de
G01 ainda abertas. Não altera os resultados históricos nem estabelece aprovação
integral da G01. O estado abaixo foi atualizado para refletir essa autorização;
a validação final de G01 permanece necessária em paralelo.

## Parecer e limites

Os registros sustentam a correção pontual de SSH relatada, mas não estabelecem
prontidão integral da infraestrutura. Aceitações de risco e dispensas não
transformam controles não testados em resultados aprovados. A revisão foi feita
por agente que atuou como Maker nesta conversa e não substitui Checker independente.

```ini
REVIEW_TYPE=DOCUMENTARY_ONLY
CHECKER_INDEPENDENCE=NOT_ESTABLISHED
G01_FIX=PASS_REPORTED
G01_OVERALL=NOT_ESTABLISHED
G02_AUTHORIZED=YES
NEXT_ACTION=G02_AUTHORIZED_WITH_G01_VALIDATION_PENDING
```
