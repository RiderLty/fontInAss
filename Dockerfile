ARG BUILDER=riderlty/fontinass-builder:4ab13f154a5064f35f0900dacdb1ac50343c6c5db7fbfaf28e68eadaf74f47c0
FROM ${BUILDER} AS builder
FROM python:3.10-slim-buster 
COPY --from=builder /wheels /wheels
COPY fontMap.json run.sh /
RUN pip install --no-cache /wheels/* && rm -rf /wheels && chmod 777 /run.sh
ARG NGINX=YES
RUN if [ "${NGINX}" = "YES" ]; then apt-get update && apt-get -y --no-install-recommends install nginx; fi
COPY nginx /etc/nginx
COPY src /src
CMD ["/bin/sh" , "-c" , "/run.sh"]