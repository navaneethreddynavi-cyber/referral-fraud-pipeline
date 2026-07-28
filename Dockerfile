# Use official Python image
FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements file first (so Docker can cache this layer)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY your_script.py .
COPY profile_data.py .

# Command to run when the container starts
CMD ["python", "your_script.py"]