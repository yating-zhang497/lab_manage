<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="title"
    width="660px"
    @close="reset"
  >
    <div style="margin-bottom: 10px; display: flex; align-items: center; gap: 10px">
      <el-button v-if="templateUrl" size="small" @click="downloadTemplate">下载导入模板</el-button>
    </div>

    <el-upload
      ref="uploadRef"
      drag
      :auto-upload="false"
      :limit="1"
      :accept="accept"
      :on-change="onFile"
      :on-remove="() => (file = null)"
      :on-exceed="onExceed"
    >
      <div style="padding: 8px 0">
        <p>将文件拖到此处，或<em>点击选择</em></p>
      </div>
    </el-upload>

    <div style="margin-top: 12px; text-align: right">
      <el-button type="primary" :loading="uploading" :disabled="!file" @click="doImport">开始导入</el-button>
    </div>

    <div v-if="report" style="margin-top: 14px">
      <el-alert
        :title="`导入完成：成功 ${report.ok_count} 条，失败 ${report.fail_count} 条`"
        :type="report.fail_count ? 'warning' : 'success'"
        :closable="false"
      />
      <el-table v-if="report.errors.length" :data="report.errors.map((e, i) => ({ i: i + 1, e }))" size="small" max-height="240" style="margin-top: 8px">
        <el-table-column prop="e" label="错误明细" />
      </el-table>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import api, { downloadFile } from '../api'

const props = defineProps({
  visible: Boolean,
  title: String,
  uploadUrl: { type: String, required: true },
  templateUrl: { type: String, default: '' },
  templateName: { type: String, default: 'template.xlsx' },
  accept: { type: String, default: '.csv,.xlsx,.xls' },
})
const emit = defineEmits(['update:visible', 'done'])

const file = ref(null)
const uploading = ref(false)
const report = ref(null)
const uploadRef = ref(null)

function onFile(f) {
  file.value = f.raw
}
function onExceed() {
  ElMessage.warning('每次只能选择一个文件，请先移除')
}
function reset() {
  file.value = null
  report.value = null
  uploading.value = false
  uploadRef.value?.clearFiles()
}

async function downloadTemplate() {
  await downloadFile(props.templateUrl, props.templateName)
}

async function doImport() {
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    const { data } = await api.post(props.uploadUrl, fd)
    report.value = data
    if (data.ok_count > 0) {
      emit('done')
      file.value = null
      uploadRef.value?.clearFiles()
    }
  } finally {
    uploading.value = false
  }
}
</script>

