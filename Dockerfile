FROM riderlty/python-with-packages:latest AS builder
ADD ./ /fontinass
WORKDIR /fontinass
RUN pyinstaller main.py -F -p ./ --name fontinass 

# FROM python:3.9-slim-buster 
FROM python:3.9-slim
COPY --from=builder /fontinass/dist/fontinass  /fontinass  
COPY ./fontMap.json ./localFontMap.json /
CMD [/fontinass]
