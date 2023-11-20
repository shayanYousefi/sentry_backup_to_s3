
import boto3
import docker
from datetime import datetime, date
from pathlib import Path

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
NOW = datetime.now().strftime(TIME_FORMAT)


def create_backup_directory(backup_folder):
    Path(backup_folder).mkdir(exist_ok=True)


def get_volume_backup_file_name(volume, date=NOW):
    return '{}-{}.tar.gz'.format(date, volume.name)


def connect_to_s3(endpoint, access_key, secret_key):

    s3_client = boto3.client('s3', endpoint_url=endpoint,
                             aws_secret_access_key=secret_key,
                             aws_access_key_id=access_key)
    return s3_client


def connect_to_docker_engine():
    client = docker.from_env()
    return client


def get_file_name_from_s3_response(content, prefix=""):
    key = content['Key']
    if prefix and key.startswith(prefix):
        key = key[len(prefix):]
    return key


def get_volume_name_from_file_name(file_name):
    sentry_index = file_name.find('sentry')
    tar_index = file_name.find('.tar.gz')
    if sentry_index == -1 or tar_index == -1:
        raise Exception(
            'could not get volume name from file {}'.format(file_name))
    return file_name[sentry_index:tar_index]


def get_upload_path(file_path, prefix):
    file_name = Path(file_path).name
    return '{}{}'.format(prefix, file_name)


def remove_backup_files(backup_files):
    for file in backup_files:
        Path(file).unlink()
        print('Removed file {}'.format(file))


def convert_to_boolean(val):
    if isinstance(val, bool):
        return val
    if not isinstance(val, str):
        raise Exception(
            "could not convert type {} to boolean".format(type(val)))
    val = val.lower().strip()
    if val == "true":
        return True
    else:
        return False


def convert_to_date(val):
    date = None
    try:
        date = datetime.strptime(val, TIME_FORMAT)
    except ValueError:
        raise Exception(
            'Could not convert --date argument to datetime. format of --date must be {}'.format(TIME_FORMAT))
    return date.strftime(TIME_FORMAT)
