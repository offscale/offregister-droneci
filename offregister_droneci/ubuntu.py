from cStringIO import StringIO
from functools import partial
from os import path
from sys import modules

from fabric.context_managers import cd
from fabric.operations import run, put, get
from nginx_parse_emit import emit, utils
from nginxparser import dumps
from offregister_docker import ubuntu as docker
from offregister_fab_utils.fs import cmd_avail
from offregister_fab_utils.ubuntu.systemd import restart_systemd
from offutils import generate_temp_password
from pkg_resources import resource_filename
from yaml import safe_dump, safe_load

data_dir = partial(path.join, path.dirname(resource_filename(modules[__name__].__name__, '__init__.py')), '_data')


def _json_bool(s):  # type: (any) -> str
    if type(s) == bool:
        return '{}'.format(s).lower()
    return s


def install0(*args, **kwargs):
    if not cmd_avail('go'):
        docker.install_docker0()
        docker.install_docker_user1()
        docker.install_docker_compose3()

    kwargs.setdefault('DRONE_OPEN', True)
    kwargs.setdefault('DRONE_SECRET', generate_temp_password(32))

    with open(data_dir('drone.docker-compose.yaml'), 'rt') as f:
        compose = safe_load(f)

    if 'DRONE_SERVER_PORTS' in kwargs:
        compose['services']['drone-server']['ports'] = kwargs['DSP'] = kwargs.pop('DRONE_SERVER_PORTS')

    if 'GITHUB' in kwargs:
        kwargs['DRONE_GITHUB'] = 'true'
        kwargs['DRONE_GITHUB_CLIENT'] = kwargs['GITHUB']['client_id']
        kwargs['DRONE_GITHUB_SECRET'] = kwargs['GITHUB']['client_secret']

    if 'DRONE_GITHUB' in kwargs and kwargs['DRONE_GITHUB']:
        compose['services']['drone-server']['environment'] = ['{}={}'.format(k, _json_bool(kwargs[k]))
                                                              for k in kwargs if k.startswith('DRONE_')]

        compose['services']['drone-agent']['environment'].append(
            'DRONE_SECRET={}'.format(kwargs['DRONE_SECRET'])
        )
        if 'ports' in compose['services']['drone-server']:
            compose['services']['drone-agent']['environment'].append(
                'DRONE_SERVER=localhost:{}'.format(compose['services']['drone-server']['ports'][1])
            )

    sio = StringIO()
    safe_dump(compose, sio, default_flow_style=False)
    sio.seek(0)

    docker_dir = run('echo $HOME/docker/drone', quiet=True)
    run('mkdir -p {docker}'.format(docker=docker_dir))
    with cd(docker_dir):
        put(sio, 'docker-compose.yaml')
        return run('docker-compose up')


def configure_nginx1(*args, **kwargs):
    nginx_conf = '/etc/nginx/sites-available/{server_name}'.format(server_name=kwargs['SERVER_NAME'])
    sio = StringIO()
    get(nginx_conf, sio)
    sio.seek(0)

    conf = sio.read()

    dumps(utils.upsert_by_location(
        '/drone', conf,
        emit.api_proxy_block('/drone', 'https://localhost:{}'.format(
            kwargs.get('DSP', kwargs.get('DRONE_SERVER_PORTS', (None, None)))[1] or '9000'
        ))
    ))

    put(sio, nginx_conf)

    return restart_systemd('nginx')
