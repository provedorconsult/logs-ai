# Erros conhecidos de implantação e integração

| Sintoma | Causa observada | Correção e evidência exigida |
| --- | --- | --- |
| `duplicate owned prefix` sem regras da integração | Variável `prefix` colide com propriedade RouterOS em `where prefix=$prefix`. | Usar `rulePrefix`; comparar contagens literais por leitura. Não apagar regras para contornar o erro. |
| `action name can contain only letters and numbers` | Nome de ação com hífens. | `logsaiPrivate` ou outro alfanumérico; gerar instalação/reversão do mesmo perfil. Prefixos de mensagem podem ter hífens. |
| `received` sobe e `persisted` não | CEF nativo usa modelo CCR/CRS/RB em Device Product, não somente `RouterOS`, ou mensagem não suportada. | Conferir cabeçalho de forma sanitizada; fixtures de CEF nativo em `tests/test_mikrotik.py`. Não registrar mensagens/comandos brutos. |
| Login administrativo aparece como PPP | RouterOS acrescenta `: ` a prefixo já terminado em `: `. | Parser aceita ambos; PPP exige tópico PPP/PPPoE. Auditar registros anteriores, preservar originais e registrar reparos. |
| Import executado, zero eventos | Ação/regra/rota/src-address incorreta, suporte TCP/CEF ausente ou falta de eventos. | Ler ação, regra, origem real e receptor; criar eventos de teste e comprovar commit. Import bem-sucedido não é aceite. |
| Uma origem errada é rejeitada | NAT/rota mudou IP percebido ou allowlist não corresponde. | Conferir IP observado e perfil. Não trocar allowlist por wildcard/CIDR para fazer passar. |
| PASS aparente de release antiga | `/health` 200 sem SHA ou snapshot de outra implantação. | Conferir deployment, digest, label, headers e baseline de mesma revisão/processo. |
| Falha após salvar Compose, antes do env | Mutação parcial da configuração. | Snapshot completo e journal; comparar/reconciliar ambos antes de redeploy, preservando valores alheios. |
| Arquivo snapshot preexistente é apagado | Cleanup não comprova propriedade. | Exclusão somente por recibo de criação própria; nunca apagar somente pelo nome. |
| Tag some depois do deploy e é recriada | Rechecagem também fazia publicação. | Verificação pós-deploy somente leitura. Não contornar proteção de tag. |
| Proxy/TLS Git inesperados | Origem variante sem `.git`, proxy específico ou `GIT_SSL_NO_VERIFY`. | Origem canônica, proxy explícito e TLS obrigatório; manter testes de B6. |
| Senha do banco diverge após regerar pacote | PostgreSQL já inicializado não altera senha via env. | Preservar `.env` original e volume; rotação coordenada. Preparador nunca sobrescreve saída. |

## Diagnóstico mínimo

1. Conferir `/health` core/coletor e SHA, sem imprimir env.
2. Conferir `/metrics`: processo, origens e contadores após commit.
3. Conferir projeto, bindings privados, serviços, migrations/checksum e logs
   sanitizados. PostgreSQL deve estar saudável e dedicado ao projeto.
4. Ler logging do roteador com fingerprint conferido antes da autenticação.
   Usuário/senha só quando autorizados especificamente para esse roteador.
5. Pedir à equipe os eventos de teste do caso faltante. `/user` é conta
   administrativa; `/ppp secret` é cliente PPP local; perfis PPP não são alterados.
6. Diagnóstico passivo de tráfego só dentro do escopo autorizado, limitado à
   origem/porta/namespace necessários, com descarte de payload bruto e remoção
   de recurso/capability/credenciais temporários ao final. Não é requisito do
   caminho normal de instalação.

O histórico detalhado está em `audits/MIKROTIK-VALIDATION.md` e nos relatórios G02.
As evidências são observações por versão, não garantia sobre ambientes futuros.
