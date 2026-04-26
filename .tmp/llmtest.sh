#!/bin/sh
for MODEL in "z-ai/glm-4.5-air:free" "qwen/qwen3-coder:free" "minimax/minimax-m2.5:free" "minimax-m2.5:free" "trinity-large-preview"; do
    echo "== $MODEL =="
    START=$(date +%s)
    curl -sS -m 60 -o /tmp/resp.json -w "http_status=%{http_code} time=%{time_total}\n" \
        https://openrouter.ai/api/v1/chat/completions \
        -H "Authorization: Bearer $OPENROUTER_API_KEY" \
        -H "Content-Type: application/json" \
        -d "{\"model\":\"$MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"say hi in 2 words\"}],\"max_tokens\":20,\"stream\":false}"
    head -c 600 /tmp/resp.json
    echo
    echo
done
