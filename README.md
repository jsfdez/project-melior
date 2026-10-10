# project-melior
Hacktoberfest 2026 project 

## Use Claude Code

```
export ANTHROPIC_BASE_URL=https://bubbly-vermilion.netbird.apps.buildinmadrid.dev
export ANTHROPIC_API_KEY=none
claude --model=gemma-4-26b-a4b
```

## Program constraints

- Use Python
- Use Gemma-4-26b-a4b

## To make LLM requests

```
curl https://bubbly-vermilion.netbird.apps.buildinmadrid.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.5",
    "messages": [
      { "role": "user", "content": "What is NetBird Agent Network?" }
    ]
  }'
```
