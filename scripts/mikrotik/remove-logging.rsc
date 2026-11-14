# Single block keeps local variables in scope during RouterOS import.
{
# Network team rollback: removes only this integration's matching rules/action.
:local actionName "logs-ai-private"
:local pppPrefix "logs-ai-ppp: "
:local adminPrefix "logs-ai-admin: "
:local actions [/system logging action find where name=$actionName]
:if ([:len $actions] > 1) do={ :error "logs-ai: ambiguous action; inspect manually" }
:if ([:len $actions] = 1) do={
    :local actionId [:pick $actions 0]
    :if (([/system logging action get $actionId target] != "remote") || \
         ([:tostr [/system logging action get $actionId remote]] != "192.168.15.25") || \
         ([/system logging action get $actionId remote-port] != 5514) || \
         ([:tostr [/system logging action get $actionId src-address]] != "192.168.15.1") || \
         ([/system logging action get $actionId remote-protocol] != "tcp") || \
         ([/system logging action get $actionId remote-log-format] != "cef")) do={
        :error "logs-ai: action differs; refusing removal"
    }
}
:foreach prefix in={"logs-ai-ppp: ";"logs-ai-admin: "} do={
    :foreach rule in=[/system logging find where prefix=$prefix] do={
        :if ([/system logging get $rule action] != $actionName) do={
            :error "logs-ai: prefix belongs to another action; refusing removal"
        }
    }
}
:foreach prefix in={"logs-ai-ppp: ";"logs-ai-admin: "} do={
    :foreach rule in=[/system logging find where prefix=$prefix] do={ /system logging remove $rule }
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
