# 0003. Use Static CLI Pipeline over Visual Workflow Engines

We use the local Python CLI and `bin/agent-listening` wrapper rather than a GUI,
workflow engine, Web server, or MCP server. A single process keeps the
integration surface small and makes the receipt/artifact boundary explicit;
reproducibility comes from the checked-in `pyproject.toml` and `uv.lock`.
