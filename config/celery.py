from celery import Celery
from config.settings import settings
from ssl import CERT_NONE

celery_app = Celery('video_processor')

# Configure Celery with Redis SSL settings
celery_app.conf.update({
    'broker_url': settings.redis_url,
    'result_backend': settings.redis_url,
    'broker_use_ssl': {
        'ssl_cert_reqs': CERT_NONE
    },
    'redis_backend_use_ssl': {
        'ssl_cert_reqs': CERT_NONE
        
    }
})
