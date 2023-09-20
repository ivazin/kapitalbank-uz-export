FROM python:3.11-slim

WORKDIR /app

COPY ./requirements.txt /app
RUN pip install --trusted-host pypi.python.org -r requirements.txt

COPY ./*.py /app

CMD ["python", "main.py"]
