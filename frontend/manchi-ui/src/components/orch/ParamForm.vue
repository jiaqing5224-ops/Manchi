<script setup lang="ts">
import { reactive, watch } from 'vue'

interface ParamDef {
  type: 'string' | 'number' | 'boolean' | 'select' | 'textarea' | 'file'
  label?: string
  default?: any
  required?: boolean
  description?: string
  options?: string[]
}

const props = defineProps<{
  paramsDef: Record<string, ParamDef>
  modelValue: Record<string, any>
}>()

const emit = defineEmits<{ 'update:modelValue': [Record<string, any>] }>()

function defaultForType(t: string): any {
  if (t === 'boolean') return false
  if (t === 'number') return 0
  return ''
}

const local = reactive<Record<string, any>>({})

function initFromDef() {
  for (const k in props.paramsDef) {
    if (!(k in local)) {
      const def = props.paramsDef[k]
      local[k] = k in props.modelValue ? props.modelValue[k] : (def.default ?? defaultForType(def.type))
    }
  }
}

initFromDef()
watch(() => props.paramsDef, initFromDef, { deep: true })

function emitChange() {
  emit('update:modelValue', JSON.parse(JSON.stringify(local)))
}
</script>

<template>
  <div class="param-form">
    <div v-for="(def, key) in paramsDef" :key="key" class="param-row">
      <label class="mini-label">
        {{ def.label || key }}<span v-if="def.required" class="req">*</span>
      </label>
      <textarea
        v-if="def.type === 'textarea'"
        class="fld-textarea"
        v-model="local[key]"
        @input="emitChange"
        :placeholder="def.description || ''"
      ></textarea>
      <input
        v-else-if="def.type === 'number'"
        type="number"
        class="fld-input"
        v-model.number="local[key]"
        @input="emitChange"
      />
      <input
        v-else-if="def.type === 'boolean'"
        type="checkbox"
        class="fld-check"
        v-model="local[key]"
        @change="emitChange"
      />
      <select
        v-else-if="def.type === 'select'"
        class="fld-input"
        v-model="local[key]"
        @change="emitChange"
      >
        <option v-for="opt in (def.options || [])" :key="opt" :value="opt">{{ opt }}</option>
      </select>
      <input
        v-else-if="def.type === 'file'"
        class="fld-input"
        v-model="local[key]"
        @input="emitChange"
        placeholder="文件路径"
      />
      <input
        v-else
        class="fld-input"
        v-model="local[key]"
        @input="emitChange"
        :placeholder="def.description || ''"
      />
      <div v-if="def.description && def.type !== 'textarea'" class="param-desc">
        {{ def.description }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.param-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.param-row {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.req {
  color: #ef4444;
  margin-left: 2px;
}
.param-desc {
  font-size: 11px;
  color: #94a3b8;
}
.fld-check {
  width: 16px;
  height: 16px;
}
</style>
