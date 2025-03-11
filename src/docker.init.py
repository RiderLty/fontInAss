import os

EMBY_SERVER_URL = os.environ.get("EMBY_SERVER_URL", default="尚未EMBY_SERVER_URL环境变量")
EMBY_WEB_EMBED_FONT = os.environ.get("EMBY_WEB_EMBED_FONT", default="True") == "True"
NGINX_GZIP_COMP_LEVEL = os.environ.get("NGINX_GZIP_COMP_LEVEL", default="1")
NGINX_GZIP = NGINX_GZIP_COMP_LEVEL in [str(i) for i in range(1,10)]


print("初始化")
print("EMBY_SERVER_URL = ",EMBY_SERVER_URL)
print("EMBY_WEB_EMBED_FONT = ",EMBY_WEB_EMBED_FONT)
with open(r"/etc/nginx/conf.d/emby.conf.template", "r", encoding="UTF-8") as f:
    config = f.read()

config = config.replace("$EMBY_SERVER_URL", EMBY_SERVER_URL)

if EMBY_WEB_EMBED_FONT:
    config = config.replace("$EMBY_WEB_EMBED_FONT" , "http://127.0.0.1:8011")
else:
    config = config.replace("$EMBY_WEB_EMBED_FONT" , EMBY_SERVER_URL)

if NGINX_GZIP:
    config = config.replace("$NGINX_GZIP_COMP_LEVEL" , NGINX_GZIP_COMP_LEVEL)
    config = config.replace("$NGINX_GZIP" , "on")
    print("开启GZIP，COMP_LEVEL=",NGINX_GZIP_COMP_LEVEL)
else:
    config = config.replace("$NGINX_GZIP" , "off")

with open(r"/etc/nginx/conf.d/emby.conf", "w", encoding="UTF-8") as f:
    f.write(config)


print(r"/etc/nginx/conf.d/emby.conf")
print(config)

os.remove(r"/etc/nginx/conf.d/emby.conf.template")