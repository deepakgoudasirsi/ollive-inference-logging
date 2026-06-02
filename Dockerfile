FROM node:20-alpine AS frontend
WORKDIR /web
COPY frontend/package.json /web/package.json
COPY frontend/package-lock.json /web/package-lock.json
RUN npm ci
COPY frontend/ /web/
RUN npm run build

FROM python:3.11-slim AS backend
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend/app /app/app

# Serve frontend from FastAPI at "/"
COPY --from=frontend /web/dist /app/frontend_dist

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

