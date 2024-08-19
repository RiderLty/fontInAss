FROM python:3.10-slim-buster 
COPY main.py fontMap.json requirements.txt run.sh /
RUN pip install -r ./requirements.txt && apt-get update && apt-get install -y nginx && chmod 777 /run.sh
COPY nginx /etc/nginx
CMD ["/run.sh"]