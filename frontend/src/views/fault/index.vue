<template>
  <section class="page" data-module="fault">
    <header class="page-head">
      <div>
        <h2>故障处置管理</h2>
        <p class="page-desc">维护故障记录，围绕故障编号、涉及站点、故障现象、发生时刻做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记故障记录</button>
        <button class="btn" type="button" @click="exportRows">导出故障处置清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="filter-bar" @submit.prevent="submitCreate">
      <label v-for="field in createFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="createForm[field]" :placeholder="`请输入${field}`" />
      </label>
      <button class="btn primary" type="submit">提交登记</button>
      <button class="btn ghost" type="button" @click="showCreate = false">取消</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <label class="filter-item">
        <span>故障状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      <button class="btn" :class="{ primary: onlyOverdue }" type="button" @click="toggleOverdue">
        仅看超期故障
      </button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td
            v-for="column in columns"
            :key="column"
            :class="{ 'overdue-cell': column === '是否超期' && row[column] === '是' }"
          >
            {{ row[column] ?? '—' }}
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无故障处置数据，可先登记故障记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条故障处置记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/fault'
const columns = ["故障编号", "涉及站点", "故障现象", "发生时刻", "影响要素", "处置人员", "恢复时刻", "故障状态", "处置时长", "是否超期", "挂起原因", "重复报障次数"]
const actions = ["派单处置", "确认恢复", "挂起故障"]
const statuses = ["待派单", "处置中", "已恢复", "已挂起"]
const createFields = ["故障编号", "涉及站点", "故障现象", "发生时刻", "影响要素", "处置人员"]
const filterParamMap: Record<string, string> = { 故障编号: 'keyword', 涉及站点: 'station', 故障现象: 'phenomenon' }

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = ["故障编号", "涉及站点", "故障现象"]
const statusFilter = ref('')
const onlyOverdue = ref(false)
const showCreate = ref(false)
const createForm = ref<Record<string, string>>({})
const summary = ref<Record<string, number>>({})

const stats = computed(() => [
  { label: '待派单故障', value: summary.value['待派单'] ?? 0 },
  { label: '处置中故障', value: summary.value['处置中'] ?? 0 },
  { label: '超期件数', value: summary.value['超期件数'] ?? 0 },
])

function resetFilters() {
  filters.value = {}
  statusFilter.value = ''
  onlyOverdue.value = false
  void reload()
}

function toggleOverdue() {
  onlyOverdue.value = !onlyOverdue.value
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  showCreate.value = true
}

function formatNow() {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm.value } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '故障记录登记失败')
    }
    noticeMessage.value = payload.message || '故障记录已登记'
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障记录登记失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const values: Record<string, string> = { action }
  if (action === '挂起故障') {
    const reason = window.prompt(`请填写故障 ${row['故障编号'] ?? row.id} 的挂起原因（必填）`)
    if (reason === null) {
      return
    }
    values['挂起原因'] = reason
  }
  if (action === '确认恢复') {
    const moment = window.prompt('请确认恢复时刻（YYYY-MM-DD HH:MM）', formatNow())
    if (moment === null) {
      return
    }
    values['恢复时刻'] = moment
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      throw new Error(payload.message || '故障处置动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message || `故障记录已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障处置操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const params = new URLSearchParams()
  for (const field of filterFields) {
    const value = (filters.value[field] ?? '').trim()
    if (value) {
      params.set(filterParamMap[field], value)
    }
  }
  if (statusFilter.value) {
    params.set('status', statusFilter.value)
  }
  if (onlyOverdue.value) {
    params.set('overdue', 'true')
  }
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      throw new Error('故障记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    summary.value = payload.summary ?? {}
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '故障处置列表读取失败'
  }
}

onMounted(reload)
</script>
