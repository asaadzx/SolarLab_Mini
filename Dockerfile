# Minimal single-stage image for the SolarLab Mini dashboard.
FROM python:3.12-slim

# Keep Python output unbuffered and avoid bytecode files in the image.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# The app is launched from its own directory.
WORKDIR /app/laptop_app/dashboard

# Install only the dashboard runtime dependencies.
COPY laptop_app/requirements-docker.txt /app/laptop_app/requirements-docker.txt
RUN pip install --no-cache-dir -r /app/laptop_app/requirements-docker.txt

# Copy the dashboard code, templates, and static files.
COPY laptop_app/dashboard/ /app/laptop_app/dashboard/

# Prepare the persistent data directory for the non-root user.
RUN mkdir -p /app/data && chown -R 10001:10001 /app/data
USER 10001:10001

# Documented port; host networking means no docker -p flag is needed.
EXPOSE 5000

# Run the Flask development server with debug disabled by app.py.
CMD ["python", "app.py"]
