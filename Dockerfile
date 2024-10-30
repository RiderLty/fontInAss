FROM python:3.10-slim-buster 
COPY fontMap.json localFontMap.json requirements.txt run.sh /
RUN chmod 777 /run.sh && apt-get update && apt-get install nginx gcc build-essential -y && pip install -r ./requirements.txt
COPY src /src
COPY nginx /etc/nginx
CMD ["/bin/sh" , "-c" , "/run.sh"]
