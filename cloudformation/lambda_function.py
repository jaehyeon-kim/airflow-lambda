import time
import re
import random
import logging
import traceback
import boto3
from datetime import datetime
from botocore import exceptions
from io import StringIO
from functools import update_wrapper

# save logs to stream
stream = StringIO()
logger = logging.getLogger()
log_handler = logging.StreamHandler(stream)
formatter = logging.Formatter("%(levelname)-8s %(asctime)-s %(name)-12s %(message)s")
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

cwlogs = boto3.client("logs")


class CustomLogManager(object):
    # create log stream and send logs to it
    def __init__(self, event):
        self.group_name = event["group_name"]
        self.stream_name = event["stream_name"]

    def has_log_group(self):
        group_exists = True
        try:
            resp = cwlogs.describe_log_groups(logGroupNamePrefix=self.group_name)
            group_exists = len(resp["logGroups"]) > 0
        except exceptions.ClientError as e:
            logger.error(e.response["Error"]["Code"])
            group_exists = False
        return group_exists

    def create_log_stream(self):
        is_created = True
        try:
            cwlogs.create_log_stream(logGroupName=self.group_name, logStreamName=self.stream_name)
        except exceptions.ClientError as e:
            logger.error(e.response["Error"]["Code"])
            is_created = False
        return is_created

    def delete_log_stream(self):
        is_deleted = True
        try:
            cwlogs.delete_log_stream(logGroupName=self.group_name, logStreamName=self.stream_name)
        except exceptions.ClientError as e:
            # ResourceNotFoundException is ok
            codes = [
                "InvalidParameterException",
                "OperationAbortedException",
                "ServiceUnavailableException",
            ]
            if e.response["Error"]["Code"] in codes:
                logger.error(e.response["Error"]["Code"])
                is_deleted = False
        return is_deleted

    def init_log_stream(self):
        if not all([self.has_log_group(), self.delete_log_stream(), self.create_log_stream()]):
            raise Exception("fails to create log stream")
        logger.info("log stream created")

    def create_log_events(self, stream):
        fmt = "%Y-%m-%d %H:%M:%S,%f"
        log_events = []
        for m in [s for s in stream.getvalue().split("\n") if s]:
            match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}", m)
            dt_str = match.group() if match else datetime.utcnow().strftime(fmt)
            log_events.append(
                {"timestamp": int(datetime.strptime(dt_str, fmt).timestamp()) * 1000, "message": m}
            )
        return log_events

    def put_log_events(self, stream):
        try:
            resp = cwlogs.put_log_events(
                logGroupName=self.group_name,
                logStreamName=self.stream_name,
                logEvents=self.create_log_events(stream),
            )
            logger.info(resp)
        except exceptions.ClientError as e:
            logger.error(e)
            raise Exception("fails to put log events")


class LambdaDecorator(object):
    # keep functions to run before, after and on exception
    # modified from lambda_decorators (https://lambda-decorators.readthedocs.io/en/latest/)
    def __init__(self, handler):
        update_wrapper(self, handler)
        self.handler = handler

    def __call__(self, event, context):
        try:
            self.event = event
            self.log_manager = CustomLogManager(event)
            return self.after(self.handler(*self.before(event, context)))
        except Exception as exception:
            return self.on_exception(exception)

    def before(self, event, context):
        # remove existing logs
        stream.seek(0)
        stream.truncate(0)
        # create log stream
        self.log_manager.init_log_stream()
        logger.info("Start Request")
        return event, context

    def after(self, retval):
        logger.info("End Request")
        # send logs to stream
        self.log_manager.put_log_events(stream)
        return retval

    def on_exception(self, exception):
        logger.error(str(exception))
        # log traceback
        logger.error(traceback.format_exc())
        # send logs to stream
        self.log_manager.put_log_events(stream)
        return str(exception)


@LambdaDecorator
def lambda_handler(event, context):
    max_len = event.get("max_len", 6)
    fails_at = random.randint(0, max_len * 2)
    for i in range(max_len):
        if i != fails_at:
            logger.info("current run {0}".format(i))
        else:
            raise Exception("fails at {0}".format(i))
        time.sleep(1)
