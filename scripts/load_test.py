from __future__ import annotations

import argparse
import concurrent.futures
import json
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx


THREAD_LOCAL = threading.local()


def get_client(timeout: int) -> httpx.Client:
    client = getattr(THREAD_LOCAL, "client", None)
    if client is None:
        client = httpx.Client(timeout=timeout, trust_env=False)
        THREAD_LOCAL.client = client
    return client


def wait_ready(base_url: str) -> None:
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            with httpx.Client(timeout=1, trust_env=False) as client:
                if client.get(f"{base_url}/health").status_code == 200:
                    return
        except Exception:
            time.sleep(0.2)
    raise RuntimeError(f"server not ready: {base_url}")


def request_once(base_url: str, repo: Path, endpoint: str, index: int, timeout: int):
    started = time.perf_counter()
    try:
        client = get_client(timeout)
        if endpoint == "health":
            response = client.get(f"{base_url}/health")
        elif endpoint == "metrics":
            response = client.get(f"{base_url}/metrics")
        elif endpoint == "tasks":
            response = client.post(
                f"{base_url}/api/tasks",
                json={
                    "repo_path": str(repo),
                    "user_request": f"load test task {index}",
                    "run": False,
                },
            )
        else:
            raise ValueError(f"unknown endpoint: {endpoint}")
        return (time.perf_counter() - started) * 1000, response.status_code
    except Exception:
        return (time.perf_counter() - started) * 1000, 0


def run_case(base_url: str, repo: Path, endpoint: str, requests: int, concurrency: int, timeout: int) -> dict[str, object]:
    started = time.perf_counter()
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [
            pool.submit(request_once, base_url, repo, endpoint, index, timeout)
            for index in range(requests)
        ]
        for future in concurrent.futures.as_completed(futures, timeout=max(timeout * requests, 60)):
            results.append(future.result())

    elapsed = time.perf_counter() - started
    latencies = [item[0] for item in results]
    ok = sum(1 for _, status_code in results if 200 <= status_code < 300)
    codes: dict[str, int] = {}
    for _, status_code in results:
        codes[str(status_code)] = codes.get(str(status_code), 0) + 1

    return {
        "endpoint": endpoint,
        "requests": requests,
        "concurrency": concurrency,
        "ok": ok,
        "failed": requests - ok,
        "codes": codes,
        "error_rate_percent": round((requests - ok) / requests * 100, 2),
        "elapsed_s": round(elapsed, 3),
        "qps": round(requests / elapsed, 2),
        "avg_ms": round(statistics.mean(latencies), 2),
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(sorted(latencies)[max(0, int(requests * 0.95) - 1)], 2),
        "max_ms": round(max(latencies), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local CodePilot HTTP load test.")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--requests", type=int, default=300)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--endpoint", choices=["health", "metrics", "tasks"], default="tasks")
    parser.add_argument("--reuse-server", action="store_true")
    args = parser.parse_args()

    repo = args.repo.resolve()
    base_url = f"http://{args.host}:{args.port}"
    server = None
    if not args.reuse_server:
        server = subprocess.Popen(
            [
                sys.executable,
                "main.py",
                "serve",
                "--host",
                args.host,
                "--port",
                str(args.port),
            ],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    try:
        wait_ready(base_url)
        result = run_case(base_url, repo, args.endpoint, args.requests, args.concurrency, args.timeout)
        print(json.dumps(result, ensure_ascii=False))
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


if __name__ == "__main__":
    main()
