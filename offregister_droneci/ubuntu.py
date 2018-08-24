from cStringIO import StringIO
from functools import partial
from os import path
from sys import modules

from fabric.context_managers import cd
from fabric.operations import run, put
from offregister_docker import ubuntu as docker
from pkg_resources import resource_filename
from yaml import load, dump

data_dir = partial(path.join, path.dirname(resource_filename(modules[__name__].__name__, '__init__.py')), '_data')


def install0(*args, **kwargs):
    docker.install_docker0()
    docker.install_docker_user1()

    kwargs['DRONE_OPEN'].setdefault(True)

    with open(data_dir('drone.docker-compose.yaml'), 'rt') as f:
        compose = load(f)

    if 'DRONE_GITHUB' in kwargs and kwargs['DRONE_GITHUB']:
        compose['drone-server'] += ['{}={}'.format(k, kwargs[k])
                                    for k in kwargs if k.startswith('DRONE_')]

        compose['drone-agent']['services']['drone-agent']['environment'].append(
            'DRONE_SECRET={}'.format(kwargs['DRONE_SECRET'])
        )

    sio = StringIO()
    dump(compose, sio)
    sio.seek(0)

    run('mkdir -p $HOME/docker')
    with cd('$HOME/docker'):
        put(sio, 'drone.yml')
        return run('docker-compose up -f drone.yml')
