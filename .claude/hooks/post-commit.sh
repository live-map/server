#!/bin/bash

# PostToolUse hook: Git commit 후 Obsidian 기록 요청
# JSON 구조화 출력을 사용해 Claude에게 직접 메시지 전달

# stdin에서 JSON 입력 읽기
input=$(cat)

# jq로 tool_name과 command 추출
tool_name=$(echo "$input" | jq -r '.tool_name // empty')
command=$(echo "$input" | jq -r '.tool_input.command // empty')
tool_response=$(echo "$input" | jq -r '.tool_response // empty')

# Bash 명령이 git commit을 포함하는지 확인
if [[ "$tool_name" == "Bash" ]] && [[ "$command" == *"git commit"* ]]; then
    # 커밋이 성공했는지 확인 (exit code 0)
    exit_code=$(echo "$tool_response" | jq -r '.exit_code // 0')

    if [[ "$exit_code" == "0" ]]; then
        # 오늘 날짜
        today=$(date +%Y-%m-%d)

        # JSON 구조화 출력으로 Claude에게 메시지 전달
        cat << EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PostToolUse",
    "additionalContext": "📷📝 Git commit 완료! Obsidian 기록을 작성해주세요.\n\n[1] After 스크린샷 캡처 (UI 변경 시):\n    - Before와 동일한 페이지 캡처\n    - 파일명: YYYY-MM-DD-HHMM-{page-name}-after.png\n    - 저장: /Users/iyeonsang/Desktop/obsidian/work/projects/livemap/screenshots/\n\n[2] Obsidian 커밋 기록 작성:\n    - 경로: /Users/iyeonsang/Desktop/obsidian/work/projects/livemap/commits/${today}.md\n    - 템플릿: /Users/iyeonsang/Desktop/obsidian/work/templates/commit-log.md\n    - 형식: Why(왜) → What(무엇을) → How(어떻게) → Result(결과) → 스크린샷"
  }
}
EOF
    fi
fi

exit 0
