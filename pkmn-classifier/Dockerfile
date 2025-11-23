FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install -r requirements.txt


# Default command to run your consumer
CMD ["python", "./src/main.py"]
