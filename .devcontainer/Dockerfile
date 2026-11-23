# Dev container for Job Finder — based on Anthropic's reference Claude Code dev container.
# Language toolchains are added later (devcontainer features or this file) once the stack is chosen.
FROM node:20

ARG TZ=Europe/Madrid
ENV TZ="$TZ"

ARG CLAUDE_CODE_VERSION=latest

# Base tools, firewall tools (iptables, ipset), Claude Code sandbox dependencies (bubblewrap, socat),
# Python for spike and helper scripts.
RUN apt-get update && apt-get install -y --no-install-recommends \
    less git procps sudo man-db unzip gnupg2 gh jq nano vim \
    iptables ipset iproute2 dnsutils aggregate curl ca-certificates \
    bubblewrap socat \
    python3 python3-pip python3-venv \
  && apt-get clean && rm -rf /var/lib/apt/lists/*

ARG USERNAME=node

# Global npm packages for the node user
RUN mkdir -p /usr/local/share/npm-global && chown -R node:node /usr/local/share

# Persistent shell history (volume mounted at /commandhistory)
RUN mkdir /commandhistory && touch /commandhistory/.bash_history && chown -R $USERNAME /commandhistory \
  && echo "export PROMPT_COMMAND='history -a' && export HISTFILE=/commandhistory/.bash_history" >> /home/node/.bashrc

# Claude Code config directory (volume mounted, keeps login and user settings between rebuilds)
RUN mkdir -p /home/node/.claude && chown -R node:node /home/node/.claude

ENV DEVCONTAINER=true

USER node
ENV NPM_CONFIG_PREFIX=/usr/local/share/npm-global
ENV PATH=$PATH:/usr/local/share/npm-global/bin
ENV EDITOR=nano
ENV VISUAL=nano

RUN npm install -g @anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}

# Egress firewall and container-level Claude Code settings
USER root
COPY init-firewall.sh allowed-domains.txt claude-settings.json /usr/local/share/devcontainer/
RUN chmod +x /usr/local/share/devcontainer/init-firewall.sh \
  && echo "node ALL=(root) NOPASSWD: /usr/local/share/devcontainer/init-firewall.sh" > /etc/sudoers.d/node-firewall \
  && chmod 0440 /etc/sudoers.d/node-firewall
USER node
