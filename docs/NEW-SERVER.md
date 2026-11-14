# Novo servidor de logs com MikroTik

Este é o caminho reproduzível para **uma instalação nova**. Leia `AGENTS.md` e
[SKILLS.md](SKILLS.md). O estado de referência e as evidências históricas estão
em [MIKROTIK-VALIDATION.md](audits/MIKROTIK-VALIDATION.md); os IDs, IPs, tokens e exceções
daquele servidor não são defaults para novas instalações.

## Escolher o caminho

| Situação | Artefato |
| --- | --- |
| Servidor/projeto novo, sem banco logs-ai | `deploy/standalone.compose.yml`: PostgreSQL 17 + core + coletor. |
| Projeto logs-ai com banco dedicado já saudável | `deploy/mikrotik.compose.yml`: somente coletor, rede externa do banco existente. |
| Desenvolvimento local do core | `docker-compose.yml`. |

Não colocar o Compose completo sobre o banco existente. Não usar o PostgreSQL
administrativo do Dokploy nem recursos de outros projetos. O pacote novo usa
Docker Compose, em um único nó; um host Docker em Swarm não torna este artefato
um Docker Stack distribuído. O volume é local ao nó e deve permanecer no mesmo
nó nas atualizações.

## Inventário e acesso

Definir nome da instância, VPS/IP privado, IP administrativo ou túnel, portas
livres, uma a 32 origens IPv4 privadas de roteadores, versões e responsáveis.
Confirmar a rota privada até o receptor e a origem realmente observada, sobretudo
com NAT. Roteadores atrás do mesmo IP NAT não podem ser atribuídos separadamente
por este receptor. Sem TLS na coleta, IP/rede são a fronteira de confiança.

SSH da VPS: host key conferida, chave dedicada e BatchMode/IdentitiesOnly; sem
fallback de senha. Tailscale SSH permanece `RunSSH=false`. Transporte do runtime
pode exigir proxy TCP aprovado; não reconfigurar Tailscale para contornar rotas.
API Dokploy: HTTPS validado ou túnel SSH validado. Exceções humanas explícitas
valem somente no host/escopo autorizado; a autorização HTTP da implantação
histórica não é uma permissão global para novos hosts.

Para host sem Dokploy, seguir a skill `logs-ai-dokploy`. Isso instala Docker/Swarm
pelo procedimento oficial revisado, não executa migrations no banco administrativo.
O projeto instala seu próprio PostgreSQL no Compose abaixo.

## Preparar uma instalação

Requisitos do preparador/verificador: Python 3.12+, biblioteca padrão, checkout
confiável do repositório. Não precisam de uv nem de token para gerar arquivos.

```sh
mkdir -p work/installations
cp deploy/profiles/example.json work/site.json
# Editar work/site.json: endereços, portas, IDs e nomes de ação.
python3 scripts/prepare_installation.py \
  --profile work/site.json \
  --revision "$(git rev-parse HEAD)" \
  --output work/installations/site01
```

Usar SHA completo **publicado e com CI aprovada**, não código local ainda sem
commit. O preparador não faz deploy nem autentica em nenhum servidor.
`example.json` é exemplo privado fictício: substitua todos os endereços.
`health_bind=127.0.0.1` exige executar a validação na VPS ou por túnel validado.
Pode ser um IP privado ou Tailnet específico; nunca wildcard público.

O diretório é criado com modo 700, arquivos 600. Contém:

- `docker-compose.yml`: JSON válido como YAML, sem credenciais literais;
- `.env`: senha PostgreSQL hexadecimal aleatória e parâmetros da instância;
- `manifest.json`: revisão, URLs administrativas e casos exigidos por roteador;
- `routers/<id>/install-logging.rsc` e `remove-logging.rsc`: pares correspondentes.

A saída precisa ser nova. O preparador **recusa sobrescrever** um pacote: não
regenerar a senha de um volume já inicializado. Fazer backup seguro do `.env`;
não anexar ao chat, GitHub, relatório ou log. O perfil não aceita segredos nem
campos desconhecidos. Guardar perfis reais em `work/`, que é ignorado pelo Git.

O padrão requer autenticação PPPoE, desconexão, criação em `/ppp secret` e edição
em `/user` **em cada roteador**. Adaptar `required_event_kinds` no perfil conforme
o escopo real antes de gerar o manifesto. `ppp.user.updated` valida edição PPP;
`routeros.admin_user.updated` valida conta administrativa: não são equivalentes.

## Implantar pelo Dokploy

A skill `logs-ai-stack` contém o procedimento API. Em resumo:

1. Conferir OpenAPI da instância, identidade do projeto/ambiente, permissões e
   ausência de recurso concorrente. Criar recurso Compose dedicado, source raw.
2. Fornecer o Compose gerado e **o `.env` completo** ao armazenamento protegido
   do recurso novo. Não imprimir `compose.one.env` ou `docker.getConfig.Config.Env`.
