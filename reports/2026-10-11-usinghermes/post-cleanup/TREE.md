# 文档树 · AgentSkill-UsingHermes-skillweave

skills=39 · bytes=450067 · est_tokens=115062

```
.  [pack] bytes=1182641 fanout=6
  skills/  [category] bytes=450067 fanout=28
    skills/autonomous-ai-agents/  [category] bytes=109316 fanout=12
      skills/autonomous-ai-agents/gateway-session-list/  [skill] bytes=8225 fanout=19
      skills/autonomous-ai-agents/hermes-community-extensions/  [skill] bytes=8882 fanout=14
      skills/autonomous-ai-agents/hermes-mcp-server-integration/  [skill] bytes=5562 fanout=11
      skills/autonomous-ai-agents/hermes-profile-authoring/  [skill] bytes=8052 fanout=13
      skills/autonomous-ai-agents/hermes-profile-configuration/  [skill] bytes=16379 fanout=12
      skills/autonomous-ai-agents/hermes-profile-housekeeping/  [skill] bytes=17570 fanout=13
      skills/autonomous-ai-agents/hermes-projects/  [skill] bytes=6667 fanout=9
      skills/autonomous-ai-agents/hermes-pycache-cleanup/  [skill] bytes=3322 fanout=10
      skills/autonomous-ai-agents/hermes-skill-card-maintenance/  [skill] bytes=5639 fanout=7
      skills/autonomous-ai-agents/hermes-skills-management/  [skill] bytes=14037 fanout=13
      skills/autonomous-ai-agents/hermes-source-hotfix/  [skill] bytes=9322 fanout=7
      skills/autonomous-ai-agents/kimi-moonshot-brotli-fix/  [skill] bytes=5659 fanout=10
    skills/diagnose-a-failed-hermes-update/  [skill] bytes=9629 fanout=13
    skills/dispatch-work-to-another-profile/  [skill] bytes=9436 fanout=13
    skills/hermes-browser-lane-repair/  [skill] bytes=7085 fanout=8
    skills/hermes-desktop-plugins/  [skill] bytes=8849 fanout=8
    skills/hermes-session-routing-forensics/  [skill] bytes=14384 fanout=15
    skills/hermes-themes/  [skill] bytes=7119 fanout=9
    skills/install-a-hermes-plugin/  [skill] bytes=14382 fanout=16
    skills/install-hermes-skills/  [skill] bytes=18304 fanout=10
    skills/load-external-skill-index/  [skill] bytes=7921 fanout=11
    skills/maintain-hermes-desktop-app/  [skill] bytes=10817 fanout=10
    skills/maintain-hermes-gateway/  [skill] bytes=17441 fanout=16
    skills/maintain-hermes-memory/  [skill] bytes=19091 fanout=10
    skills/maintain-hermes-models/  [skill] bytes=12549 fanout=9
    skills/maintain-hermes-node/  [skill] bytes=8480 fanout=9
    skills/maintain-hermes-profile/  [skill] bytes=19723 fanout=14
    skills/maintain-hermes-profile-skill-parity/  [skill] bytes=13408 fanout=10
    skills/maintain-hermes-profiles/  [skill] bytes=11958 fanout=12
    skills/maintain-hermes-skill-cards/  [skill] bytes=7463 fanout=8
    skills/maintain-hermes-skills/  [skill] bytes=8936 fanout=6
    skills/manage-global-heartbeat/  [skill] bytes=10765 fanout=13
    skills/manage-hermes-cron-jobs/  [skill] bytes=16866 fanout=14
    skills/productivity/  [category] bytes=10599 fanout=1
      skills/productivity/session-librarian/  [skill] bytes=10599 fanout=10
    skills/recruit-learning-in-profile/  [skill] bytes=15791 fanout=10
    skills/recruit-learning-in-session/  [skill] bytes=16290 fanout=9
    skills/remove-a-hermes-plugin/  [skill] bytes=9343 fanout=7
    skills/remove-hermes-skills/  [skill] bytes=13944 fanout=10
    skills/update-hermes-skills/  [skill] bytes=20178 fanout=13
```

## 每层选择数（fanout>1）

```
   6  <pack>/
  28  skills/
  12  skills/autonomous-ai-agents/
```

## 孤儿文件 / 悬空引用

