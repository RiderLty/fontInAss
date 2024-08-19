if [ ! -f ./configure_nginx ]; then \
    cat /etc/nginx/conf.d/emby.conf.template | envsubst > /etc/nginx/conf.d/emby.conf 
    cat /etc/nginx/conf.d/emby.js.template | envsubst > /etc/nginx/conf.d/emby.js 
    touch ./configure_nginx
fi
nginx && python3 main.py