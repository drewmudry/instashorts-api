# instashorts-api

## Local Development Setup

### Without Docker
to run the fast api: 
open a terminal and run: 

```fastapi dev main.py```

to run a local worker: 
open another terminal and run:

```celery -A tasks.video_processor worker --loglevel=INFO``` 

### With Docker

#### Prerequisites
- Docker and Docker Compose installed
- `.env` file with all required environment variables

#### Running the Application

1. Build and start all services:
```bash
docker-compose up --build
```

2. To run in detached mode (background):
```bash
docker-compose up -d --build
```

3. To stop all services:
```bash
docker-compose down
```

4. To view logs:
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web      # FastAPI
docker-compose logs -f redis    # Redis
docker-compose logs -f celery   # Celery worker
```

5. To check service status:
```bash
docker-compose ps
```

#### Services
- FastAPI: http://localhost:8000
- Redis: localhost:6379
- Celery Worker: Automatically connected to Redis

#### Notes
- Code changes are automatically reflected due to volume mounts
- Redis data persists between restarts
- All environment variables are loaded from `.env` file 