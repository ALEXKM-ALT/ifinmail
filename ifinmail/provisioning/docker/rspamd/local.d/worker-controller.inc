# Rspamd controller (web UI) — bound to localhost only, security
bind_socket = "127.0.0.1:11334";
secure_ip = "127.0.0.1";
password = "$2$..."  # Generate with: rspamadm pw; replace with actual hash
