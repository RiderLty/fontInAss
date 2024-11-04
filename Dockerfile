# FROM python:3.10-slim-buster 

# ARG NGINX=YES
# ARG TARGETPLATFORM

# COPY fontMap.json localFontMap.json requirements.txt run.sh /
# RUN apt-get update && chmod 777 /run.sh
# # RUN test "${NGINX}" = "YES" && apt-get install nginx -y || echo "不安装nginx"
# RUN if [ "${NGINX}" = "YES" ]; then apt-get install nginx -y; fi
# RUN if [ "${TARGETPLATFORM}" != "linux/amd64" ]; then apt-get install gcc build-essential -y; fi
# COPY nginx /etc/nginx
# COPY src /src
# CMD ["/bin/sh" , "-c" , "/run.sh"]



# FROM python:3.10-slim-buster AS builder
# # RUN apt-get update && \
# #     apt-get install -y --no-install-recommends gcc build-essential
# COPY requirements.txt .
# RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt
# # 最终阶段
# FROM python:3.10-slim-buster 
# COPY --from=builder /wheels /wheels
# COPY --from=builder /requirements.txt .
# RUN pip install --no-cache /wheels/* && rm -rf /wheels
# CMD ["/bin/sh" , "-c" , "cat"]

FROM python:3.10-slim-buster AS builder
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc build-essential
COPY requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

FROM python:3.10-slim-buster 
ARG NGINX=YES
COPY --from=builder /wheels /wheels
COPY --from=builder /requirements.txt .
COPY fontMap.json localFontMap.json requirements.txt run.sh /
RUN pip install --no-cache /wheels/* && rm -rf /wheels && chmod 777 /run.sh
RUN if [ "${NGINX}" = "YES" ]; then apt-get update && apt-get -y --no-install-recommends install nginx; fi
COPY nginx /etc/nginx
COPY src /src
CMD ["/bin/sh" , "-c" , "/run.sh"]