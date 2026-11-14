# Single block keeps local variables in scope during RouterOS import.
{
# Network team rollback: removes only this integration's matching rules/action.
# BEGIN CONFIG - adapt these values, or generate from deploy/profiles/example.json.
:local destination "CHANGE_ME_RECEIVER_IP"
:local source "CHANGE_ME_ROUTER_IP"
:local port 5514
:local actionName "logsaiPrivate"
:local pppPrefix "logs-ai-ppp: "
:local adminPrefix "logs-ai-admin: "
# END CONFIG - keep prefixes unchanged: they are part of the parser contract.

:if (([:typeof [:toip $destination]] != "ip") || ([:typeof [:toip $source]] != "ip")) do={
    :error "logs-ai: configure destination/source IPv4 addresses before import"
}
:if (([:len $actionName] = 0) || ([:len $actionName] > 32) || \
     ($actionName ~ "[^a-zA-Z0-9]")) do={
    :error "logs-ai: actionName must contain only letters/numbers, maximum 32"
}
:if (($port < 1) || ($port > 65535)) do={ :error "logs-ai: invalid TCP port" }
:local actions [/system logging action find where name=$actionName]
:if ([:len $actions] > 1) do={ :error "logs-ai: ambiguous action; inspect manually" }
:if ([:len $actions] = 1) do={
    :local actionId [:pick $actions 0]
    :if (([/system logging action get $actionId target] != "remote") || \
         ([:tostr [/system logging action get $actionId remote]] != $destination) || \
         ([/system logging action get $actionId remote-port] != $port) || \
         ([:tostr [/system logging action get $actionId src-address]] != $source) || \
         ([/system logging action get $actionId remote-protocol] != "tcp") || \
         ([/system logging action get $actionId remote-log-format] != "cef")) do={
        :error "logs-ai: action differs; refusing removal"
    }
}
:foreach rulePrefix in={"logs-ai-ppp: ";"logs-ai-admin: "} do={
    :foreach rule in=[/system logging find where prefix=$rulePrefix] do={
        :if ([/system logging get $rule action] != $actionName) do={
            :error "logs-ai: prefix belongs to another action; refusing removal"
        }
    }
}
:foreach rulePrefix in={"logs-ai-ppp: ";"logs-ai-admin: "} do={
    :foreach rule in=[/system logging find where prefix=$rulePrefix] do={ /system logging remove $rule }
}
:if ([:len $actions] = 1) do={
    :if ([:len [/system logging find where action=$actionName]] = 0) do={
        /system logging action remove [:pick $actions 0]
    } else={
        :put "logs-ai: integration rules removed; action retained because other rules still reference it"
    }
}
:put "logs-ai: removal completed; PPP profiles and users were preserved"
}
