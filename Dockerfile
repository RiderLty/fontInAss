FROM python:3.10-slim-buster 
COPY main.py fontMap.json requirements.txt /
RUN pip install -r ./requirements.txt
CMD [/python main.py]

# FROM riderlty/python-with-packages:latest AS builder
# ADD ./ /fontinass
# WORKDIR /fontinass
# RUN pyinstaller main.py -F -p ./ --name fontinass 

# # FROM python:3.9-slim-buster 
# FROM python:3.9-slim
# COPY --from=builder /fontinass/dist/fontinass  /fontinass  
# COPY fontMap.json /
# CMD [/fontinass]