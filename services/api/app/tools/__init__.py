"""Agent action tools — the bridge between agent chat and AgentPulse operations.

Each tool is an OpenAI/DeepSeek function-calling schema + a Python handler
that calls internal service functions directly (no HTTP). When an employee
decides to call a tool, the handler executes it and returns structured results
that feed back into the conversation.
"""
