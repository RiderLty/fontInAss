FROM python:3.10-slim-buster 
COPY main.py fontMap.json requirements.txt run.sh /
RUN chmod 777 /run.sh & pip install -r ./requirements.txt  && apt-get update && apt-get install nginx -y
COPY nginx /etc/nginx
CMD ["/bin/sh" , "-c" , "/run.sh"]
