import argparse
import json
import time

import httpx


def main() -> None:
    p = argparse.ArgumentParser(description="Smoke test: create model->train->generate.")
    p.add_argument("--api", default="http://127.0.0.1:8000")
    p.add_argument("--person-id", type=int, default=1)
    p.add_argument("--name", default="smoke-tiny")
    p.add_argument("--base-model-name", default="hf-internal-testing/tiny-stable-diffusion-pipe")
    p.add_argument("--trigger-token", default="sks person")
    p.add_argument("--steps", type=int, default=1)
    p.add_argument("--rank", type=int, default=2)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--resolution", type=int, default=256)
    p.add_argument("--poll-seconds", type=float, default=3.0)
    p.add_argument("--max-polls", type=int, default=200)
    args = p.parse_args()

    client = httpx.Client(timeout=60.0)

    model = client.post(
        f"{args.api}/v1/models",
        json={
            "person_id": args.person_id,
            "name": args.name,
            "base_model_name": args.base_model_name,
            "trigger_token": args.trigger_token,
            "train_config": {
                "steps": args.steps,
                "learning_rate": args.learning_rate,
                "rank": args.rank,
                "resolution": args.resolution,
            },
        },
    ).json()
    model_id = model["id"]
    print("model_id", model_id)

    version_id = None
    status = None
    for _ in range(args.max_polls):
        m = client.get(f"{args.api}/v1/models/{model_id}").json()
        versions = m.get("versions") or []
        if versions:
            v = versions[0]
            version_id = v.get("id")
            status = v.get("status")
            print("train_status", status, "version_id", version_id)
            if status in ("completed", "failed"):
                if v.get("error_message"):
                    print("train_error", v.get("error_message"))
                break
        time.sleep(args.poll_seconds)

    if status != "completed" or not version_id:
        print("training_not_completed")
        return

    gen = client.post(
        f"{args.api}/v1/generations",
        json={
            "model_version_id": version_id,
            "prompt": f"portrait photo of {args.trigger_token}",
            "negative_prompt": "",
            "steps": 5,
            "width": 256,
            "height": 256,
        },
    ).json()
    gen_id = gen["id"]
    print("generation_id", gen_id)

    for _ in range(args.max_polls):
        g = client.get(f"{args.api}/v1/generations/{gen_id}").json()
        print("gen_status", g.get("status"))
        if g.get("status") in ("completed", "failed"):
            print(json.dumps(g, indent=2))
            break
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    main()

