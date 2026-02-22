FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app
CMD ["uvicorn", "mock_llm:app", "--host", "0.0.0.0", "--port", "5100"]