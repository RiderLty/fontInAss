FROM riderlty/python-with-packages:latest AS builder
ADD ./ /fontinass
WORKDIR /fontinass
RUN cd server && pyinstaller main.py -F -p ./ --name fontinass 

# FROM python:3.9-slim-buster 
FROM python:3.9-slim
COPY --from=builder /fontinass/dist/fontinass  /fontinass  fontMap.json . localFontMap.json .
CMD [/fontinass]
