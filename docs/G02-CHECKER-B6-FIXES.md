# G02 — B6: origem Git efetiva e verificação TLS

Reavaliação posterior: B6 aprovado nos cenários específicos; novos achados de
CD tratados em [G02-CHECKER-CD-FIXES.md](G02-CHECKER-CD-FIXES.md).

Data: 13/11/2026 (America/Sao_Paulo). Base confrontada:
`de83b9547be37fa124fc060dac93e9da80badd9e`, igual a `origin/main`, checkout
inicialmente limpo. Fonte: reavaliação transcrita pelo responsável no chat;
o arquivo completo indicado na máquina do Checker não foi acessado.

As duas lacunas altas procedem. A revisão anterior rejeitou os negativos de
B1/B2/B3/B5, mas isso não aprovou B6, a configuração autoritativa de B4, G02 ou
G01. Esta correção é trabalho do Maker, pendente de nova revisão independente.

## Correções e provas próprias

| Lacuna | Causa no código anterior | Correção e validação |
| --- | --- | --- |
| Proxy da variante sem `.git` | Cliente aceitava duas grafias da origem, mas consultava a configuração efetiva somente para a variante `.git`. | Fetch e push agora precisam ser exatamente `https://github.com/provedorconsult/logs-ai.git`, sem variantes ou origens adicionais. O construtor de transporte também recebe a URL efetiva e consulta sua configuração. Testes recusam variantes em fetch/push antes de rede; proxy específico da URL sem sufixo é detectado e o listener local não recebe CONNECT. |
| `GIT_SSL_NO_VERIFY` herdado | A variável podia desativar validação TLS nos processos Git. | Sua presença é recusada antes de qualquer invocação Git, incluindo metadados locais. Verificação TLS é ligada explicitamente e a configuração efetiva por URL precisa confirmar `sslVerify=true`. Testes cobrem valores `1`, `true`, `0` e vazio, além de override específico que tenta desligar TLS. |

Prova TLS com Git real: servidor HTTPS somente em loopback, certificado
autoassinado e repositório sintético inexistente. Sem confiança na CA, Git
falhou por certificado e o servidor não recebeu requisição HTTP. Com a variável
proibida, o cliente recusou antes de iniciar Git. Como controle positivo, a CA
de teste foi explicitamente fornecida: TLS verificado alcançou HTTP, embora o
repositório intencionalmente retornasse 404. Não houve acesso ao GitHub nem uso
de credenciais reais nesses testes.

O job de deploy normaliza a origem local após checkout para manter o contrato
canônico, sem editar tags ou recursos remotos nessa etapa. A configuração de
autenticação e CA aprovada é preservada; não se usa TLS desativado como fallback.

## Resultados e limites

- **108 testes aprovados, nenhum pulado**, com PostgreSQL 17 local exclusivo
  em tmpfs, incluindo os novos negativos e o controle positivo TLS.
- Ruff, formatação, exportação das dependências e actionlint aprovados. O aviso
  de depreciação Starlette/httpx permanece.
- Consulta de rulesets via conector GitHub retornou `[]` novamente. O JSON
  proposto no repositório continua sendo proposta, sem aplicação comprovada.
- Leitura remota: `/health` HTTP 200, revisão
  `bbb9a698ca4c274e43d18f133a08039c28f0ca4a`. Isso não comprova deploy de
  `de83b95` nem destas correções.
- Nenhum novo deploy ou alteração de VPS, privilégios, SSH, Tailscale, firewall,
  MikroTik, tags ou rulesets foi realizado. As mudanças são no cliente de
  entrega, configuração do workflow, testes e documentação; não alteram app,
  Compose, Dockerfile ou migrations.

Proteção remota efetiva das tags ainda depende de administrador. O inventário
completo autoritativo de B4 ainda deve ser fornecido pelo armazenamento seguro
em `DOKPLOY_ENV_FILE`/`DOKPLOY_ENV_SNAPSHOT`; não se infere sua completude pela
resposta da API nem se pedem segredos no chat. O cliente mantém a recusa de
promoções sem esses requisitos. CD automática não foi habilitada. O aceite
independente e os estados integrais G02/G01 continuam não estabelecidos.
