#!/bin/bash
# Default-deny egress firewall for the dev container.
# Adapted from Anthropic's reference Claude Code dev container (anthropics/claude-code/.devcontainer).
# Allowed: DNS, SSH, localhost, the Docker host network, GitHub (from api.github.com/meta)
# and the domains in allowed-domains.txt. Everything else is rejected.
set -euo pipefail
IFS=$'\n\t'

DOMAINS_FILE="/usr/local/share/devcontainer/allowed-domains.txt"

# 1. Keep Docker's internal DNS rules before flushing
DOCKER_DNS_RULES=$(iptables-save -t nat | grep "127\.0\.0\.11" || true)

iptables -F; iptables -X
iptables -t nat -F; iptables -t nat -X
iptables -t mangle -F; iptables -t mangle -X
ipset destroy allowed-domains 2>/dev/null || true

if [ -n "$DOCKER_DNS_RULES" ]; then
  iptables -t nat -N DOCKER_OUTPUT 2>/dev/null || true
  iptables -t nat -N DOCKER_POSTROUTING 2>/dev/null || true
  echo "$DOCKER_DNS_RULES" | xargs -L 1 iptables -t nat
fi

# 2. DNS, SSH and localhost
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A INPUT -p udp --sport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 22 -j ACCEPT
iptables -A INPUT -p tcp --sport 22 -m state --state ESTABLISHED -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

ipset create allowed-domains hash:net

# 3. GitHub ranges
echo "Fetching GitHub IP ranges..."
gh_ranges=$(curl -s --connect-timeout 10 https://api.github.com/meta)
if ! echo "$gh_ranges" | jq -e '.web and .api and .git' >/dev/null; then
  echo "ERROR: could not read GitHub IP ranges" >&2
  exit 1
fi
while read -r cidr; do
  [[ "$cidr" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}/[0-9]{1,2}$ ]] || { echo "ERROR: bad CIDR $cidr" >&2; exit 1; }
  ipset add allowed-domains "$cidr" -exist
done < <(echo "$gh_ranges" | jq -r '(.web + .api + .git)[]' | grep -v ':' | aggregate -q)

# 4. Allowed domains (resolved once at start; restart the container if a service changes IPs)
resolved=0
while read -r domain; do
  domain="${domain%%#*}"; domain="$(echo "$domain" | tr -d '[:space:]')"
  [ -z "$domain" ] && continue
  ips=$(dig +noall +answer A "$domain" | awk '$4 == "A" {print $5}')
  if [ -z "$ips" ]; then
    echo "WARNING: could not resolve $domain — skipped" >&2
    continue
  fi
  while read -r ip; do
    [[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || { echo "ERROR: bad IP $ip for $domain" >&2; exit 1; }
    ipset add allowed-domains "$ip" -exist
  done < <(echo "$ips")
  resolved=$((resolved + 1))
done < "$DOMAINS_FILE"
if [ "$resolved" -eq 0 ]; then
  echo "ERROR: no allowed domain could be resolved" >&2
  exit 1
fi

# 5. Docker host network (IDE connection)
HOST_IP=$(ip route | grep default | cut -d" " -f3)
[ -n "$HOST_IP" ] || { echo "ERROR: could not detect host IP" >&2; exit 1; }
HOST_NETWORK=$(echo "$HOST_IP" | sed "s/\.[0-9]*$/.0\/24/")
iptables -A INPUT -s "$HOST_NETWORK" -j ACCEPT
iptables -A OUTPUT -d "$HOST_NETWORK" -j ACCEPT

# 6. Default deny
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT DROP
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT
iptables -A OUTPUT -j REJECT --reject-with icmp-admin-prohibited

# 7. Verify
if curl --connect-timeout 5 -s https://example.com >/dev/null 2>&1; then
  echo "ERROR: firewall check failed — example.com is reachable" >&2
  exit 1
fi
if ! curl --connect-timeout 5 -s https://api.github.com/zen >/dev/null 2>&1; then
  echo "ERROR: firewall check failed — api.github.com is not reachable" >&2
  exit 1
fi
echo "Firewall ready: default deny, $resolved allowed domains + GitHub"
