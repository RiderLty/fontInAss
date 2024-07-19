FROM python:3.8-slim
RUN pip install -r ./requirements.txt
CMD [/python main.py]
