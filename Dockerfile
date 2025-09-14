FROM node:22.19-slim as npm_builder
COPY ./src/subset /workspace
WORKDIR /workspace
RUN npm install && npm run build

FROM python:3.10-bookworm AS cython_builder
COPY ./src/py2cy /workspace
COPY ./requirements.txt /
RUN pip install cython && python /workspace/setup.py && pip wheel --no-cache-dir --no-deps --wheel-dir /wheels --find-links /wheels  -r /requirements.txt 

FROM python:3.10-slim-bookworm
COPY onlineFonts.json run.sh requirements.txt uv.lock pyproject.toml /
COPY src  /src/
COPY --from=npm_builder /workspace/dist /src/subset/dist/
COPy --from=cython_builder /workspace/*.so /src/py2cy/
RUN --mount=type=bind,target=/wheels,from=cython_builder,source=/wheels \
    chmod 777 /run.sh &&  pip install --no-cache --find-links /wheels -r /requirements.txt  && mkdir /data
CMD ["/bin/sh" , "-c" , "/run.sh"]
