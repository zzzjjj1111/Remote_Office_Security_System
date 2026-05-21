<script setup>
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView />
</template>

<style>
/* 全局充实，清空原有的居中限制 */
#app {
  width: 100vw;
  height: 100vh;
  margin: 0;
  padding: 0;
  max-width: none;
}
</style>
