"""Generates realistic 3-version historical schema and lineage dataset for LineagIQ demo."""

import os
import shutil
import time
from typing import Any

from core.embedder import LocalEmbedder
from core.models import (
    BusinessTermNode,
    ColumnNode,
    DatasetNode,
    Edge,
    EdgeType,
    GraphPayload,
    PipelineNode,
    UserTeamNode,
)
from core.writer import ArtifactWriter


def build_version_0() -> GraphPayload:
    """Version 0: Initial Core E-Commerce Platform."""
    nodes: list[Any] = []
    edges: list[Any] = []

    # Teams
    team_ae = UserTeamNode(
        id="team.analytics_engineering", name="Analytics Engineering", email="analytics-eng@acme.corp"
    )
    nodes.append(team_ae)

    # 1. Raw Data Sources
    raw_cust = DatasetNode(
        id="postgres.raw.raw_customers",
        name="raw_customers",
        database="postgres",
        schema_name="raw",
        description="Landing table for raw customer profile records from Postgres OLTP",
        owner="team.analytics_engineering",
    )
    raw_orders = DatasetNode(
        id="postgres.raw.raw_orders",
        name="raw_orders",
        database="postgres",
        schema_name="raw",
        description="Landing table for raw order records from Postgres OLTP",
        owner="team.analytics_engineering",
    )
    raw_payments = DatasetNode(
        id="postgres.raw.raw_payments",
        name="raw_payments",
        database="postgres",
        schema_name="raw",
        description="Landing table for payment transaction records",
        owner="team.analytics_engineering",
    )
    nodes.extend([raw_cust, raw_orders, raw_payments])

    # Columns for raw_customers
    c_id = ColumnNode(
        id="postgres.raw.raw_customers.id", name="id", dataset_id=raw_cust.id, data_type="INTEGER", is_nullable=False
    )
    c_name = ColumnNode(
        id="postgres.raw.raw_customers.name", name="name", dataset_id=raw_cust.id, data_type="VARCHAR", is_nullable=True
    )
    c_email = ColumnNode(
        id="postgres.raw.raw_customers.email",
        name="email",
        dataset_id=raw_cust.id,
        data_type="VARCHAR",
        is_nullable=True,
    )
    nodes.extend([c_id, c_name, c_email])

    # Columns for raw_orders
    o_id = ColumnNode(
        id="postgres.raw.raw_orders.id", name="id", dataset_id=raw_orders.id, data_type="INTEGER", is_nullable=False
    )
    o_cust_id = ColumnNode(
        id="postgres.raw.raw_orders.customer_id", name="customer_id", dataset_id=raw_orders.id, data_type="INTEGER"
    )
    o_status = ColumnNode(
        id="postgres.raw.raw_orders.status", name="status", dataset_id=raw_orders.id, data_type="VARCHAR"
    )
    nodes.extend([o_id, o_cust_id, o_status])

    # Columns for raw_payments
    p_id = ColumnNode(
        id="postgres.raw.raw_payments.id", name="id", dataset_id=raw_payments.id, data_type="INTEGER", is_nullable=False
    )
    p_order_id = ColumnNode(
        id="postgres.raw.raw_payments.order_id", name="order_id", dataset_id=raw_payments.id, data_type="INTEGER"
    )
    p_amount = ColumnNode(
        id="postgres.raw.raw_payments.amount", name="amount", dataset_id=raw_payments.id, data_type="NUMERIC"
    )
    nodes.extend([p_id, p_order_id, p_amount])

    # 2. Staging Pipelines (dbt)
    pipe_stg_cust = PipelineNode(
        id="dbt.staging.stg_customers",
        name="stg_customers",
        description="Standardizes customer records and handles nulls",
        resource_type="model",
        owner="team.analytics_engineering",
    )
    pipe_stg_orders = PipelineNode(
        id="dbt.staging.stg_orders",
        name="stg_orders",
        description="Cleans raw orders and casts dates",
        resource_type="model",
        owner="team.analytics_engineering",
    )
    pipe_stg_payments = PipelineNode(
        id="dbt.staging.stg_payments",
        name="stg_payments",
        description="Normalizes payment transactions into dollars",
        resource_type="model",
        owner="team.analytics_engineering",
    )
    nodes.extend([pipe_stg_cust, pipe_stg_orders, pipe_stg_payments])

    # 3. Data Marts
    dim_cust = DatasetNode(
        id="dbt.marts.dim_customers",
        name="dim_customers",
        database="snowflake",
        schema_name="marts",
        description="Customer dimensional mart with lifetime orders and spend",
        owner="team.analytics_engineering",
    )
    fct_orders = DatasetNode(
        id="dbt.marts.fct_orders",
        name="fct_orders",
        database="snowflake",
        schema_name="marts",
        description="Fact table of all processed customer transactions",
        owner="team.analytics_engineering",
    )
    nodes.extend([dim_cust, fct_orders])

    # Edges V0
    edges.append(Edge(source_id=raw_cust.id, target_id=pipe_stg_cust.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=pipe_stg_cust.id, target_id=dim_cust.id, type=EdgeType.PRODUCED_BY))

    edges.append(Edge(source_id=raw_orders.id, target_id=pipe_stg_orders.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=pipe_stg_orders.id, target_id=dim_cust.id, type=EdgeType.PRODUCED_BY))
    edges.append(Edge(source_id=pipe_stg_orders.id, target_id=fct_orders.id, type=EdgeType.PRODUCED_BY))

    edges.append(Edge(source_id=raw_payments.id, target_id=pipe_stg_payments.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=pipe_stg_payments.id, target_id=fct_orders.id, type=EdgeType.PRODUCED_BY))

    # Ownership
    for ds in [raw_cust, raw_orders, raw_payments, dim_cust, fct_orders]:
        edges.append(Edge(source_id=ds.id, target_id=team_ae.id, type=EdgeType.OWNED_BY))

    # Joins
    edges.append(Edge(source_id=c_id.id, target_id=o_cust_id.id, type=EdgeType.JOINS_WITH))
    edges.append(Edge(source_id=o_id.id, target_id=p_order_id.id, type=EdgeType.JOINS_WITH))

    # Belongs to
    for c in [c_id, c_name, c_email]:
        edges.append(Edge(source_id=c.id, target_id=raw_cust.id, type=EdgeType.BELONGS_TO))
    for c in [o_id, o_cust_id, o_status]:
        edges.append(Edge(source_id=c.id, target_id=raw_orders.id, type=EdgeType.BELONGS_TO))
    for c in [p_id, p_order_id, p_amount]:
        edges.append(Edge(source_id=c.id, target_id=raw_payments.id, type=EdgeType.BELONGS_TO))

    return GraphPayload(nodes=nodes, edges=edges)


