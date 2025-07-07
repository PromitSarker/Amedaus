FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install Python and pip
RUN apt update && apt install -y python3 python3-pip && apt clean

# Set the working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Expose port
EXPOSE 8000

# Run the FastAPI app (adjust path to your main:app)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]