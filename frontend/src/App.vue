<template>
  <div class="app-shell">
    <aside class="app-side">
      <h1 class="app-title">气象观测站网运维平台</h1>
      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          {{ item.label }}
        </RouterLink>
      </nav>
    </aside>
    <main class="app-main">
      <header class="app-head">
        <span class="head-desc">面向区域气象观测站网的站点入网、传感器检定、观测数据质控、供电通信保障与运维结算的一体化运行监控后台。</span>
        <span class="head-user">当前值班：{{ store.operator }} · {{ store.shiftLabel }}</span>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useSessionStore } from '@/stores/session'

const store = useSessionStore()

const navItems = [{ label: "运营概览", path: "/" }, { label: "观测站点", path: "/station" }, { label: "观测传感器", path: "/sensor" }, { label: "观测记录", path: "/observation" }, { label: "数据质控", path: "/quality" }, { label: "设备标定", path: "/calibration" }, { label: "数据传输", path: "/transmission" }, { label: "供电保障", path: "/power" }, { label: "站网布局", path: "/layout" }, { label: "巡检任务", path: "/inspection" }, { label: "故障处置", path: "/fault" }, { label: "备件器材", path: "/sparepart" }, { label: "元数据登记", path: "/metainfo" }, { label: "告警监测", path: "/alarm" }, { label: "通信设备", path: "/comm" }, { label: "服务保障", path: "/service" }, { label: "运维合同", path: "/contract" }, { label: "经费结算", path: "/settlement" }, { label: "人员培训", path: "/training" }]
</script>