```
broken  skills/autonomous-ai-agents/gateway-session-list/ -> references/troubleshooting-pyc-cache.md
broken  skills/autonomous-ai-agents/hermes-profile-configuration/ -> references/new-profile-feishu-bot.md
broken  skills/autonomous-ai-agents/hermes-profile-housekeeping/ -> references/profile-context-file-edits.md
broken  skills/autonomous-ai-agents/hermes-pycache-cleanup/ -> references/stale-pyc-after-desktop-install.md
orphan  skills/autonomous-ai-agents/hermes-skill-card-maintenance/scripts/align_skill_card.py
orphan  skills/autonomous-ai-agents/hermes-source-hotfix/references/context-length-resolution.md
orphan  skills/autonomous-ai-agents/hermes-source-hotfix/references/moonshot-brotli-patch.md
orphan  skills/diagnose-a-failed-hermes-update/test-prompts.json
orphan  skills/diagnose-a-failed-hermes-update/test-results.md
broken  skills/diagnose-a-failed-hermes-update/ -> scripts/desktop-update/posix.sh
orphan  skills/dispatch-work-to-another-profile/test-prompts.json
orphan  skills/hermes-session-routing-forensics/test-prompts.json
orphan  skills/install-a-hermes-plugin/test-prompts.json
orphan  skills/install-hermes-skills/test-prompts.json
orphan  skills/load-external-skill-index/test-prompts.json
broken  skills/maintain-hermes-memory/ -> assets/template.html
orphan  skills/maintain-hermes-models/test-prompts.json
orphan  skills/maintain-hermes-models/test-results.md
broken  skills/maintain-hermes-node/ -> scripts/lib/node-bootstrap.sh
broken  skills/maintain-hermes-profile/ -> references/maintain-hermes-self-improvement-controls.md
broken  skills/maintain-hermes-profile/ -> references/maintain-hermes-skills-inventory-and-availability.md
orphan  skills/maintain-hermes-profile-skill-parity/scripts/where-a-profiles-skills-drift-from-their-repos.py
orphan  skills/maintain-hermes-profile-skill-parity/scripts/where-do-a-profiles-skills-come-from.py
orphan  skills/maintain-hermes-skills/test-prompts.json
broken  skills/maintain-hermes-skills/ -> references/install-hermes-skills-relocating-a-skill.md
orphan  skills/manage-global-heartbeat/test-prompts.json
orphan  skills/manage-global-heartbeat/test-results.md
orphan  skills/manage-hermes-cron-jobs/test-prompts.json
orphan  skills/manage-hermes-cron-jobs/test-results.md
orphan  skills/recruit-learning-in-profile/test-prompts.json
broken  skills/recruit-learning-in-profile/ -> references/install-hermes-skills-relocating-a-skill.md
broken  skills/recruit-learning-in-profile/ -> references/maintain-hermes-skills-authoring-conventions.md
broken  skills/recruit-learning-in-profile/ -> references/maintain-hermes-skills-inventory-and-availability.md
broken  skills/recruit-learning-in-profile/ -> references/maintain-hermes-skills-overlap-and-merge.md
orphan  skills/recruit-learning-in-session/test-prompts.json
orphan  skills/recruit-learning-in-session/test-results.md
broken  skills/recruit-learning-in-session/ -> assets/template.html
broken  skills/recruit-learning-in-session/ -> references/maintain-hermes-skill-curator.md
broken  skills/recruit-learning-in-session/ -> references/maintain-hermes-skills-authoring-conventions.md
orphan  skills/remove-a-hermes-plugin/test-prompts.json
orphan  skills/remove-a-hermes-plugin/test-results.md
orphan  skills/remove-hermes-skills/test-prompts.json
broken  skills/remove-hermes-skills/ -> references/install-hermes-skills-diagnosis.md
broken  skills/remove-hermes-skills/ -> references/install-hermes-skills-from-names.md
broken  skills/remove-hermes-skills/ -> references/maintain-hermes-skills-inventory-and-availability.md
broken  skills/remove-hermes-skills/ -> scripts/lock-provenance.py
orphan  skills/update-hermes-skills/test-prompts.json
broken  skills/update-hermes-skills/ -> references/install-hermes-skills-diagnosis.md
broken  skills/update-hermes-skills/ -> references/install-hermes-skills-from-names.md
broken  skills/update-hermes-skills/ -> references/install-hermes-skills-scan-gate.md
broken  skills/update-hermes-skills/ -> references/recruit-learning-in-session-routing.md
```
