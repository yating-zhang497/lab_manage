<template>
  <el-row :gutter="12">
    <el-col
      v-for="f in visibleFields"
      :key="f.key"
      :span="isLongText(f) ? 24 : 12"
    >
      <el-form-item :label="f.label" :required="requiredKeys.includes(f.key)">
        <el-input
          v-if="f.dtype === 'text' && isLongText(f)"
          v-model="model[f.key]"
          type="textarea"
          :rows="2"
        />
        <el-input
          v-else-if="f.dtype === 'text'"
          v-model="model[f.key]"
        />
        <el-input-number
          v-else-if="f.dtype === 'number'"
          v-model="model[f.key]"
          :controls="false"
          style="width: 100%"
        />
        <el-date-picker
          v-else-if="f.dtype === 'date'"
          v-model="model[f.key]"
          type="date"
          value-format="YYYY-MM-DD"
          style="width: 100%"
        />
        <el-switch v-else-if="f.dtype === 'boolean'" v-model="model[f.key]" />
        <el-select v-else v-model="model[f.key]" clearable style="width: 100%">
          <el-option v-for="o in f.options" :key="o" :value="o" />
        </el-select>
      </el-form-item>
    </el-col>
  </el-row>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  fields: { type: Array, default: () => [] },
  model: { type: Object, required: true },
  // 必填字段key列表（唯一标识），显示红色星号
  requiredKeys: { type: Array, default: () => [] },
  // 表单中不渲染的字段key（如由专门区块维护的字段）
  excludeKeys: { type: Array, default: () => [] },
})

const visibleFields = computed(() =>
  props.fields.filter((f) => !props.excludeKeys.includes(f.key))
)

// 适合多行输入的长文本字段
const LONG_TEXT_KEYS = [
  'notes', 'targets', 'targets_done', 'research_direction',
  'acknowledgements', 'authors_raw', 'summary', 'title',
  'corresponding_text',
]

function isLongText(f) {
  return f.dtype === 'text' && LONG_TEXT_KEYS.includes(f.key)
}
</script>
