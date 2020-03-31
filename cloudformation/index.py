import time
import logging
import boto3
from botocore import exceptions

logger = logging.getLogger()
logger.setLevel(logging.INFO)

cwlogs = boto3.client("logs")


def has_log_group(prefix):
    group_exists = True
    try:
        resp = cwlogs.describe_log_groups(logGroupNamePrefix=prefix)
        group_exists = len(resp["logGroups"]) > 0
    except exceptions.ClientError:
        group_exists = False
    return group_exists


def create_log_stream(group_name, stream_name):
    is_created = True
    try:
        cwlogs.create_log_stream(logGroupName=group_name, logStreamName=stream_name)
    except exceptions.ClientError:
        is_created = False
    return is_created


def delete_log_stream(group_name, stream_name):
    is_deleted = True
    try:
        cwlogs.delete_log_stream(
            logGroupName=group_name, logStreamName=stream_name,
        )
    except exceptions.ClientError as e:
        # ResourceNotFoundException is ok
        codes = [
            "InvalidParameterException",
            "OperationAbortedException",
            "ServiceUnavailableException",
        ]
        if e.response["Error"]["Code"] in codes:
            is_deleted = False
    return is_deleted


def init_log_stream(event):
    return all(
        [
            has_log_group(event["group_name"]),
            delete_log_stream(event["group_name"], event["stream_name"]),
            create_log_stream(event["group_name"], event["stream_name"]),
        ]
    )


def lambda_handler(event, context):
    is_stream_ready = init_log_stream(event)
    if not is_stream_ready:
        logger.error("no log group or fails to create log stream")
        return

    for r in range(15):
        time.sleep(1)
        if int(event["fail_at"]) == r:
            raise Exception("fail at {0}".format(event["fail_at"]))
        logger.info("wait for {0} sec".format(r + 1))


event = {
    "group_name": "/airflow/lambda/airflow-test",
    "stream_name": "2020/04/01/[$LATEST]bc53f53f28ab4fc2882d86386201f70f",
    "fail_at": "10",
}

group_name = "/airflow/lambda/airflow-test"
stream_name = "2020/04/01/[$LATEST]bc53f53f28ab4fc2882d86386201f70f"

has_log_group(group_name)
delete_log_stream(group_name, stream_name)
create_log_stream(group_name, stream_name)
