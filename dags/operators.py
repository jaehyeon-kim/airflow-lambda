import re
import json
import math
import uuid
from datetime import datetime
from botocore import exceptions
from airflow.exceptions import AirflowException
from airflow.models import BaseOperator
from airflow.utils import apply_defaults

from airflow.contrib.hooks.aws_hook import AwsHook
from airflow.contrib.hooks.aws_logs_hook import AwsLogsHook


class LambdaOperator(BaseOperator):
    @apply_defaults
    def __init__(
        self,
        function_name,
        awslogs_group,
        qualifier="$LATEST",
        payload={},
        aws_conn_id=None,
        region_name=None,
        *args,
        **kwargs
    ):
        super(LambdaOperator, self).__init__(**kwargs)

        self.function_name = function_name
        self.qualifier = qualifier

        self.awslogs_group = awslogs_group
        self.awslogs_stream = "{0}/[{1}]{2}".format(
            datetime.utcnow().strftime("%Y/%m/%d"),
            self.qualifier,
            re.sub("-", "", str(uuid.uuid4())),
        )

        self.payload = json.dumps(
            {**{"group_name": self.awslogs_group, "stream_name": self.awslogs_stream}, **payload,}
        )

        self.client = AwsHook(aws_conn_id=aws_conn_id).get_client_type("lambda")
        self.log_hook = AwsLogsHook(aws_conn_id=aws_conn_id, region_name=region_name)

    def execute(self, context):
        self.log.info(
            "Invoking Lambda Function - Function name: {0}, Qualifier {1}".format(
                self.function_name, self.qualifier
            )
        )

        invoke_opts = {
            "FunctionName": self.function_name,
            "Qualifier": self.qualifier,
            "InvocationType": "RequestResponse",
            "Payload": bytes(self.payload, encoding="utf8"),
        }
        try:
            resp = self.client.invoke(**invoke_opts)
            self.log.info("Lambda function invoked - StatusCode {0}".format(resp["StatusCode"]))
        except exceptions.ClientError as e:
            raise AirflowException(e.response["Error"])

        self._wait_for_function_ended()

        self._check_success_invocation()
        self.log.info("Lambda Function has been successfully invoked")

    def _wait_for_function_ended(self):
        waiter = self.client.get_waiter("function_active")
        waiter.config.max_attempts = math.ceil(
            self._get_function_timeout() / 5
        )  # poll interval - 5 seconds
        waiter.wait(FunctionName=self.function_name, Qualifier=self.qualifier)

    def _check_success_invocation(self):
        self.log.info("Lambda Function logs output")
        messages = []
        for event in self.log_hook.get_log_events(self.awslogs_group, self.awslogs_stream):
            dt = datetime.fromtimestamp(event["timestamp"] / 1000.0)
            self.log.info("[{}] {}".format(dt.isoformat(), event["message"]))
            messages.append(event["message"])
        if any([re.search("ERROR", m) != None for m in messages]):
            raise AirflowException("Lambda Function invocation is not successful")

    def _get_function_timeout(self):
        resp = self.client.get_function(FunctionName=self.function_name, Qualifier=self.qualifier)
        return resp["Configuration"]["Timeout"]


# client = AwsHook(aws_conn_id=None).get_client_type("lambda")
# resp = client.invoke(FunctionName="foo")

###### how to put traceback???

# function_name = "airflow-test"
# awslogs_group = "/airflow/lambda/airflow-test"


# LambdaOperator(
#     function_name=function_name,
#     awslogs_group=awslogs_group,
#     payload={"fail_at": 2},
#     task_id="XXXXXXXXX",
# ).execute({})

# import re

# messages = [
#     "INFO     2020-04-02 03:29:50,913 botocore.credentials Found credentials in environment variables.",
#     "INFO     2020-04-02 03:29:51,360 root         log stream created",
#     "INFO     2020-04-02 03:29:51,360 root         Start Request",
#     "INFO     2020-04-02 03:29:51,360 root         current run 0",
#     "INFO     2020-04-02 03:29:52,362 root         current run 1",
#     "ERROR    2020-04-02 03:29:53,363 root         fails at 2",
# ]

# any([re.search("ERROR|EXCEPTION", m) != None for m in messages])
