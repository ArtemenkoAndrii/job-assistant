# Dev container for Job Finder — based on Anthropic's reference Claude Code dev container.
# Python toolchain per ADR-0005: uv installs Python 3.14 at build time (before the firewall exists).
FROM node:20

ARG TZ=Europe/Madrid
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# Base tools, firewall tools (iptables, ipset), Claude Code sandbox dependencies (bubblewrap, socat),
# Python for spike and helper scripts.
RUN apt-get update && apt-get install -y --no-install-recommends \
    less git procps sudo man-db unzip gnupg2 jq nano vim \
    iptables ipset iproute2 dnsutils aggregate curl ca-certificates \
    bubblewrap socat shellcheck \
    python3 python3-pip python3-venv \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# GitHub CLI from GitHub's own apt repository: Debian's gh is too old
# (`gh issue view` fails on the removed Projects (classic) field).
RUN mkdir -p -m 755 /etc/apt/keyrings \
  && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list \
  && apt-get update && apt-get install -y --no-install-recommends gh \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG USERNAME=node

# Global npm packages for the node user
RUN mkdir -p /usr/local/share/npm-global && chown -R node:node /usr/local/share

# Persistent shell history (volume mounted at /commandhistory)
RUN mkdir /commandhistory && touch /commandhistory/.bash_history && chown -R $USERNAME /commandhistory \
  && echo "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" >> /home/node/.bashrc

# Claude Code config directory (volume mounted, keeps login and user settings between rebuilds)
RUN mkdir -p /home/node/.claude && chown -R node:node /home/node/.claude

# GitHub CLI config directory (volume mounted, keeps the agent's fine-grained token between rebuilds)
RUN mkdir -p /home/node/.config/gh && chown -R node:node /home/node/.config

# WeasyPrint system libraries (PDF rendering, ADR-0005)
RUN apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

# uv (pinned) for the node user; Python 3.14 is installed by uv below
ARG UV_VERSION=0.13.9
RUN python3 -m pip install --no-cache-dir --break-system-packages "uv==${UV_VERSION}"

# Secret scanner for the pre-commit hook and scripts/lint.sh; same version as CI
ARG GITLEAKS_VERSION=8.21.2
COPY install-gitleaks.sh /tmp/install-gitleaks.sh
RUN GITLEAKS_VERSION=$GITLEAKS_VERSION bash /tmp/install-gitleaks.sh /usr/local/bin && rm /tmp/install-gitleaks.sh

# Terraform for infra/ (ADR-0009): fmt and validate without waiting for CI. Keep equal to infra/.terraform-version
# (scripts/check_infra.py fails if they differ). Needs registry.terraform.io at run time for `init`.
ARG TERRAFORM_VERSION=1.17.2
COPY install-terraform.sh /tmp/install-terraform.sh
RUN TERRAFORM_VERSION=$TERRAFORM_VERSION bash /tmp/install-terraform.sh /usr/local/bin && rm /tmp/install-terraform.sh

ENV DEVCONTAINER=true

USER node
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin
ENV EDITOR=nano
ENV VISUAL=nano

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Python 3.14 managed by uv; at run time uv must not download interpreters (firewall)
# Keep equal to apps/jobfinder/.python-version
ARG PYTHON_VERSION=3.14.6
RUN uv python install ${PYTHON_VERSION}
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy

# Some runtimes (e.g. rootless Podman) hand the capabilities added for the firewall (NET_ADMIN, NET_RAW)
# to the non-root user as ambient capabilities. bubblewrap then refuses to start ("Unexpected capabilities
# but not setuid") and the Claude Code sandbox fails. This wrapper, first in PATH, starts Claude Code with
# all inheritable and ambient capabilities dropped. The firewall still runs as root via sudo.
USER root
RUN printf '%s\n' '#!/bin/sh' \
      'exec setpriv --inh-caps=-all --ambient-caps=-all -- /usr/local/share/npm-global/bin/claude "$@"' \
      > /usr/local/bin/claude \
  && chmod 755 /usr/local/bin/claude
USER node

# Egress firewall and container-level Claude Code settings
USER root
COPY init-firewall.sh allowed-domains.txt claude-settings.json /usr/local/share/devcontainer/
RUN chmod +x /usr/local/share/devcontainer/init-firewall.sh \
  && echo "node ALL=(root) NOPASSWD: /usr/local/share/devcontainer/init-firewall.sh" > /etc/sudoers.d/node-firewall \
  && chmod 0440 /etc/sudoers.d/node-firewall
USER node
