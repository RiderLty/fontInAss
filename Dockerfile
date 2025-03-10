FROM riderlty/fontinass-builder:latest AS cache
FROM python:3.10-slim-bookworm
ARG NGINX=YES
COPY onlineFonts.json run.sh requirements.txt /
COPY nginx /etc/nginx
COPY src /src/
COPY --from=cache /wheels /wheels
COPY --from=cache /app/src/py2cy/* /app/src/py2cy/
RUN chmod 777 /run.sh && pip install --no-cache --find-links /wheels -r /requirements.txt  && rm -rf /wheels && mkdir /data
RUN if [ "${NGINX}" = "YES" ]; then apt-get update && apt-get -y --no-install-recommends install nginx; fi
CMD ["/bin/sh" , "-c" , "/run.sh"]