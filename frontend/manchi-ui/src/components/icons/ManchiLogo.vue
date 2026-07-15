<template>
  <div class="manchi-logo" :style="{ width: size + 'px', height: size + 'px' }">
    <svg
      :width="size"
      :height="size"
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      class="logo-svg"
    >
      <defs>
        <linearGradient id="lg" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#4FC3F7" />
          <stop offset="50%" stop-color="#7C3AED" />
          <stop offset="100%" stop-color="#4FC3F7" />
        </linearGradient>
      </defs>

      <!-- Terminal cursor accent -->
      <rect x="3" y="3" width="5" height="5" rx="1.5" fill="url(#lg)" opacity="0.5" class="cursor-accent" />

      <!-- M shape -->
      <path
        d="M8 32 L14 8 L20 22 L26 8 L32 32"
        stroke="url(#lg)"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
        class="m-path"
      />

      <!-- Terminal baseline -->
      <line x1="8" y1="36" x2="32" y2="36" stroke="#4FC3F7" stroke-width="1.2" opacity="0.25" class="baseline" />
    </svg>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 32 })
</script>

<style scoped>
.manchi-logo {
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-svg {
  overflow: visible;
}

/* M path glow animation */
.m-path {
  filter: drop-shadow(0 0 2px rgba(79, 195, 247, 0.3));
  animation: logo-glow 3s ease-in-out infinite;
}

@keyframes logo-glow {
  0%, 100% {
    filter: drop-shadow(0 0 2px rgba(79, 195, 247, 0.2));
    stroke-opacity: 0.9;
  }
  50% {
    filter: drop-shadow(0 0 6px rgba(79, 195, 247, 0.5)) drop-shadow(0 0 12px rgba(124, 58, 237, 0.2));
    stroke-opacity: 1;
  }
}

/* Cursor blink */
.cursor-accent {
  animation: cursor-blink 1.2s step-end infinite;
}

@keyframes cursor-blink {
  0%, 100% { opacity: 0.5; }
  50% { opacity: 0.15; }
}

/* Baseline pulse */
.baseline {
  animation: baseline-pulse 2s ease-in-out infinite;
}

@keyframes baseline-pulse {
  0%, 100% { opacity: 0.15; }
  50% { opacity: 0.4; }
}
</style>