def build_version_1() -> GraphPayload:
    """Version 1: Global Multi-Currency & GDPR Compliance Overhaul."""
    payload = build_version_0()
    nodes = list(payload.nodes)
    edges = list(payload.edges)

    # 1. New Governance Team & Business Terms
    team_gov = UserTeamNode(
        id="team.data_governance", name="Data Governance & Compliance", email="privacy-officer@acme.corp"
    )
    term_gdpr = BusinessTermNode(
        id="term.gdpr_right_to_be_forgotten",
        name="GDPR Right To Be Forgotten",
        definition="Requires crypto-shredding and irreversible pseudonymization of EU citizen PII",
        domain="Compliance",
    )
    term_net_rev = BusinessTermNode(
        id="term.net_revenue_usd",
        name="Net Revenue (USD)",
        definition="Gross order revenue converted to USD minus refunds, payment gateway fees, and localized VAT",
        domain="Finance",
    )
    nodes.extend([team_gov, term_gdpr, term_net_rev])

    # 2. Breaking Schema Evolution: Remove raw plaintext email, add hashed email and gdpr consent
    nodes = [n for n in nodes if n.id != "postgres.raw.raw_customers.email"]
    edges = [
        e
        for e in edges
        if e.source_id != "postgres.raw.raw_customers.email" and e.target_id != "postgres.raw.raw_customers.email"
    ]

    c_email_hash = ColumnNode(
        id="postgres.raw.raw_customers.email_sha256",
        name="email_sha256",
        dataset_id="postgres.raw.raw_customers",
        data_type="VARCHAR",
        description="One-way SHA-256 hashed email for identity resolution without PII exposure",
    )
    c_gdpr_consent = ColumnNode(
        id="postgres.raw.raw_customers.gdpr_consent_status",
        name="gdpr_consent_status",
        dataset_id="postgres.raw.raw_customers",
        data_type="VARCHAR",
        description="Explicit consent status (OPT_IN, OPT_OUT, PENDING)",
    )
    nodes.extend([c_email_hash, c_gdpr_consent])
    edges.append(Edge(source_id=c_email_hash.id, target_id="postgres.raw.raw_customers", type=EdgeType.BELONGS_TO))
    edges.append(Edge(source_id=c_gdpr_consent.id, target_id="postgres.raw.raw_customers", type=EdgeType.BELONGS_TO))
    edges.append(Edge(source_id=c_email_hash.id, target_id=term_gdpr.id, type=EdgeType.GOVERNED_BY))

    # 3. Currency and Gateway columns on raw_payments
    p_curr = ColumnNode(
        id="postgres.raw.raw_payments.currency_code",
        name="currency_code",
        dataset_id="postgres.raw.raw_payments",
        data_type="VARCHAR",
        description="ISO 4217 Currency (USD, EUR, GBP, JPY)",
    )
    p_fx = ColumnNode(
        id="postgres.raw.raw_payments.exchange_rate_to_usd",
        name="exchange_rate_to_usd",
        dataset_id="postgres.raw.raw_payments",
        data_type="NUMERIC",
        description="Historical FX conversion rate to USD at settlement timestamp",
    )
    nodes.extend([p_curr, p_fx])
    edges.append(Edge(source_id=p_curr.id, target_id="postgres.raw.raw_payments", type=EdgeType.BELONGS_TO))
    edges.append(Edge(source_id=p_fx.id, target_id="postgres.raw.raw_payments", type=EdgeType.BELONGS_TO))

    # 4. New External Source: Stripe Payment Gateway API
    stripe_charges = DatasetNode(
        id="stripe.api.charges",
        name="stripe_charges",
        database="stripe_gateway",
        schema_name="api_v1",
        description="Raw webhook ingest of global credit card charges, fees, and dispute events",
        owner="team.data_governance",
    )
    pipe_stripe = PipelineNode(
        id="dbt.staging.stg_stripe_transactions",
        name="stg_stripe_transactions",
        description="Ingests Stripe webhook charges and reconciles dispute statuses",
        resource_type="model",
        owner="team.analytics_engineering",
    )
    nodes.extend([stripe_charges, pipe_stripe])
    edges.append(Edge(source_id=stripe_charges.id, target_id=pipe_stripe.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=pipe_stripe.id, target_id="dbt.staging.stg_payments", type=EdgeType.PRODUCED_BY))
    edges.append(Edge(source_id=stripe_charges.id, target_id=team_gov.id, type=EdgeType.OWNED_BY))

    # Governance on fct_orders
    edges.append(Edge(source_id="dbt.marts.fct_orders", target_id=term_net_rev.id, type=EdgeType.GOVERNED_BY))

    return GraphPayload(nodes=nodes, edges=edges)


