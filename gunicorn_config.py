#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

bind = '0.0.0.0:8083'
workers = 1
loglevel = "info"


# Function to be executed before each request

def pre_request(worker, req):
    req.start_time = time.time()
    worker.log.info(f"[START] {req.method} {req.path} from {req.remote_addr}")


def post_request(worker, req, environ, resp):
    duration = time.time() - getattr(req, 'start_time', time.time())
    worker.log.info(f"[END] {req.method} {req.path} → {resp.status} in {duration:.3f}s")


# Function to be executed when a worker is aborted due to a timeout
def worker_abort(worker):
    worker.log.info("Aborted for timeout!")
    raise TimeoutError('Request timed out')


# Assign the pre_request and post_request functions
pre_request = pre_request
post_request = post_request
worker_abort = worker_abort

# Additional configuration settings (if needed)
timeout = 99999
keepalive = 2

max_requests = 20000
