"""Normal headless CLI; JSON configurations are identical to web exports."""

import argparse
import asyncio
import json
import os
from pathlib import Path

from pydantic import ValidationError

from .config import GameConfig, ModelConfig, demo_config
from .personas import validate_persona
from .providers import HTTPProvider
from .runner import Runner
from .storage import Store


def main():
    parser = argparse.ArgumentParser(prog="clocktower")
    parser.add_argument("--data", type=Path, default=Path(os.getenv("CLOCKTOWER_DATA", "data")))
    sub = parser.add_subparsers(dest="command", required=True)
    web = sub.add_parser("web", help="Start the complete local web application")
    web.add_argument("--port", type=int, default=8000)
    run = sub.add_parser("run", help="Run a saved JSON configuration without a frontend")
    run.add_argument("config", type=Path)
    run.add_argument(
        "--mock", action="store_true", help="Override all providers with the offline demo policy"
    )
    demo = sub.add_parser("demo", help="Run an offline game or write an example config")
    demo.add_argument("--players", type=int, default=7, choices=range(5, 16))
    demo.add_argument("--write", type=Path)
    validate = sub.add_parser("validate", help="Validate configuration and persona references")
    validate.add_argument("config", type=Path)
    persona = sub.add_parser("persona", help="Create, list, and validate Markdown personas")
    psub = persona.add_subparsers(dest="operation", required=True)
    psub.add_parser("list")
    create = psub.add_parser("create")
    create.add_argument("name")
    create.add_argument("--from", dest="source", default="builtin:analyst")
    pv = psub.add_parser("validate")
    pv.add_argument("file", type=Path)
    models = sub.add_parser("models", help="List available models using backend credentials")
    models.add_argument("provider", choices=["openai", "anthropic", "einfra", "compatible"])
    models.add_argument("--endpoint")
    models.add_argument("--credential-env")
    args = parser.parse_args()
    store = Store(args.data)
    try:
        if args.command == "web":
            import uvicorn

            from .api import create_app

            uvicorn.run(create_app(args.data), host="127.0.0.1", port=args.port, access_log=False)
        elif args.command == "persona":
            if args.operation == "list":
                print(json.dumps(store.personas.list(), indent=2))
            elif args.operation == "validate":
                print("Valid:", validate_persona(args.file.read_text()))
            else:
                text = store.personas.read(args.source)
                lines = text.splitlines()
                lines[0] = "# " + args.name
                ref = store.personas.save("\n".join(lines) + "\n")
                print(store.personas.root / ref)
        elif args.command == "models":
            print(
                json.dumps(
                    asyncio.run(
                        HTTPProvider().models(
                            ModelConfig(
                                provider=args.provider,
                                base_url=args.endpoint,
                                credential_env=args.credential_env,
                            )
                        )
                    ),
                    indent=2,
                )
            )
        else:
            config = (
                demo_config(args.players)
                if args.command == "demo"
                else GameConfig.model_validate_json(args.config.read_text())
            )
            if args.command == "validate":
                for player in config.players:
                    store.personas.read(player.persona)
                print("Valid configuration")
                return
            if args.command == "demo" and args.write:
                args.write.write_text(config.model_dump_json(indent=2) + "\n")
                print(args.write)
                return
            if getattr(args, "mock", False):
                config.defaults = ModelConfig()
                for player in config.players:
                    player.model = {}
            runner = Runner(config, store)
            print(f"Run {runner.id}; saving to {store.path('runs', runner.id)}", flush=True)
            result = asyncio.run(runner.run())
            print(json.dumps(result["result"], indent=2))
    except (ValueError, FileNotFoundError) as exc:
        message = "; ".join(e["msg"] for e in exc.errors()) if isinstance(exc, ValidationError) else str(exc)
        parser.exit(2, f"Error: {message}\n")


if __name__ == "__main__":
    main()
