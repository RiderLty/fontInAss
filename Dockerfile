FROM node:22.19-slim as NPM_BUILDER
COPY ./src/subset /workspace
WORKDIR /workspace
RUN npm install && npm run build

FROM python:3.10-bookworm AS CYTHON_BUILDER
COPY ./src/py2cy /workspace
WORKDIR /workspace
RUN pip install cython && python /workspace/setup.py

FROM astral/uv:python3.10-bookworm-slim
COPY onlineFonts.json run.sh requirements.txt uv.lock pyproject.toml /
COPY src  /src/
COPy --from=CYTHON_BUILDER /workspace/*.so /src/py2cy/
COPY --from=NPM_BUILDER /workspace/dist /src/subset/
ENV UV_COMPILE_BYTECODE=1
ENV UV_SYSTEM_PYTHON=1
RUN uv pip install -r /requirements.txt && chmod 777 /run.sh
CMD ["/bin/sh" , "-c" , "/run.sh"]
