#!/usr/bin/env python3

import boto3
import docker
from os import getenv
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from argparse import BooleanOptionalAction, ArgumentParser


def define_arguments(parser):
    parser.add_argument('-e', '--s3-endpoint',
                        help='Endpoint to store backup file',
                        default=getenv('S3_ENDPOINT', ''))
    parser.add_argument('-u', '--access-key',
                        help='Access key for s3',
                        default=getenv('S3_ACCESS_KEY', ''))
    parser.add_argument('-p', '--secret-key',
                        help='Secret key for s3',
                        default=getenv('S3_SECRET_KEY', ''))
    parser.add_argument('-b', '--bucket',
                        help='Bucket of s3',
                        default=getenv('S3_BUCKET', ''))
    parser.add_argument('--prefix',
                        help='Prefix to add to upload path',
                        default=getenv('S3_PATH_PREFIX', ''))
    parser.add_argument('-r', '--remove-files',
                        help='Remove files after upload',
                        action=BooleanOptionalAction,
                        default=False)
    parser.add_argument('--backup-folder',
                        help='Local backup file location',
                        nargs=1,
                        default='./backup')


def connect_to_docker_engine():
    client = docker.from_env()
    return client


def connect_to_s3(endpoint, access_key, secret_key):

    s3_client = boto3.client('s3', endpoint_url=endpoint,
                             aws_secret_access_key=secret_key,
                             aws_access_key_id=access_key)
    return s3_client


def get_sentry_volumes(client):

    volumes = client.volumes.list()
    sentry_volumes = []
    for volume in volumes:
        if 'sentry-' in volume.name:
            sentry_volumes.append(volume)
    return sentry_volumes


def create_backup_directory(backup_folder):
    Path(backup_folder).mkdir(exist_ok=True)


def get_volume_backup_file_name(volume):
    return '{}-{}.tar.gz'.format(datetime.now().date(), volume.name)


def export(docker_client, volumes, backup_folder):

    backup_files = []

    for volume in volumes:
        backup_file_name = get_volume_backup_file_name(volume)
        backup_file_path = '{}/{}'.format(backup_folder, backup_file_name)

        print('exporting {} to {}'.format(
            volume.name,
            backup_file_path))
        export_volume(docker_client, volume.name,
                      backup_file_name, backup_folder)

        backup_files.append(backup_file_path)
    return backup_files


def export_volume(docker_client, volume_name, backup_file_name, backup_folder):
    absolute_path = Path(backup_folder).absolute()
    docker_client.containers.run("busybox:1.36.1",
                                 "tar -zcvf /vackup/{} /vackup-volume".format(
                                     backup_file_name),
                                 remove=True,
                                 volumes={
                                     volume_name: {'bind': '/vackup-volume', 'mode': 'rw'},
                                     absolute_path: {'bind': '/vackup', 'mode': 'rw'},
                                 },
                                 )

    return backup_file_name


def get_upload_path(file_path, prefix):
    file_name = Path(file_path).name
    if prefix:
        prefix = prefix.rstrip('/')
        return '{}/{}'.format(prefix, file_name)
    else:
        return file_name


def upload_backup_files_to_s3(backup_files, s3_client, bucket, prefix):
    for backup_file in backup_files:
        upload_path = get_upload_path(backup_file, prefix)
        s3_client.upload_file(
            backup_file, bucket, upload_path)
        print('File {} uploaded successfully'.format(backup_file))


def remove_backup_files(backup_files):
    for file in backup_files:
        Path(file).remove()
        print('Removed file {}'.format(file))


if __name__ == "__main__":

    load_dotenv()
    parser = ArgumentParser(description='Sentry backup script')
    define_arguments(parser)
    args = parser.parse_args()
    backup_folder = args.backup_folder
    create_backup_directory(backup_folder)
    docker_client = connect_to_docker_engine()
    s3_client = connect_to_s3(
        args.s3_endpoint, args.access_key, args.secret_key)
    volumes = get_sentry_volumes(docker_client)
    print("Exporting sentry volumes")
    backup_files = export(docker_client, volumes, backup_folder)
    if args.s3_endpoint[0]:
        print(args.access_key)
        if not args.access_key:
            print('Aborting upload. No access key given')
            exit(1)
        if not args.secret_key:
            print('Aborting upload. No secret key given')
            exit(1)
        print("Uploading backup files to s3")
        try:
            upload_backup_files_to_s3(
                backup_files, s3_client, args.bucket, args.prefix)
        finally:
            if args.remove_files:
                print('Removing local backup files')
                remove_backup_files(backup_files)
