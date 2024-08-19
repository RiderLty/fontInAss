if [ ! -f ./configure_nginx ]; then \
    find /etc/nginx -name "*.template" -exec sh -c 'envsubst < "$0" > "${0%.template} "' {} \; && touch ./configure_nginx
fi
nginx && python3 main.py