import re
import time
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
        self.payload = payload
        # log stream is created and added to payload
        self.awslogs_group = awslogs_group
        self.awslogs_stream = "{0}/[{1}]{2}".format(
            datetime.utcnow().strftime("%Y/%m/%d"),
            self.qualifier,
            re.sub("-", "", str(uuid.uuid4())),
        )
        # lambda client and cloudwatch logs hook
        self.client = AwsHook(aws_conn_id=aws_conn_id).get_client_type("lambda")
        self.awslogs_hook = AwsLogsHook(aws_conn_id=aws_conn_id, region_name=region_name)

    def execute(self, context):
        self.log.info(
            "Log group {0}, Log stream {1}".format(self.awslogs_group, self.awslogs_stream)
        )
        self.log.info(
            "Invoking Lambda Function - Function name: {0}, Qualifier {1}".format(
                self.function_name, self.qualifier
            )
        )
        self.log.info("Payload - {0}".format(self.payload))
        # invoke - wait - check
        payload = json.dumps(
            {
                **{"group_name": self.awslogs_group, "stream_name": self.awslogs_stream},
                **self.payload,
            }
        )
        invoke_opts = {
            "FunctionName": self.function_name,
            "Qualifier": self.qualifier,
            "InvocationType": "RequestResponse",
            "Payload": bytes(payload, encoding="utf8"),
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
        has_message = False
        invocation_failed = False
        messages = []
        max_trial = 5
        current_trial = 0
        # sometimes events are not retrieved, run for 5 times if so
        while True:
            current_trial += 1
            for event in self.awslogs_hook.get_log_events(self.awslogs_group, self.awslogs_stream):
                dt = datetime.fromtimestamp(event["timestamp"] / 1000.0)
                self.log.info("[{}] {}".format(dt.isoformat(), event["message"]))
                messages.append(event["message"])
            if len(messages) > 0 or current_trial > max_trial:
                break
            time.sleep(2)
        if len(messages) == 0:
            raise AirflowException("Fails to get log events")
        for m in reversed(messages):
            if re.search("ERROR", m) != None:
                raise AirflowException("Lambda Function invocation is not successful")

    def _get_function_timeout(self):
        resp = self.client.get_function(FunctionName=self.function_name, Qualifier=self.qualifier)
        return resp["Configuration"]["Timeout"]
