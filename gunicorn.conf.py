# Gunicorn production config
bind = '0.0.0.0:5000'
workers = 4
worker_class = 'gevent'
worker_connections = 1000
timeout = 30
keepalive = 2
accesslog = '-'
errorlog = '-'
loglevel = 'info'
