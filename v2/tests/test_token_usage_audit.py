import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("token_audit",Path(__file__).resolve().parents[1]/"scripts/report_token_usage.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def usage(n):
    return {"input_tokens":n*10,"cached_input_tokens":n*8,"output_tokens":n,
            "reasoning_output_tokens":0,"total_tokens":n*11}


class TokenAuditTests(unittest.TestCase):
    def fixture(self,folder,name,parent,events):
        path = folder/f"rollout-{name}.jsonl"
        rows = [{"type":"session_meta","payload":{"id":name,"parent_thread_id":parent,
            "source":{"subagent":{"thread_spawn":{"agent_path":"/root/"+name}}} if parent else "vscode"}}]
        for second,total in events:
            rows.append({"timestamp":f"2026-09-08T00:00:{second:02d}Z","type":"event_msg",
                "payload":{"type":"token_count","info":{"total_token_usage":usage(total),"last_token_usage":usage(total)}}})
        path.write_text("\n".join(json.dumps(row) for row in rows)+"\n")

    def test_repeated_cumulative_events_not_double_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder,"main",None,[(1,10),(2,10),(3,20)])
            report = module.audit([folder],"main")
            self.assertEqual(report["recorded_usage_total"]["total_tokens"],220)
            self.assertEqual(report["recorded_usage_total"]["uncached_input_tokens"],40)

    def test_session_reset_segments_and_since(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder,"main",None,[(1,10),(2,20),(3,3),(4,7)])
            report = module.audit([folder],"main","2026-09-08T00:00:03Z")
            self.assertEqual(report["recorded_usage_total"]["total_tokens"],297)
            self.assertEqual(report["recorded_usage_since"]["total_tokens"],77)
            self.assertEqual(len(report["threads"][0]["counter_resets"]),1)

    def test_descendants_only_and_duplicate_archived_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder,"main",None,[(1,10)])
            self.fixture(folder,"child","main",[(2,5)])
            self.fixture(folder,"grandchild","child",[(3,2)])
            self.fixture(folder,"unrelated",None,[(4,999)])
            report = module.audit([folder,folder],"main")
            self.assertEqual(report["recorded_usage_total"]["total_tokens"],187)
            self.assertEqual(len(report["threads"]),3)

    def test_missing_usage_is_not_claimed_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.fixture(folder,"main",None,[(1,10)])
            self.fixture(folder,"child","main",[])
            report = module.audit([folder],"main")
            self.assertFalse(report["all_discovered_threads_have_usage"])
            self.assertFalse(report["complete_project_lifetime_usage_known"])


if __name__ == "__main__":
    unittest.main()
