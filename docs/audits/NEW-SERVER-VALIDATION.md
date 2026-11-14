# Evidências da padronização para novas instalações

Data: 13/11/2026, fuso America/Sao_Paulo. Maker: Codex.
Esta rodada publica ferramentas/skills; não implanta uma nova VPS nem atualiza
o serviço histórico `827fa14` automaticamente.

## Verificado

- 191 testes aprovados com PostgreSQL 17 descartável: guards anteriores de CD,
  parser RouterOS, TCP/DB, múltiplas origens com retry sem troca de atribuição,
  geração privada/exclusiva e recusa de nomes inválidos, injeção e binds públicos.
- Ruff, formatação, lock/export de requirements e Actionlint aprovados.
- Seis skills com frontmatter e links locais conferidos; perfis e Compose JSON
  sintaticamente válidos como dados/YAML.
- `:parse` de instalação/reversão aceito pelo RouterOS 7.24.5 por SSH com chave
  do host já confirmada, sem chamar a função compilada ou aplicar configuração.
  Tipo de `topics` confirmado como array, para comparação independente de ordem.
- Build Docker local concluído com CA como secret e proxy aprovado. Uma primeira
  tentativa falhou ao resolver o proxy dentro do build; a repetição mapeou somente
  o nome do proxy para seu endereço resolvido no build, sem desabilitar TLS/proxy.

## Pacote completo em Docker descartável

Com o mesmo template `standalone.compose.yml`, imagem do código local com revisão
sintética de teste e rede Docker isolada, foram gerados dois roteadores fictícios:

1. Core, coletor e PostgreSQL ficaram saudáveis, com banco sem porta publicada.
2. Baseline salvo antes da emissão de mensagens. Cada origem enviou CEF nativo
   com produto de hardware e separador adicional, cobrindo autenticação PPPoE,
   término de sessão, criação PPP e atualização de conta administrativa.
3. Verificador retornou PASS em oito verificações (quatro tipos por origem).
   Consulta PostgreSQL confirmou quatro registros em cada fonte correta; zero
   atributos continham o segredo sintético colocado na mensagem bruta.
4. Dado marcador permaneceu após `--force-recreate` dos contêineres sem remover
   volume. O baseline anterior foi rejeitado pelo novo ID de processo.
5. Stack, rede, volume e diagnósticos temporários próprios foram removidos.

As adaptações do smoke foram somente de teste: bind em loopback, portas próprias,
IPAM isolado e imagem já construída localmente. O perfil de produção continua
com receptor em IP privado explícito e contexto Git fixado no SHA completo.
A CI foi ampliada para gerar pacote privado e conferir readiness da instalação
completa usando a imagem construída para o SHA do job; não confundir esse smoke
com eventos reais de um novo roteador.

## Limites e aceite

Não foi instalado Dokploy em uma VPS nova nesta rodada. O download público de
`dokploy.com/install.sh` retornou 403 no executor; a skill instrui consultar a
fonte oficial e revisar o instalador efetivamente disponível no destino. Não se
executou instalador alternativo, nem se presumiu flag de seleção de versão.

Os scripts padronizados foram compilados pelo parser, não importados como nova
configuração no roteador de referência. A evidência funcional real da versão
histórica está em `MIKROTIK-VALIDATION.md`. Instalações futuras precisam de
comissionamento real por origem, backup/restauração e inventário do seu destino.
A fila permanece em memória e syslog não confirma transação por evento.
Skills são instruções, não autorização global, independência de Checker ou
aprovação integral de gates/CD.


## Compatibilidade de configuração do coletor anexado

Uma verificação adicional com o CLI real do Compose identificou avaliação
antecipada de fallback obrigatório aninhado: a configuração plural exigia
indevidamente a variável singular. Os dois campos agora têm defaults separados;
o runtime exige ao menos uma allowlist. Dois testes de regressão executam o
interpolador real nos modos singular/plural. O relatório estrutural publicado
em paralelo pelo Auditor Gemini foi integrado sem alteração do seu conteúdo.

## CI publicada

Código publicado em `8ae6720` e correção de compatibilidade em
`e280edc1e5d536dd99508cfb6d03bac684375caa`, preservando o relatório estrutural
remoto `32c091d`. A CI [43549640791](https://github.com/provedorconsult/logs-ai/actions/runs/43549640791)
concluiu `verify=success`, incluindo build e readiness do pacote completo;
`deploy=skipped`. A interface CLI documentada também gerou um pacote novo e
passou no `docker compose config --quiet`; a prévia privada foi removida.
Essa execução comprova checks de código/pacote, não bootstrap de outra VPS nem
comissionamento de roteadores que ainda não foram conectados.
