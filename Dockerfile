# Use the official Python runtime as the base image
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy only the dependency file first
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the remaining application files
COPY . .

# Tell Docker that the application listens on port 5000
EXPOSE 5000

# Start the Flask application
RUN chmod +x start.sh

CMD ["./start.sh"]