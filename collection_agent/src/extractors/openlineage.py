from typing import Any


class OpenLineageExtractor:
    """
    Extractor for standard OpenLineage JSON run events emitted by Airflow, Spark, dbt, or Flink.

    Parses OpenLineage run events to extract pipeline job definitions, input dataset consumption edges (`CONSUMED_BY`),
    and output dataset production edges (`PRODUCED_BY`).
    """

    def parse_event(self, event_data: dict[str, Any]) -> dict[str, Any]:
        """
        Parses a single OpenLineage run event payload.

        :param event_data: Loaded JSON dictionary of an OpenLineage event.
        :return: Parsed dictionary containing `pipeline_id`, `inputs`, `outputs`, and lineage `edges`.
        """
        event_type = event_data.get("eventType")
        job = event_data.get("job", {})
        job_name = f"{job.get('namespace', '')}.{job.get('name', '')}".strip(".")

        inputs = event_data.get("inputs", [])
        outputs = event_data.get("outputs", [])

        input_datasets = [
            ds for ds in (
                f"{inp.get('namespace', '')}.{inp.get('name', '')}".strip(".")
                for inp in inputs
            ) if ds
        ]
        output_datasets = [
            ds for ds in (
                f"{out.get('namespace', '')}.{out.get('name', '')}".strip(".")
                for out in outputs
            ) if ds
        ]

        edges = []
        # Inputs -> Pipeline (CONSUMED_BY)
        for inp_ds in input_datasets:
            if inp_ds and job_name:
                edges.append({
                    "source": inp_ds,
                    "target": job_name,
                    "type": "CONSUMED_BY",
                })

        # Pipeline -> Outputs (PRODUCED_BY)
        for out_ds in output_datasets:
            if out_ds and job_name:
                edges.append({
                    "source": job_name,
                    "target": out_ds,
                    "type": "PRODUCED_BY",
                })


        return {
            "pipeline_id": job_name,
            "event_type": event_type,
            "run_id": event_data.get("run", {}).get("runId"),
            "event_time": event_data.get("eventTime"),
            "inputs": input_datasets,
            "outputs": output_datasets,
            "edges": edges,
        }

    def parse_events(self, events: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
        """
        Parses one or multiple OpenLineage run event payloads.

        :param events: Loaded JSON dictionary (single event) or list of event dictionaries.
        :return: List of parsed event dictionaries.
        """
        if isinstance(events, dict):
            return [self.parse_event(events)]
        return [self.parse_event(e) for e in events if isinstance(e, dict)]

