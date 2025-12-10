FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc

RUN pip install --no-cache-dir telethon google-generativeai cryptg watchdog requests dotenv

COPY . /app/

CMD ["python","-u","media_sorter.py"]