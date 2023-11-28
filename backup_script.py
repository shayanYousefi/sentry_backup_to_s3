#!/usr/bin/env python3

from os import getenv
from pathlib import Path
from dotenv import load_dotenv
from argparse import ArgumentParser
from utility import create_backup_directory, get_volume_backup_file_name, connect_to_s3, connect_to_docker_engine, get_upload_path, remove_backup_files, convert_to_boolean


def define_arguments(parser):
    parser.add_argument('-e', '--s3-endpoint',
                        help='Endpoint to use for s3. __*Note*__: if not provided volume backup in backup folder is used and other s3 args are ignored',
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
    parser.add_argument('-a', '--prefix',
                        help='Prefix to add to remote file path',
                        default=getenv('S3_PATH_PREFIX', ''))
    parser.add_argument('-r', '--remove-files',
                        action="store_true",
                        help='Whether to remove local files after backup is done. ignored if s3 endpoint is not defined',
                        default=False)
    parser.add_argument('--backup-folder',
                        help='Local backup file location',
                        default=getenv('BACKUP_FOLDER', './backup'))


def get_sentry_volumes(client):

    volumes = client.volumes.list()
    sentry_volumes = []
    for volume in volumes:
        if 'sentry-' in volume.name:
            sentry_volumes.append(volume)
    return sentry_volumes


def export_volumes(docker_client, volumes, backup_folder):

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
                                 "tar -zcvf /backup/{} /backup-volume".format(
                                     backup_file_name),
                                 remove=True,
                                 volumes={
                                     volume_name: {'bind': '/backup-volume', 'mode': 'rw'},
                                     absolute_path: {'bind': '/backup', 'mode': 'rw'},
                                 },
                                 )

    return backup_file_name


def upload_backup_files_to_s3(backup_files, s3_client, bucket, prefix):
    for backup_file in backup_files:
        upload_path = get_upload_path(backup_file, prefix)
        s3_client.upload_file(
            backup_file, bucket, upload_path)
        print('File {} uploaded successfully'.format(backup_file))


if __name__ == "__main__":

    load_dotenv()
    parser = ArgumentParser(description='Sentry backup script')
    define_arguments(parser)
    args = parser.parse_args()
    backup_folder = args.backup_folder
    create_backup_directory(backup_folder)

    docker_client = connect_to_docker_engine()

    volumes = get_sentry_volumes(docker_client)
    print("Exporting sentry volumes")
    backup_files = export_volumes(docker_client, volumes, backup_folder)
    if args.s3_endpoint:
        if not args.access_key:
            print('Aborting upload. No access key given')
            exit(1)
        if not args.secret_key:
            print('Aborting upload. No secret key given')
            exit(1)
        print("Uploading backup files to s3")
        try:

            s3_client = connect_to_s3(
                args.s3_endpoint, args.access_key, args.secret_key)
            upload_backup_files_to_s3(
                backup_files, s3_client, args.bucket, args.prefix)
        finally:
            if args.remove_files:
                print('Removing local backup files')
                remove_backup_files(backup_files)
