<template>
  <div class="status-indicator" :class="`status--${status}`" :title="statusLabel">
    <span class="status-dot" />
    <span class="status-label">{{ statusLabel }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AppStatus } from '@/stores/app'

const props = withDefaults(defineProps<{ status?: AppStatus }>(), {
  status: 'idle'
})

const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    idle: '待命中',
    processing: '处理中',
    newMail: '新邮件'
  }
  return labels[props.status] || '待命中'
})
</script>

<style scoped>
.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-size: 11px;
  letter-spacing: 0.3px;
  color: var(--text-muted);
  text-transform: uppercase;
  transition: all var(--transition-base);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  transition: background var(--transition-base), box-shadow var(--transition-base);
}

.status--idle .status-dot {
  background: var(--status-idle);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.status--processing .status-dot {
  background: var(--status-processing);
  box-shadow: 0 0 6px rgba(234, 179, 8, 0.5);
  animation: pulse 1.2s ease-in-out infinite;
}

.status--newMail .status-dot {
  background: var(--status-newmail);
  box-shadow: 0 0 8px rgba(59, 130, 246, 0.5);
  animation: pulse 0.8s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
