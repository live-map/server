#!/bin/bash

# PreToolUse hook: Git commit 전 Before 스크린샷 요청
# JSON 구조화 출력을 사용해 Claude에게 직접 메시지 전달

# stdin에서 JSON 입력 읽기
input=$(cat)

# jq로 tool_name과 command 추출
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
command=$(echo "$input" | jq -r '.tool_input.command // empty')

# Bash 명령이 git commit을 포함하는지 확인
if [[ "$tool_name" == "Bash" ]] && [[ "$command" == *"git commit"* ]]; then
    # JSON 구조화 출력으로 Claude에게 메시지 전달
    cat << 'EOF'
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "additionalContext": "📷 BEFORE SCREENSHOT REQUIRED\n\n커밋 전에 UI 변경사항이 있으면 Before 스크린샷을 먼저 캡처하세요.\n\n1. 변경된 파일에서 UI 관련 파일 확인\n2. 해당 페이지 URL로 이동하여 스크린샷 캡처\n3. 저장 위치: /Users/iyeonsang/Desktop/obsidian/work/projects/livemap/screenshots/\n4. 파일명: YYYY-MM-DD-HHMM-{page-name}-before.png"
  }
}
EOF
fi

exit 0
