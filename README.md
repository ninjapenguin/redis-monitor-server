Redis Monitor Server
====================

Redis Monior is a stand alone server written to monitor one or multiple redis servers. Its primary use is to allow you to automate the testing of applications that interface directly with [Redis](http://www.redis.io)

## Contents
 * [Download] (https://github.com/ninjapenguin/redis-monitor-server/#download)
 * [Installation] (https://github.com/ninjapenguin/redis-monitor-server/#installation)
 * [Quickstart] (https://github.com/ninjapenguin/redis-monitor-server/#quickstart)

## Download

You can download Redis Monitor via:

### Bash

```bash
git clone https://github.com/ninjapenguin/redis-monitor-server.git
````

## Installation

To install dependencies

 ```bash
 pip install -r < requirements.txt
 ````

## Quickstart

### Option 1: starting the server manually and connecting to

To start the redis monitoring server listening on two local ports:

```bash
python monitor.py --redis_port 6997 6998
````

You are then able to communicate with server using zmq REQ socket, using python for example:

```python
import zmq
context = zmq.Context()

socket = context.socket(zmq.REQ)
socket.connect("tcp://localhost:5559")
socket.send('last')
response = socket.recv()
# response == u'keys *'
````