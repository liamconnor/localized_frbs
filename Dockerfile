FROM python:3.11-slim

WORKDIR /app

# Install datasette and plugins
RUN pip install datasette datasette-cluster-map

# Copy database and metadata
COPY frbs.db /app/
COPY metadata.json /app/
COPY templates /app/templates/

EXPOSE 8080

CMD ["datasette", "frbs.db", "--host", "0.0.0.0", "--port", "8080", "--metadata", "metadata.json", "--template-dir", "templates"]
