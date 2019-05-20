FROM python:alpine
RUN apk add --no-cache gcc linux-headers make musl-dev python-dev g++
ADD src/requirements.txt /app/
WORKDIR /app
RUN pip install -r requirements.txt
COPY src/ /app
EXPOSE 9484
CMD python ./kubedex.py
