FROM python:3.10-slim-buster 
ARG TARGETPLATFORM
COPY fontMap.json localFontMap.json requirements.txt run.sh /
RUN if [ "$TARGETPLATFORM" = "linux/amd64" ]; then \
        echo "x86平台"; \
        pip install -r ./requirements.txt; \
    elif [ "$TARGETPLATFORM" = "linux/arm64" ]; then \
        echo "ARM平台"; \
        apt-get update && apt-get install gcc build-essential -y && pip install -r ./requirements.txt; \
    else \
        echo "未识别的平台"; \
    fi
COPY src /src
CMD ["/bin/sh" , "-c" ,"python src/main.py"]