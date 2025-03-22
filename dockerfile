# Source image
FROM python:3.12-alpine as builder

# Create app directory
WORKDIR /app

# Set python env vars
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install required software 
RUN pip install --upgrade pip
RUN apk add --no-cache imagemagick imagemagick-heic imagemagick-jpeg imagemagick-pdf imagemagick-svg imagemagick-webp gcc musl-dev libavif-dev

# Copy python files
COPY ./image_autoresize.py .
COPY ./requirements.txt .

# Install python dependencies
RUN pip install -r requirements.txt

# Add app user and group
RUN addgroup -S -g 10001 app && \
  adduser -u 10000 -G app -D app

# Take ownership of app files
RUN chown -R app:app .

# Switch to app user account
USER app

# Run the program
ENTRYPOINT ["python", "image_autoresize.py"]
