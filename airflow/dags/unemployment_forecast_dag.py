"""DAG to automate monthly unemployment forecasting using H2O AutoML and Auto-sklearn."""

from datetime import datetime, timedelta
import calendar
from airflow import DAG
from airflow.models import Variable
from airflow.providers.docker.operators.docker import DockerOperator
from docker.types import Mount

# Retrieve the host project directory path (default to /Users/amirargani/Documents/GitHub/DeepWorkInsights)
# This is needed by DockerOperator to bind-mount the workspace so results are persistent on host.
HOST_PROJECT_PATH = Variable.get("host_project_path", default_var="/Users/amirargani/Documents/GitHub/DeepWorkInsights")

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'unemployment_forecast',
    default_args=default_args,
    description='Automated monthly German unemployment forecasting using AutoML',
    schedule='0 0,5,10,15,20 * * *',  # Run daily 5 times a day (00:00, 05:00, 10:00, 15:00, 20:00)
    start_date=datetime(2026, 8, 1),
    catchup=False,
    is_paused_upon_creation=False,
) as dag:

    # Task 1: Fetch and update German unemployment data
    fetch_data = DockerOperator(
        task_id='fetch_data',
        image='deepwork-forecast:latest',
        container_name='deepwork_fetch_data_{{ ts_nodash }}',
        api_version='auto',
        auto_remove=True,
        command='python -m packages.fetch_data',
        docker_url='unix://var/run/docker.sock',
        network_mode='deepwork_default',
        mounts=[Mount(source=HOST_PROJECT_PATH, target='/app', type='bind')],
        working_dir='/app',
        skip_on_exit_code=10,
    )

    # Task 2: Train H2O AutoML models and forecast the target month
    automl_forecast = DockerOperator(
        task_id='automl_forecast',
        image='deepwork-forecast:latest',
        container_name='deepwork_automl_forecast_{{ ts_nodash }}',
        api_version='auto',
        auto_remove=True,
        command='python -m packages.automl',
        docker_url='unix://var/run/docker.sock',
        network_mode='deepwork_default',
        mounts=[Mount(source=HOST_PROJECT_PATH, target='/app', type='bind')],
        working_dir='/app',
        environment={
            'DEEPWORK_MODE': 'test',
            'TARGET_DATE': '{{ logical_date.strftime("%Y-%m-%d") }}'
        },
        trigger_rule='none_failed',
    )

    # Task 3: Train Auto-sklearn models, rank performance, and compile unified report
    autosklearn_forecast = DockerOperator(
        task_id='autosklearn_forecast',
        image='deepwork-forecast:latest',
        container_name='deepwork_autosklearn_forecast_{{ ts_nodash }}',
        api_version='auto',
        auto_remove=True,
        command='python -m packages.autosklearn',
        docker_url='unix://var/run/docker.sock',
        network_mode='deepwork_default',
        mounts=[Mount(source=HOST_PROJECT_PATH, target='/app', type='bind')],
        working_dir='/app',
        environment={
            'DEEPWORK_MODE': 'test',
            'TARGET_DATE': '{{ logical_date.strftime("%Y-%m-%d") }}'
        },
        trigger_rule='none_failed',
    )

    # Task 4: Select and promote the best models when new original data becomes available
    promote_best_models = DockerOperator(
        task_id='promote_best_models',
        image='deepwork-forecast:latest',
        container_name='deepwork_promote_best_models_{{ ts_nodash }}',
        api_version='auto',
        auto_remove=True,
        command='python -m packages.model_selection',
        docker_url='unix://var/run/docker.sock',
        network_mode='deepwork_default',
        mounts=[Mount(source=HOST_PROJECT_PATH, target='/app', type='bind')],
        working_dir='/app',
        environment={
            'TARGET_DATE': '{{ logical_date.strftime("%Y-%m-%d") }}'
        },
        trigger_rule='none_failed',
    )

    # Define sequential dependency chain starting with fetch_data
    fetch_data >> automl_forecast >> autosklearn_forecast >> promote_best_models
