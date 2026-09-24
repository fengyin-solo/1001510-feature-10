import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
const Station = () => import('@/views/station/index.vue')
const Sensor = () => import('@/views/sensor/index.vue')
const Observation = () => import('@/views/observation/index.vue')
const Quality = () => import('@/views/quality/index.vue')
const Calibration = () => import('@/views/calibration/index.vue')
const Transmission = () => import('@/views/transmission/index.vue')
const Power = () => import('@/views/power/index.vue')
const Layout = () => import('@/views/layout/index.vue')
const Inspection = () => import('@/views/inspection/index.vue')
const Fault = () => import('@/views/fault/index.vue')
const Sparepart = () => import('@/views/sparepart/index.vue')
const Metainfo = () => import('@/views/metainfo/index.vue')
const Alarm = () => import('@/views/alarm/index.vue')
const Comm = () => import('@/views/comm/index.vue')
const Service = () => import('@/views/service/index.vue')
const Contract = () => import('@/views/contract/index.vue')
const Settlement = () => import('@/views/settlement/index.vue')
const Training = () => import('@/views/training/index.vue')

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    { path: '/station', name: 'station', component: Station },
    { path: '/sensor', name: 'sensor', component: Sensor },
    { path: '/observation', name: 'observation', component: Observation },
    { path: '/quality', name: 'quality', component: Quality },
    { path: '/calibration', name: 'calibration', component: Calibration },
    { path: '/transmission', name: 'transmission', component: Transmission },
    { path: '/power', name: 'power', component: Power },
    { path: '/layout', name: 'layout', component: Layout },
    { path: '/inspection', name: 'inspection', component: Inspection },
    { path: '/fault', name: 'fault', component: Fault },
    { path: '/sparepart', name: 'sparepart', component: Sparepart },
    { path: '/metainfo', name: 'metainfo', component: Metainfo },
    { path: '/alarm', name: 'alarm', component: Alarm },
    { path: '/comm', name: 'comm', component: Comm },
    { path: '/service', name: 'service', component: Service },
    { path: '/contract', name: 'contract', component: Contract },
    { path: '/settlement', name: 'settlement', component: Settlement },
    { path: '/training', name: 'training', component: Training },
  ],
})

export default router
