import airflow
from airflow import DAG
from airflow.utils.dates import days_ago
from datetime import timedelta
from dags.operators import LambdaOperator

function_name = "airflow-test"

demo_dag = DAG(
    dag_id="demo-dag",
    start_date=days_ago(1),
    catchup=False,
    max_active_runs=1,
    concurrency=1,
    schedule_interval=timedelta(seconds=30),
)

demo_task = LambdaOperator(
    task_id="demo-task",
    function_name=function_name,
    awslogs_group="/airflow/lambda/{0}".format(function_name),
    payload={"max_len": 6},
    dag=demo_dag,
)
