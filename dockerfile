FROM python:3.12-slim

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt

# Copy the entire project
COPY . /app/

# Set Python path
ENV PYTHONPATH=/app


CMD ["fastapi", "run", "main.py", "--port", "8000"]