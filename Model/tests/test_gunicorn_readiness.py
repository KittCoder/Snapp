import json
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1]
DIAG_RE = re.compile(r"\b(pid|ppid|thread|warmup_module_name|module_name|warmup_manager_id|manager_id|warmup_state_id|state_id|status|warmup_completed|model_loaded|index_loaded|finished_at)=([^ ]+)")


def free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def parse_message(line):
    try:
        payload = json.loads(line)
        message = payload.get("message", "")
    except json.JSONDecodeError:
        message = line
    return message, dict(DIAG_RE.findall(message))


class GunicornReadinessIntegrationTests(unittest.TestCase):
    def test_preliminary_import_then_gunicorn_ready_uses_same_worker_manager(self):
        env = {
            **os.environ,
            "SNAPP_ENV": "production",
            "SNAPP_LOG_FORMAT": "json",
            "SNAPP_ADMIN_TOKEN": "test-token",
            "PYTHONUNBUFFERED": "1",
        }
        subprocess.run(
            [sys.executable, "-c", "import model"],
            cwd=MODEL_DIR,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )

        port = free_port()
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "gunicorn",
                "--bind",
                f"0.0.0.0:{port}",
                "--workers",
                "1",
                "--threads",
                "2",
                "--timeout",
                "120",
                "model:app",
            ],
            cwd=MODEL_DIR,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        lines = []
        line_queue: queue.Queue[str] = queue.Queue()

        def read_output():
            assert process.stdout is not None
            for output_line in process.stdout:
                lines.append(output_line.rstrip())
                line_queue.put(output_line.rstrip())

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        try:
            warmup_diag = None
            deadline = time.time() + 90
            while time.time() < deadline:
                try:
                    line = line_queue.get(timeout=1)
                except queue.Empty:
                    if process.poll() is not None:
                        self.fail(f"Gunicorn exited before warmup completed: {process.returncode}\n" + "\n".join(lines[-80:]))
                    continue
                message, diag = parse_message(line)
                if "matcher_warmup_complete" in message:
                    warmup_diag = diag
                    break
            self.assertIsNotNone(warmup_diag, "\n".join(lines[-120:]))

            ready_diags = []
            for _ in range(3):
                response = subprocess.run(
                    [
                        sys.executable,
                        "-c",
                        (
                            "import json,sys,urllib.request;"
                            f"r=urllib.request.urlopen('http://127.0.0.1:{port}/ready', timeout=20);"
                            "body=r.read().decode();"
                            "print(r.status);"
                            "print(body)"
                        ),
                    ],
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    timeout=30,
                )
                status_line, body = response.stdout.split("\n", 1)
                self.assertEqual(status_line.strip(), "200", body)
                payload = json.loads(body)
                self.assertEqual(payload["status"], "ready")
                self.assertTrue(payload["warmup_completed"])
                self.assertEqual(payload["artifact_validation_status"], payload["artifact_validation"]["status"])

                deadline = time.time() + 10
                while time.time() < deadline:
                    line = line_queue.get(timeout=1)
                    message, diag = parse_message(line)
                    if "ready_request" in message:
                        ready_diags.append(diag)
                        break

            self.assertEqual(len(ready_diags), 3, "\n".join(lines[-120:]))
            for ready_diag in ready_diags:
                self.assertEqual(ready_diag.get("pid"), warmup_diag.get("pid"))
                self.assertEqual(ready_diag.get("manager_id"), warmup_diag.get("warmup_manager_id"))
                self.assertEqual(ready_diag.get("state_id"), warmup_diag.get("warmup_state_id"))
                self.assertEqual(ready_diag.get("status"), "ready")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            if process.stdout is not None:
                process.stdout.close()


if __name__ == "__main__":
    unittest.main()
