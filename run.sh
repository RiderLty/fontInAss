[ -f "/etc/nginx/conf.d/emby.conf.template" ] && uv run src/docker.init.py
command -v nginx >/dev/null 2>&1 && nginx && uv run src/main.py || uv run src/main.py
