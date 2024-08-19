FROM nginx
COPY main.py fontMap.json requirements.txt run.sh /
RUN apt update && apt install -y python3 python3-pip && pip install --break-system-packages -r ./requirements.txt && chmod 777 /run.sh
COPY nginx /etc/nginx
CMD ["/run.sh"]
