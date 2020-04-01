import time
import logging
import boto3
from botocore import exceptions
from io import StringIO
from functools import wraps, update_wrapper

stream = StringIO()
logger = logging.getLogger()
handler = logging.StreamHandler(stream)
formatter = logging.Formatter(
    "[%(levelname)-8s] %(asctime)-s %(name)-12s %(message)s", "%Y-%m-%dT%H:%M:%SZ"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)


# def lambda_handler(event, context):
#     for i in range(5):
#         if i != 3:
#             logger.info(i)
#         else:
#             logger.critical(i)
#         time.sleep(1)
#     for m in stream.getvalue().split("\n"):
#         print(m)


# lambda_handler({}, {})

# cwlogs = boto3.client("logs")


class CustomLogHandler(object):
    def __init__(self, handler):
        update_wrapper(self, handler)
        self.handler = handler

    def __call__(self, event, context):
        try:
            return self.after(self.handler(*self.before(event, context)))
        except Exception as exception:
            return self.on_exception(exception)

    def before(self, event, context):
        print("event: ", event)
        return event, context

    def after(self, retval):
        print("retval: ", retval)
        return retval

    def on_exception(self, exception):
        return {"statusCode": 500, "body": "uh oh, you broke it"}


@CustomLogHandler
def lambda_handler(event, context):
    print("hello")
    raise Exception


# def has_log_group(prefix):
#     group_exists = True
#     try:
#         resp = cwlogs.describe_log_groups(logGroupNamePrefix=prefix)
#         group_exists = len(resp["logGroups"]) > 0
#     except exceptions.ClientError:
#         group_exists = False
#     return group_exists


# def create_log_stream(group_name, stream_name):
#     is_created = True
#     try:
#         cwlogs.create_log_stream(logGroupName=group_name, logStreamName=stream_name)
#     except exceptions.ClientError:
#         is_created = False
#     return is_created


# def delete_log_stream(group_name, stream_name):
#     is_deleted = True
#     try:
#         cwlogs.delete_log_stream(
#             logGroupName=group_name, logStreamName=stream_name,
#         )
#     except exceptions.ClientError as e:
#         # ResourceNotFoundException is ok
#         codes = [
#             "InvalidParameterException",
#             "OperationAbortedException",
#             "ServiceUnavailableException",
#         ]
#         if e.response["Error"]["Code"] in codes:
#             is_deleted = False
#     return is_deleted


# def is_stream_ready(event):
#     return all(
#         [
#             has_log_group(event["group_name"]),
#             delete_log_stream(event["group_name"], event["stream_name"]),
#             create_log_stream(event["group_name"], event["stream_name"]),
#         ]
#     )


# def lambda_handler(event, context):
#     if not is_stream_ready(event):
#         logger.error("no log group or fails to create log stream")
#         return

#     for r in range(15):
#         time.sleep(1)
#         if int(event["fail_at"]) == r:
#             raise Exception("fail at {0}".format(event["fail_at"]))
#         logger.info("wait for {0} sec".format(r + 1))


# event = {
#     "group_name": "/airflow/lambda/airflow-test",
#     "stream_name": "2020/04/01/[$LATEST]bc53f53f28ab4fc2882d86386201f70f",
#     "fail_at": "10",
# }

# group_name = "/airflow/lambda/airflow-test"
# stream_name = "2020/04/01/[$LATEST]bc53f53f28ab4fc2882d86386201f70f"

# has_log_group(group_name)
# delete_log_stream(group_name, stream_name)
# create_log_stream(group_name, stream_name)
