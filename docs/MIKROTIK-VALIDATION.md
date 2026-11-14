# Evidências da integração MikroTik

Data: 14/11/2026 UTC. Maker: Codex; revisão independente pendente.

## Implementação e testes

- 150 testes aprovados com PostgreSQL 17 descartável, incluindo persistência
  transacional de eventos TCP/CEF e legados, rejeição de origem não permitida,
  framing limitado, descarte de comandos/segredos e retry de falha do banco.
- Ruff e formatação aprovados. Um aviso de depreciação Starlette/httpx permanece.
- Monitor SSH valida a chave antes de autenticar; comandos são fixos e de leitura.
- Não há migration adicional nem alteração do core G02 ou do seu volume.

## Roteador observado

Após confirmação humana do fingerprint, autenticação SSH e consultas de leitura
confirmaram RouterOS 7.24.5, fuso America/Bahia e propriedades de logging TCP/CEF.
Na inspeção inicial, ação e regras desta integração ainda não existiam.
Não foram consultadas senhas PPP nem alterada configuração do roteador.
Contagens operacionais e credenciais não são publicadas neste relatório.

## Deploy e aceite

Deploy do coletor ainda pendente no momento deste commit de implementação.
O artefato raw Compose fixa o contexto de build no SHA completo, sem depender
de criação/recriação de tags. O CD anterior baseado em tags continua pendente;
esta entrega não comprova proteção administrativa de tags ou CD automático.

Aplicação dos scripts pela equipe de redes e recebimento real dos eventos
PPPoE/administrativos ainda pendentes. Testes sintéticos não comprovam esse
recebimento. Aceite independente permanece com Hermes e Devs Humanos.
