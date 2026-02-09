import argparse
import json
import time

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a generation and poll its status.")
    parser.add_argument("--api", default="http://127.0.0.1:8000", help="Backend API base URL")
    parser.add_argument("--model-version-id", type=int, default=3)
    parser.add_argument("--prompt", default="a portrait photo of sks person")
    parser.add_argument("--negative-prompt", default="")
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--width", type=int, default=256)
    parser.add_argument("--height", type=int, default=256)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    parser.add_argument("--max-polls", type=int, default=60)
    args = parser.parse_args()

    client = httpx.Client(timeout=60.0)
    payload = {
        "model_version_id": args.model_version_id,
        "prompt": args.prompt,
        "negative_prompt": args.negative_prompt,
        "steps": args.steps,
        "width": args.width,
        "height": args.height,
    }

    gen = client.post(f"{args.api}/v1/generations", json=payload).json()
    gid = gen["id"]
    print("generation_id", gid)

    for _ in range(args.max_polls):
        g = client.get(f"{args.api}/v1/generations/{gid}").json()
        print("status", g.get("status"))
        if g.get("status") in ("completed", "failed"):
            print(json.dumps(g, indent=2))
            return
        time.sleep(args.poll_seconds)

    print("timed_out")
    print(json.dumps(client.get(f"{args.api}/v1/generations/{gid}").json(), indent=2))


if __name__ == "__main__":
    main()