3. Manter comando nativo vazio e autoDeploy desativado até estabelecer CD real.
   Registrar IDs efetivos, nome do projeto Docker e volume. Não inventar IDs.
4. Contexto Git fixa o SHA completo; `APP_REVISION` deve ter o mesmo valor.
   Correlacionar o pedido pelo deployment ID/título único, esperar `done`, ler
   o build e conferir label da imagem, digest e `/health` dos dois componentes.
5. PostgreSQL não publica porta. Core e coletor têm UID sem privilégios,
   filesystem somente leitura e limites; a recepção TCP publica somente no IP
   privado especificado. Confirmar bindings efetivos, não apenas o texto YAML.

Alternativa em host com Docker/Compose, dentro do mesmo escopo autorizado:

```sh
docker compose --env-file work/installations/site01/.env \
  -f work/installations/site01/docker-compose.yml up -d --build --wait
```

Não misturar gestão CLI e Dokploy sobre o mesmo projeto/volume sem plano explícito.
A senha em `.env` configura a inicialização do PostgreSQL; mudar o arquivo depois
não altera a senha no banco existente. Rotação requer procedimento coordenado.

## Aplicar no MikroTik e comprovar

RouterOS validado: **7.24.5**. Outras versões exigem conferir `remote-protocol=tcp`
e `remote-log-format=cef`; não presumir suporte nem fazer fallback silencioso UDP.
A equipe de redes recebe somente o par de scripts do **seu** roteador.
O agente permanece em leitura quando esse for o escopo autorizado.

Revisar os parâmetros no bloco `BEGIN CONFIG` de ambos os arquivos. Os templates
sem geração/adaptação recusam os placeholders `CHANGE_ME`; não importá-los diretamente. A ação usa
somente letras/números. Manter prefixos canônicos e não usar variável `prefix`
em filtros `where prefix=...`. O código inteiro fica em um bloco de escopo.
Consultar [RUNBOOK.md](RUNBOOK.md) para as falhas já reproduzidas.

Antes dos testes, salvar baseline. O transporte HTTP é explícito: `direct`
quando alcançável diretamente; em runtime com proxy usar `proxy` e a origem
aprovada em `DOKPLOY_APPROVED_PROXY`. Não desabilitar TLS ou host-key checking.

```sh
DOKPLOY_TRANSPORT=direct python3 scripts/verify_installation.py baseline \
  --manifest work/installations/site01/manifest.json --output work/baseline.json
```

Importar `install-logging.rsc` no RouterOS. Gerar em **contas de teste** os casos
escolhidos: login/desconexão PPPoE, criação/edição de `/ppp secret`, edição de
`/user`. Não desconectar clientes de produção. Então:

```sh
DOKPLOY_TRANSPORT=direct python3 scripts/verify_installation.py verify \
  --manifest work/installations/site01/manifest.json \
  --baseline work/baseline.json --output work/receipt.json
```

Somente PASS comprova eventos novos de cada tipo/origem desde o baseline, após
commit do banco, com mesma revisão/processo. Uma fonte não satisfaz outra.
Reinício exige novo baseline e repetição. O verificador não identifica a conta
de teste; correlacionar janela e sujeito por SQL somente leitura se necessário.
Não confundir contadores de eventos com sessões únicas: uma desconexão pode
produzir duas mensagens. Logs intermediários ignorados são contados, sem replay.
Registrar também deployment/digest, migration/checksum, consulta de banco,
logs sem erro e estado dos serviços. Aceite independente continua separado.

## Atualização e recuperação

Preservar nome do projeto Docker, volume, senha e rede. Antes de alterar,
registrar o ambiente completo protegido, artefato, SHA/digest saudável e backup.
Mudar somente os campos planejados, conferir configuração efetiva e guardar
journal durável de intenção/etapas; não sobrescrever env parcial. Em falha,
reconciliar recurso e ambiente com o snapshot; retorno HTTP aceito não é sucesso.

As migrations são transacionais, com advisory lock e checksum. Não editar SQL
aplicado nem fazer downgrade para código sem migrations já registradas. Voltar
imagem não desfaz schema. Nunca executar `down -v` em dados a preservar.
Rollback do roteador: usar o `remove-logging.rsc` gerado no **mesmo pacote**;
o agente não aplica alterações se o escopo for somente leitura.

O CD antigo baseado em tags permanece sujeito aos seus gates (proteção de tags,
runner, snapshot autoritativo e configuração). A implantação raw fixada em SHA é
outro caminho rastreável; não declarar CD ativa porque existe YAML ou GitHub
integrado. Habilitação exige execução observada e recuperação validada.

## Evidências desta padronização

Ver [NEW-SERVER-VALIDATION.md](audits/NEW-SERVER-VALIDATION.md) para testes observados,
limitações e distinção entre validação local, sintaxe RouterOS e instalação real.
