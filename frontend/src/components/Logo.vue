<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <defs v-if="gradient">
      <linearGradient :id="gid" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#3b82f6" />
        <stop offset="100%" stop-color="#6366f1" />
      </linearGradient>
    </defs>
    <g
      :stroke="gradient ? `url(#${gid})` : 'currentColor'"
      stroke-width="1.7"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      <!-- 山花屋顶 -->
      <path d="M3.2 9.6 12 4.2l8.8 5.4" />
      <!-- 檐梁 -->
      <path d="M5 11.4h14" />
      <!-- 立柱 -->
      <path d="M7.6 11.6v6.6M12 11.6v6.6M16.4 11.6v6.6" />
      <!-- 基座 -->
      <path d="M3.8 19.8h16.4" />
    </g>
  </svg>
</template>

<script setup>
defineProps({
  size: { type: [Number, String], default: 24 },
  gradient: { type: Boolean, default: false },
})

// 同页多处使用渐变时避免 id 冲突
const gid = `logo-grad-${Math.random().toString(36).slice(2, 8)}`
</script>
