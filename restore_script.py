#!/usr/bin/env python3

from os import getenv
from pathlib import Path
from dotenv import load_dotenv
from argparse import ArgumentParser
import utility
import docker


def define_arguments(parser):
    parser.add_argument('-d', '--datetime',
                        required=True,
                        help='What datetime to restore. format: 2023-02-03T10:01:05'
                        )
    parser.add_argument('-e', '--s3-endpoint',
                        help='Endpoint for s3',
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
                        help='Prefix to add to upload path',
                        default=getenv('S3_PATH_PREFIX', ''))
    parser.add_argument('-r', '--remove-files',
                        action="store_true",
                        help='Whether to remove local files after script is done',
                        default=False)
    parser.add_argument('--backup-folder',
                        help='Local backup file location',
                        default=getenv('BACKUP_FOLDER', './backup'))


def download_from_s3(s3_client, bucket, prefix, file_name, backup_folder):
    s3_client.download_file(bucket, "{}{}".format(prefix, file_name),
                            "{}/{}".format(backup_folder, file_name))
    return file_name


def download_backup_files(s3_client, bucket, prefix, file_names, backup_folder):
    downloaded_file = []
    for file_name in file_names:
        print('Downloading {}'.format(file_name))
        download_from_s3(
            s3_client, bucket, prefix, file_name, backup_folder)
        downloaded_file.append(file_name)
    return downloaded_file


def import_volumes(docker_client, file_names, backup_folder):

    for file_name in file_names:
        print('Importing {}'.format(file_name))
        import_volume(docker_client, file_name, backup_folder)


def import_volume(docker_client, file_name, backup_folder):
    absolute_Backup_folder_path = Path(backup_folder).absolute()
    full_path = "{}/{}".format(absolute_Backup_folder_path, file_name)
    volume_name = utility.get_volume_name_from_file_name(file_name)
    try:
        volume = docker_client.volumes.get(volume_name)
        volume.remove()
    except docker.errors.NotFound:
        pass
    docker_client.volumes.create(volume_name)
    docker_client.containers.run('busybox:1.36.1',
                                 'sh -c "cd /backup-volume && tar xvf /backup/{} --strip 1"'.format(
                                     file_name),
                                 remove=True,
                                 volumes={
                                     volume_name: {'bind': '/backup-volume', 'mode': 'rw'},
                                     absolute_Backup_folder_path: {'bind': '/backup', 'mode': 'rw'},
                                 })


# def get_local_backup_file_list(backup_folder,date):


def get_remote_backup_file_list(s3_client, bucket, prefix, date):
    response = s3_client.list_objects_v2(
        Bucket=bucket,
        MaxKeys=40,
        Prefix="{}{}".format(prefix, date)
    )
    file_list = []
    if response["KeyCount"] != 0:
        file_list = []
        for content in response["Contents"]:
            file_key = utility.get_file_name_from_s3_response(content, prefix)
            file_list.append(file_key)
    return file_list


def get_local_backup_file_list(backup_folder, date):
    file_list = []
    for file in Path(backup_folder).iterdir():
        if file.name.startswith(date) and file.name.endswith(".tar.gz") and file.name.find('sentry') != -1:
            file_list.append(file.name)
    return file_list


if __name__ == "__main__":

    load_dotenv()
    parser = ArgumentParser(description='Sentry backup script')
    define_arguments(parser)
    args = parser.parse_args()
    args.datetime = utility.convert_to_date(args.datetime)

    backup_folder = args.backup_folder
    utility.create_backup_directory(backup_folder)

    docker_client = utility.connect_to_docker_engine()

    if args.s3_endpoint:
        if not args.access_key:
            print('Aborting upload. No access key given')
            exit(1)
        if not args.secret_key:
            print('Aborting upload. No secret key given')
            exit(1)
        print("Downloading backup files to s3")
        s3_client = utility.connect_to_s3(
            args.s3_endpoint, args.access_key, args.secret_key)
        file_names = get_remote_backup_file_list(
            s3_client, args.bucket, args.prefix, args.datetime)
        download_backup_files(
            s3_client, args.bucket, args.prefix, file_names, args.backup_folder)
    else:
        file_names = get_local_backup_file_list(
            backup_folder, args.datetime)
    print("Importing sentry volumes")
    if len(file_names) < 1:
        print('No file found to restore. Aborting restore.')
        exit(1)
    import_volumes(docker_client, file_names, backup_folder)
