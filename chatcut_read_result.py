"""Read a spawned job's result out of the durable Dict.

Separate from the launcher ON PURPOSE: the whole point is that the answer does
not depend on the process that started the work still being alive.
"""
import json
import modal

app = modal.App("chatcut-read-result")
RESULTS = modal.Dict.from_name("chatcut-results", create_if_missing=True)


@app.local_entrypoint()
def main(run_id: str = "", list_all: bool = False):
    if list_all or not run_id:
        print("keys:", list(RESULTS.keys()))
        return
    v = RESULTS.get(run_id)
    if v is None:
        print(f"{run_id}: ABSENT — not finished, or never started. Not 'empty'.")
        return
    print(json.dumps(v, indent=1)[:12000])
