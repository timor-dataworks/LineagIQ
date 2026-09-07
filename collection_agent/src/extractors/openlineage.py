from typing import Dict, Any, List


class OpenLineageExtractor:
    """
    Extractor for standard OpenLineage JSON run events.
    """

    def parse_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        event_type = event_data.get("eventType")
        job = event_data.get("job", {})
        job_name = f"{job.get('namespace', '')}.{job.get('name', '')}"
        
        inputs = event_data.get("inputs", [])
        outputs = event_data.get("outputs", [])
        
        input_datasets = [
            f"{inp.get('namespace', '')}.{inp.get('name', '')}"
            for inp in inputs
        ]
        output_datasets = [
            f"{out.get('namespace', '')}.{out.get('name', '')}"
            for out in outputs
        ]
        
        edges = []
        for inp_ds in input_datasets:
            edges.append({
                "source": job_name,
                "target": inp_ds,
                "type": "CONSUMED_BY",
            })
            
        for out_ds in output_datasets:
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
