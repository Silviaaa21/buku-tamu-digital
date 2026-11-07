FROM python:3.11-slim

# Set timezone & environment
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

# Buat grup dan user non-root
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# Buat direktori aplikasi dan direktori volume data
WORKDIR /app
RUN mkdir -p /data && chown -R appuser:appgroup /data /app

# Salin source code
COPY --chown=appuser:appgroup app.py .

# Beralih ke user non-root
USER appuser

# Expose port 5000 internal (tidak dibuka ke publik)
EXPOSE 5000

# Jalankan backend
CMD ["python", "app.py"]