def build_version_2() -> GraphPayload:
    """Version 2: AI-Powered Churn Prediction & Real-Time Streaming Architecture."""
    payload = build_version_1()
    nodes = list(payload.nodes)
    edges = list(payload.edges)

    # 1. Teams & Stakeholders
    team_c_suite = UserTeamNode(id="team.c_suite", name="Executive Leadership (CEO/CRO/CFO)", email="exec@acme.corp")
    team_ml = UserTeamNode(id="team.ml_ai_engineering", name="Machine Learning & AI Platform", email="ml-ops@acme.corp")
    nodes.extend([team_c_suite, team_ml])

    # 2. Real-Time Streaming Ingestion (Kafka + Flink)
    kafka_events = DatasetNode(
        id="kafka.events.user_sessions_stream",
        name="user_sessions_stream",
        database="kafka_cluster",
        schema_name="production_events",
        description="Real-time event stream capturing user web/mobile sessions, cart abandonment, and search queries",
        owner="team.ml_ai_engineering",
    )
    flink_session_agg = PipelineNode(
        id="pipeline.streaming.session_aggregator",
        name="session_aggregator",
        description="Apache Flink streaming job computing rolling 30-day session activity and churn triggers",
        resource_type="streaming_job",
        owner="team.ml_ai_engineering",
    )
    realtime_features = DatasetNode(
        id="feature_store.realtime.user_engagement_features",
        name="user_engagement_features",
        database="feast_feature_store",
        schema_name="customer_features",
        description="Aggregated real-time customer behavioral features for low-latency ML scoring",
        owner="team.ml_ai_engineering",
    )
    nodes.extend([kafka_events, flink_session_agg, realtime_features])

    edges.append(Edge(source_id=kafka_events.id, target_id=flink_session_agg.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=flink_session_agg.id, target_id=realtime_features.id, type=EdgeType.PRODUCED_BY))
    edges.append(Edge(source_id=kafka_events.id, target_id=team_ml.id, type=EdgeType.OWNED_BY))
    edges.append(Edge(source_id=realtime_features.id, target_id=team_ml.id, type=EdgeType.OWNED_BY))

    # 3. Machine Learning Churn Predictor Pipeline
    churn_predictor = PipelineNode(
        id="pipeline.ml.customer_churn_predictor",
        name="customer_churn_predictor",
        description="Gradient-boosted decision tree predicting 30-day customer churn risk and revenue exposure",
        resource_type="ml_pipeline",
        owner="team.ml_ai_engineering",
    )
    churn_scores = DatasetNode(
        id="ml_serving.predictions.customer_churn_scores",
        name="customer_churn_scores",
        database="snowflake",
        schema_name="ml_predictions",
        description="Scored customer churn probabilities, risk levels, and automated retention recommendations",
        owner="team.ml_ai_engineering",
    )
    nodes.extend([churn_predictor, churn_scores])

    # ML Inputs: dim_customers, fct_orders, user_engagement_features
    edges.append(Edge(source_id="dbt.marts.dim_customers", target_id=churn_predictor.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id="dbt.marts.fct_orders", target_id=churn_predictor.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=realtime_features.id, target_id=churn_predictor.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=churn_predictor.id, target_id=churn_scores.id, type=EdgeType.PRODUCED_BY))
    edges.append(Edge(source_id=churn_scores.id, target_id=team_ml.id, type=EdgeType.OWNED_BY))

    # 4. Executive BI Command Center & Growth Marketing Automation
    exec_dashboard = DatasetNode(
        id="bi.tableau.executive_churn_revenue_command_center",
        name="executive_churn_revenue_command_center",
        database="tableau_server",
        schema_name="executive_finance",
        description="C-Level strategic dashboard visualizing ARR at risk, customer retention cohort curves, and pipeline health",
        owner="team.c_suite",
    )
    marketing_sync = PipelineNode(
        id="pipeline.automation.churn_prevention_hubspot_sync",
        name="churn_prevention_hubspot_sync",
        description="Automated reverse-ETL webhook triggering high-touch VIP retention workflows for at-risk accounts",
        resource_type="reverse_etl",
        owner="team.analytics_engineering",
    )
    nodes.extend([exec_dashboard, marketing_sync])

    edges.append(Edge(source_id=churn_scores.id, target_id=exec_dashboard.id, type=EdgeType.DISPLAYED_IN))
    edges.append(Edge(source_id="dbt.marts.fct_orders", target_id=exec_dashboard.id, type=EdgeType.DISPLAYED_IN))
    edges.append(Edge(source_id=churn_scores.id, target_id=marketing_sync.id, type=EdgeType.CONSUMED_BY))
    edges.append(Edge(source_id=exec_dashboard.id, target_id=team_c_suite.id, type=EdgeType.OWNED_BY))

    # 5. Strategic Business Terms
    term_churn = BusinessTermNode(
        id="term.customer_churn_risk_index",
        name="Customer Churn Risk Index",
        definition="Composite metric (0.0-1.0) forecasting probability of customer contract non-renewal within 90 days",
        domain="Revenue Operations",
    )
    term_ltv = BusinessTermNode(
        id="term.lifetime_value_forecast",
        name="Customer Lifetime Value Forecast",
        definition="Estimated future net margin contribution discounted over projected account lifespan",
        domain="Finance",
    )
    nodes.extend([term_churn, term_ltv])

    edges.append(Edge(source_id=churn_scores.id, target_id=term_churn.id, type=EdgeType.GOVERNED_BY))
    edges.append(Edge(source_id=churn_scores.id, target_id=term_ltv.id, type=EdgeType.GOVERNED_BY))

    return GraphPayload(nodes=nodes, edges=edges)


