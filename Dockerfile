FROM python:3.11-slim

WORKDIR /app
# COPY ./*.py /app
COPY ./requirements.txt /app

RUN pip install --trusted-host pypi.python.org -r requirements.txt

CMD ["python", "main.py"]
