from ielts_scorer import databricks_sql


class Completed:
    def __init__(self, stdout, returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def test_run_statement_polls_pending_statement(monkeypatch):
    responses = iter([
        Completed('{"statement_id":"s1","status":{"state":"PENDING"}}'),
        Completed('{"statement_id":"s1","status":{"state":"SUCCEEDED"},"result":{"data_array":[["ok"]]}}'),
    ])
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        return next(responses)

    monkeypatch.setattr(databricks_sql.subprocess, "run", fake_run)
    monkeypatch.setattr(databricks_sql.time, "sleep", lambda _: None)

    result = databricks_sql.run_statement("SELECT 1", timeout=2)

    assert result["status"]["state"] == "SUCCEEDED"
    assert calls[1][:4] == ["databricks", "api", "get", "/api/2.0/sql/statements/s1"]
