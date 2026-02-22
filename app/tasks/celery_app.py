from celery import Celery

from app.core.config import settings

celery = Celery("lumina_tasks", broker=settings.redis_url, backend=settings.redis_url)

celery.conf.imports = ("app.tasks.tasks",)

celery.conf.task_routes = {
    "app.tasks.tasks.*": {"queue": "lumina"},
}
