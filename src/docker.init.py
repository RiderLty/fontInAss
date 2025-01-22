import os

EMBY_SERVER_URL = os.environ.get("EMBY_SERVER_URL", default="尚未EMBY_SERVER_URL环境变量")
EMBY_WEB_EMBED_FONT = os.environ.get("EMBY_WEB_EMBED_FONT", default="True") == "True"
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

with open(r"/etc/nginx/conf.d/emby.conf", "w", encoding="UTF-8") as f:
    f.write(config)

os.remove(r"/etc/nginx/conf.d/emby.conf.template")