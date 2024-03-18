import logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(name)s %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s  %(name)s %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        # 'file': {
        #     'level': 'INFO',
        #     'class': 'logging.FileHandler',
        #     'filename': '/path/to/django/debug.log',
        #     'formatter': 'verbose'
        # },
    },
    'loggers': {
        logger_name: {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        } for logger_name in ['django', 'django.request', 'django.db.backends', 'django.security']
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    }
}