def run_multiversion_generation(target_dir: str | None = None) -> None:
    """Generates and writes 3 progressive versions of lineage and schema metadata."""
    effective_dir = target_dir or os.environ.get("DATA_PATH")
    if not effective_dir:
        raise ValueError("DATA_PATH environment variable must be set.")

    if not effective_dir.startswith("s3://"):
        if os.path.exists(effective_dir):
            for item in os.listdir(effective_dir):
                item_path = os.path.join(effective_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path, ignore_errors=True)
                else:
                    try:
                        os.remove(item_path)
                    except OSError:
                        pass
        os.makedirs(effective_dir, exist_ok=True)

    embedder = LocalEmbedder()
    writer = ArtifactWriter()

    # Step 1: Version 0
    print("Writing Version 0 (Initial Core E-Commerce Platform)...")
    p0 = build_version_0()
    p0 = embedder.embed_payload(p0)
    writer.write_all(p0, effective_dir, mode="overwrite")
    print(f"  V0 committed: {len(p0.nodes)} nodes, {len(p0.edges)} edges")

    time.sleep(2)

    # Step 2: Version 1
    print("Writing Version 1 (Multi-Currency & GDPR Compliance Overhaul)...")
    p1 = build_version_1()
    p1 = embedder.embed_payload(p1)
    writer.write_all(p1, effective_dir, mode="overwrite")
    print(f"  V1 committed: {len(p1.nodes)} nodes, {len(p1.edges)} edges")

    time.sleep(2)

    # Step 3: Version 2
    print("Writing Version 2 (AI-Powered Churn Prediction & Real-Time Streaming)...")
    p2 = build_version_2()
    p2 = embedder.embed_payload(p2)
    writer.write_all(p2, effective_dir, mode="overwrite")
    print(f"  V2 committed: {len(p2.nodes)} nodes, {len(p2.edges)} edges")

    print("\nAll 3 versions committed successfully to Delta Lake at:", effective_dir)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate 3-version historical lineage dataset for LineagIQ demo")
    parser.parse_args()

    target_dir = os.environ.get("DATA_PATH")
    if not target_dir:
        raise ValueError("DATA_PATH environment variable must be set.")
    run_multiversion_generation(target_dir)


if __name__ == "__main__":
    main()
