FROM python:3.9-slim
RUN pip install -r ./requirements.txt
CMD [/python main.py]
