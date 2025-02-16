# instashorts-api
to run the fast api: 
open a terminal and run: 

```fastapi dev main.py```

to run a local worker: 
open another terminal and run:

```celery -A tasks.video_processor worker --loglevel=INFO``` 