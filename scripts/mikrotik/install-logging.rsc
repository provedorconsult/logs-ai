# Single block keeps local variables in scope during RouterOS import.
{
# RouterOS 7.24.5. Apply by the network team, after checking the receiver health.
# Sends native CEF over TCP on the private network. No PPP profiles/users are changed.
# Do not enable debug/packet logging: only the requested informational events are selected.
:local destination "192.168.15.25"
:local source "192.168.15.1"
:local port 5514
:local actionName "logs-ai-private"
:local pppPrefix "logs-ai-ppp: "
:local adminPrefix "logs-ai-admin: "

:local actionIds [/system logging action find where name=$actionName]
:if ([:len $actionIds] > 1) do={ :error "logs-ai: ambiguous logging action; inspect manually" }
:if ([:len $actionIds] = 1) do={
    :local actionId [:pick $actionIds 0]
    :if (([/system logging action get $actionId target] != "remote") || \
         ([:tostr [/system logging action get $actionId remote]] != $destination) || \
         ([/system logging action get $actionId remote-port] != $port) || \
         ([:tostr [/system logging action get $actionId src-address]] != $source) || \
         ([/system logging action get $actionId remote-protocol] != "tcp") || \
         ([/system logging action get $actionId remote-log-format] != "cef")) do={
        :error "logs-ai: existing action differs; no settings were overwritten"
    }
}

# Validate collisions before adding anything. Existing rules/actions are preserved.
:foreach rulePrefix in={"logs-ai-ppp: ";"logs-ai-admin: "} do={
    :local rules [/system logging find where prefix=$rulePrefix]
    :if ([:len $rules] > 1) do={ :error "logs-ai: duplicate owned prefix; inspect manually" }
    :if ([:len $rules] = 1) do={
        :local ruleId [:pick $rules 0]
        :if ([/system logging get $ruleId disabled] = true) do={
            :error "logs-ai: existing integration rule is disabled; inspect manually"
        }
        :if ([/system logging get $ruleId action] != $actionName) do={
            :error "logs-ai: prefix is used by another action; no settings were overwritten"
        }
        :local topics [:tostr [/system logging get $ruleId topics]]
        :if (($rulePrefix = $pppPrefix) && ($topics != "ppp,info") && ($topics != "ppp;info")) do={
            :error "logs-ai: existing PPP rule differs; inspect manually"
        }
        :if (($rulePrefix = $adminPrefix) && ($topics != "system,info,!ppp") && \
             ($topics != "system;info;!ppp")) do={
            :error "logs-ai: existing administrative rule differs; inspect manually"
        }
    }
}

:if ([:len $actionIds] = 0) do={
    /system logging action add name=$actionName target=remote remote=$destination \
        remote-port=$port src-address=$source remote-protocol=tcp remote-log-format=cef \
        syslog-facility=local0 syslog-severity=auto
}
:if ([:len [/system logging find where prefix=$pppPrefix]] = 0) do={
    /system logging add topics=ppp,info action=$actionName prefix=$pppPrefix
}
:if ([:len [/system logging find where prefix=$adminPrefix]] = 0) do={
    /system logging add topics=system,info,!ppp action=$actionName prefix=$adminPrefix
}
:put "logs-ai: private TCP/CEF forwarding configured; verify persisted events at the receiver"
}
