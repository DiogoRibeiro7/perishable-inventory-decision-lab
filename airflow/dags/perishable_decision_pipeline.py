"""Example Airflow DAG for dbt and Cloud Run batch jobs.

The orchestration environment needs the Google Airflow provider. Both dbt and
model scoring are packaged as independently deployable Cloud Run Jobs.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.google.cloud.operators.bigquery import BigQueryCheckOperator
from airflow.providers.google.cloud.operators.cloud_run import CloudRunExecuteJobOperator

GCP_PROJECT_ID = "{{ var.value.gcp_project_id }}"
GCP_REGION = "europe-west1"
DBT_JOB = "perishable-lab-dbt"
DECISION_JOB = "perishable-lab-daily-decisions"

with DAG(
    dag_id="perishable_inventory_daily_decisions",
    start_date=datetime(2026, 1, 1),
    schedule="30 4 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data-science",
        "retries": 2,
        "retry_delay": timedelta(minutes=10),
    },
    tags=["forecasting", "inventory", "fresh-food"],
) as dag:
    transform_features = CloudRunExecuteJobOperator(
        task_id="transform_features",
        project_id=GCP_PROJECT_ID,
        region=GCP_REGION,
        job_name=DBT_JOB,
        overrides={
            "container_overrides": [
                {"args": ["build", "--select", "+stg_daily_demand"]}
            ]
        },
        deferrable=True,
    )

    validate_feature_rows = BigQueryCheckOperator(
        task_id="validate_feature_rows",
        sql="""
        select count(*) > 0
        from `{{ var.value.gcp_project_id }}.marts.daily_forecast_features`
        where feature_date = date_sub(date('{{ ds }}'), interval 1 day)
        """,
        use_legacy_sql=False,
    )

    generate_decisions = CloudRunExecuteJobOperator(
        task_id="generate_decisions",
        project_id=GCP_PROJECT_ID,
        region=GCP_REGION,
        job_name=DECISION_JOB,
        overrides={
            "container_overrides": [
                {
                    "args": [
                        "score-bigquery",
                        "--decision-date",
                        "{{ ds }}",
                    ]
                }
            ]
        },
        deferrable=True,
    )

    validate_recommendations = BigQueryCheckOperator(
        task_id="validate_recommendations",
        sql="""
        select
          count(*) > 0
          and countif(recommended_order_quantity < 0) = 0
          and countif(model_version is null) = 0
        from `{{ var.value.gcp_project_id }}.marts.fct_daily_order_decisions`
        where decision_date = date('{{ ds }}')
        """,
        use_legacy_sql=False,
    )

    transform_features >> validate_feature_rows >> generate_decisions >> validate_recommendations
