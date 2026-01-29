FROM python:3.9-slim

WORKDIR /app

# Copy the built React app
COPY dist ./dist

# Expose port
EXPOSE 8080

# Serve the static files
CMD ["python", "-m", "http.server", "8080", "--directory", "dist"]

