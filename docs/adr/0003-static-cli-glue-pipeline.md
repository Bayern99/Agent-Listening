# 0003. Use Static CLI Pipeline over Visual Workflow Engines

We decided to implement a pure CLI glue runner and transformation script (`run_analysis.sh` / Python builder) rather than adopting workflow engines like n8n or Node-RED for V0.1. This eliminates Docker/container socket security risks, permission issues, and server maintenance overhead while ensuring total portability and local reproducibility.
