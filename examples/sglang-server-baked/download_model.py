import os
from huggingface_hub import snapshot_download


def main():
    model_id = os.environ.get("MODEL_ID")
    if not model_id:
        raise SystemExit("MODEL_ID env var is required at build time")

    revision = os.environ.get("MODEL_REVISION")
    local_dir = os.environ.get("LOCAL_MODEL_DIR", "/models")
    token = os.environ.get("HF_TOKEN")

    snapshot_download(
        repo_id=model_id,
        revision=revision,
        local_dir=local_dir,
        local_dir_use_symlinks=False,
        token=token,
        ignore_patterns=["*.safetensors.index.json", "*.md"],
    )


if __name__ == "__main__":
    main()
