ARG BUILDER=riderlty/fontinass-builder:hashvalue
FROM ${BUILDER} 
ARG NGINX=YES
RUN if [ "${NGINX}" = "YES" ]; then apt-get update && apt-get -y --no-install-recommends install nginx; fi
COPY onlineFonts.json run.sh /
COPY nginx /etc/nginx
COPY src /src/
RUN chmod 777 /run.sh
CMD ["/bin/sh" , "-c" , "/run.sh"]