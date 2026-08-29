# 0003. Use Static CLI Pipeline over Visual Workflow Engines

We decided to implement a Python CLI (`python -m src.cli`) rather than adopting workflow engines like n8n or Node-RED for V0.1. This avoids Docker/container socket security risks, permission issues, and server maintenance overhead. Reproducibility comes from the checked-in `pyproject.toml` and `uv.lock`.
