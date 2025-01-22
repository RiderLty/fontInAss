[ -f "/etc/nginx/conf.d/emby.conf.template" ] && python src/docker.init.py
command -v nginx >/dev/null 2>&1 && nginx && python src/main.py || python src/main.py