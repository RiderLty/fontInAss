FROM python:3.10-slim-buster 
COPY main.py fontMap.json requirements.txt /
RUN pip install -r ./requirements.txt
CMD ["python" , "main.py"]