# Single block keeps local variables in scope during RouterOS import.
{
# RouterOS 7.24.5. Apply by the network team, after checking the receiver health.
# Sends native CEF over TCP on the private network. No PPP profiles/users are changed.
# Do not enable debug/packet logging: only the requested informational events are selected.
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
        :local actualTopics [/system logging get $ruleId topics]
        :local expectedTopics {"ppp";"info"}
        :if ($rulePrefix = $adminPrefix) do={ :set expectedTopics {"system";"info";"!ppp"} }
        :if ([:len $actualTopics] != [:len $expectedTopics]) do={
            :error "logs-ai: existing rule topics differ; inspect manually"
        }
        :foreach requiredTopic in=$expectedTopics do={
            :local topicFound false
            :foreach actualTopic in=$actualTopics do={
                :if ($actualTopic = $requiredTopic) do={ :set topicFound true }
            }
            :if ($topicFound = false) do={ :error "logs-ai: existing rule topics differ; inspect manually" }
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
