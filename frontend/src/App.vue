<template>
  <router-view />
</template>

<style>
/* ============================================================
   Design System — 简约 · 丝滑
   ============================================================ */
:root {
  /* Brand palette — override Element Plus */
  --el-color-primary: #3b82f6;
  --el-color-primary-light-3: #76a8f9;
  --el-color-primary-light-5: #9dc0fb;
  --el-color-primary-light-7: #c4dafc;
  --el-color-primary-light-8: #d8e6fd;
  --el-color-primary-light-9: #ebf3fe;
  --el-color-primary-dark-2: #2f68c5;

  --el-color-success: #10b981;
  --el-color-success-light-3: #58cea7;
  --el-color-success-light-5: #88dcc0;
  --el-color-success-light-7: #b7ead9;
  --el-color-success-light-8: #cff1e6;
  --el-color-success-light-9: #e7f8f2;
  --el-color-success-dark-2: #0d9467;

  --el-color-warning: #f59e0b;
  --el-color-warning-light-3: #f8bb54;
  --el-color-warning-light-5: #face85;
  --el-color-warning-light-7: #fce2b6;
  --el-color-warning-light-8: #fdecce;
  --el-color-warning-light-9: #fef5e7;
  --el-color-warning-dark-2: #c47e09;

  --el-color-danger: #ef4444;
  --el-color-danger-light-3: #f47c7c;
  --el-color-danger-light-5: #f7a2a2;
  --el-color-danger-light-7: #fac7c7;
  --el-color-danger-light-8: #fcdada;
  --el-color-danger-light-9: #fdecec;
  --el-color-danger-dark-2: #bf3636;

  --el-color-error: #ef4444;
  --el-color-error-light-3: #f47c7c;
  --el-color-error-light-5: #f7a2a2;
  --el-color-error-light-7: #fac7c7;
  --el-color-error-light-8: #fcdada;
  --el-color-error-light-9: #fdecec;
  --el-color-error-dark-2: #bf3636;

  /* Neutrals */
  --el-text-color-primary: #1f2937;
  --el-text-color-regular: #4b5563;
  --el-text-color-secondary: #6b7280;
  --el-text-color-placeholder: #9ca3af;
  --el-border-color: #e5e7eb;
  --el-border-color-light: #eceef2;
  --el-border-color-lighter: #f0f1f5;
  --el-border-color-extra-light: #f5f6f8;
  --el-fill-color: #f3f4f6;
  --el-fill-color-light: #f5f7fa;
  --el-fill-color-lighter: #fafbfc;
  --el-bg-color-page: #f5f6fa;
  --el-border-radius-base: 8px;
  --el-border-radius-small: 6px;
  --el-font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC',
    'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;

  --el-box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08), 0 2px 6px rgba(15, 23, 42, 0.04);
  --el-box-shadow-light: 0 4px 12px rgba(15, 23, 42, 0.06);

  --el-transition-duration: 0.22s;
  --el-transition-function-ease-in-out-bezier: cubic-bezier(0.4, 0, 0.2, 1);

  /* semantic tokens */
  --hpgc-primary: #3b82f6;
  --hpgc-primary-soft: #ebf3fe;
  --hpgc-primary-dark: #2f68c5;
  --hpgc-success: #10b981;
  --hpgc-warning: #f59e0b;
  --hpgc-danger: #ef4444;
  --hpgc-info: #94a3b8;

  /* CCF Classification */
  --hpgc-ccf-a: #d0342c;
  --hpgc-ccf-a-bg: #fdf0ef;
  --hpgc-ccf-b: #e65c00;
  --hpgc-ccf-b-bg: #fdf4ec;
  --hpgc-ccf-c: #2980b9;
  --hpgc-ccf-c-bg: #eff6fc;

  /* Status */
  --hpgc-status-active: #0f9d6e;
  --hpgc-status-active-bg: #e7f8f2;
  --hpgc-status-graduated: #94a3b8;
  --hpgc-status-graduated-bg: #f4f5f7;
  --hpgc-status-pending: #d97706;
  --hpgc-status-pending-bg: #fef5e7;

  /* Sidebar */
  --hpgc-sidebar-bg: #171d2b;
}

body {
  margin: 0;
  background: var(--el-bg-color-page);
  font-family: var(--el-font-family);
  color: var(--el-text-color-primary);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

::selection {
  background: rgba(59, 130, 246, 0.18);
}

html {
  scroll-behavior: smooth;
}

/* ========================
   Card — flat & quiet
   ======================== */
.el-card {
  border-radius: 12px !important;
  border: 1px solid #eef0f4 !important;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.03) !important;
  transition: box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.el-card__header {
  padding: 14px 20px;
  border-bottom: 1px solid #f0f1f5;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}
.el-card__body {
  padding: 16px 20px;
}

/* ========================
   Table
   ======================== */
.el-table {
  --el-table-border-color: #f0f1f5;
  --el-table-header-bg-color: #f8f9fb;
  --el-table-header-text-color: #6b7280;
  --el-table-text-color: #374151;
  --el-table-row-hover-bg-color: #f5f9ff;
  --el-table-current-row-bg-color: #ebf3fe;
  font-size: 13px;
  border-radius: 10px;
  overflow: hidden;
}
.el-table th.el-table__cell {
  font-weight: 600;
  font-size: 12.5px;
}
.el-table td.el-table__cell,
.el-table th.el-table__cell.is-leaf {
  border-bottom: 1px solid #f2f3f7;
}
.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell {
  background: #fafbfc;
}
.el-table .cell {
  line-height: 1.65;
}
.sort-header {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  cursor: pointer;
  user-select: none;
}
.sort-badge {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  color: var(--el-color-primary);
  font-weight: 600;
  min-width: 14px;
}
.result-count {
  font-size: 12.5px;
  color: #6b7280;
  white-space: nowrap;
  margin-right: 4px;
}

/* ========================
   Tag
   ======================== */
.el-tag {
  border-radius: 6px !important;
  font-weight: 500;
}

/* ========================
   Button — soft press
   ======================== */
.el-button {
  border-radius: 8px !important;
  font-weight: 500;
  transition: background-color 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    border-color 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    color 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.18s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.1s ease !important;
}
.el-button:not(.is-disabled):active {
  transform: scale(0.97);
}
.el-button--primary:not(.is-plain):not(.is-text):not(.is-link):not(.is-disabled) {
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.28);
}
.el-button--primary:not(.is-plain):not(.is-text):not(.is-link):not(.is-disabled):hover {
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.35);
}

/* ========================
   Input & Select — calm focus ring
   ======================== */
.el-input__wrapper,
.el-select__wrapper {
  border-radius: 8px !important;
  transition: box-shadow 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.el-input__wrapper.is-focus,
.el-select__wrapper.is-focused {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset,
    0 0 0 3px rgba(59, 130, 246, 0.12) !important;
}
.el-textarea__inner {
  border-radius: 8px !important;
}
.el-textarea__inner:focus {
  box-shadow: 0 0 0 1px var(--el-color-primary) inset,
    0 0 0 3px rgba(59, 130, 246, 0.12) !important;
}

/* ========================
   Dialog — smooth entrance
   ======================== */
.el-dialog {
  border-radius: 16px !important;
  overflow: hidden;
}
.el-dialog__title {
  font-size: 16px;
  font-weight: 600;
  color: #111827;
}
.el-dialog__body {
  color: var(--el-text-color-regular);
}
.el-overlay {
  background-color: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(2px);
}
.dialog-fade-enter-active {
  animation: hpgc-overlay-in 0.24s ease both !important;
}
.dialog-fade-enter-active .el-dialog {
  animation: hpgc-dialog-in 0.32s cubic-bezier(0.16, 1, 0.3, 1) both !important;
}
.dialog-fade-leave-active {
  animation: hpgc-overlay-out 0.18s ease both !important;
}
.dialog-fade-leave-active .el-dialog {
  animation: hpgc-dialog-out 0.18s ease both !important;
}
@keyframes hpgc-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes hpgc-overlay-out {
  from { opacity: 1; }
  to { opacity: 0; }
}
@keyframes hpgc-dialog-in {
  from { opacity: 0; transform: translateY(14px) scale(0.97); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes hpgc-dialog-out {
  from { opacity: 1; transform: scale(1); }
  to { opacity: 0; transform: scale(0.97); }
}

/* ========================
   Drawer
   ======================== */
.el-drawer {
  --el-drawer-padding-primary: 20px;
}
.el-drawer__header {
  border-bottom: 1px solid #f0f1f5;
  margin-bottom: 0;
  padding: 17px 20px;
  color: #111827;
  font-weight: 600;
  font-size: 15px;
}
.el-drawer__header .el-drawer__title {
  font-weight: 600;
  font-size: 15px;
  color: #111827;
}
.el-drawer__body {
  padding: 18px 20px 24px;
}

/* ========================
   Message / MessageBox / Notification
   ======================== */
.el-message {
  border-radius: 10px;
  border: none;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.1);
}
.el-message-box {
  border-radius: 14px;
}
.el-message-box__title {
  font-weight: 600;
}
.el-notification {
  border-radius: 12px;
}

/* ========================
   Popper (select / dropdown / date)
   ======================== */
.el-popper.is-light {
  border-radius: 10px;
  border-color: #eceef2;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.1), 0 2px 6px rgba(15, 23, 42, 0.04);
}
.el-select-dropdown__item {
  transition: background-color 0.12s, color 0.12s;
}
.el-select-dropdown__item.is-selected {
  font-weight: 600;
}
.el-dropdown-menu {
  padding: 6px;
}
.el-dropdown-menu__item {
  border-radius: 6px;
  transition: background-color 0.12s, color 0.12s;
}
.el-dropdown-menu__item:not(.is-disabled):hover {
  background: #f5f7fa;
  color: var(--el-color-primary);
}
.el-popper.is-dark {
  border-radius: 8px;
  background: #273244;
  border-color: #273244;
  font-size: 12.5px;
}

/* ========================
   Pagination
   ======================== */
.el-pagination {
  --el-pagination-button-bg-color: transparent;
  font-weight: 500;
}
.el-pagination .btn-prev,
.el-pagination .btn-next,
.el-pagination .el-pager li {
  border-radius: 6px;
  transition: background-color 0.15s, color 0.15s;
}
.pagination {
  display: flex;
  justify-content: flex-end;
  padding: 12px 4px 0;
}

/* ========================
   Descriptions (detail drawers)
   ======================== */
.el-descriptions {
  --el-descriptions-table-border: 1px solid #f0f1f5;
}
.el-descriptions__label {
  color: #6b7280 !important;
  font-weight: 500 !important;
}
.el-descriptions__label.is-bordered-label {
  background: #fafbfc;
}

/* ========================
   Form / Tabs / Loading
   ======================== */
.el-form-item__label {
  color: #4b5563;
  font-weight: 500;
}
.el-tabs__item {
  transition: color 0.2s;
}
.el-tabs__active-bar {
  transition: transform 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
}
.el-loading-mask {
  background-color: rgba(255, 255, 255, 0.65);
  backdrop-filter: blur(2px);
  border-radius: 10px;
  transition: opacity 0.25s;
}
.el-switch {
  --el-switch-on-color: var(--el-color-primary);
}

/* Section headings in detail views */
h4 {
  color: #1f2937;
  font-size: 14px;
  font-weight: 600;
  margin: 22px 0 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f0f1f5;
}

/* ========================
   Scrollbar
   ======================== */
* {
  scrollbar-width: thin;
  scrollbar-color: #d6dae2 transparent;
}
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: #d6dae2;
  border-radius: 3px;
}
::-webkit-scrollbar-thumb:hover {
  background: #b9bec8;
}

/* ========================
   Route transition — 丝滑切页
   ======================== */
.page-enter-active {
  transition: opacity 0.25s ease, transform 0.25s cubic-bezier(0.25, 0.8, 0.35, 1);
}
.page-leave-active {
  transition: opacity 0.12s ease;
}
.page-enter-from {
  opacity: 0;
  transform: translateY(10px);
}
.page-leave-to {
  opacity: 0;
}

/* ========================
   Toolbar (list pages)
   ======================== */
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px 16px;
  flex-wrap: wrap;
}
.toolbar-filters {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 10px;
}
.toolbar-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-left: auto;
}
/* 用 gap 控制间距，去掉 Element 默认的相邻按钮 margin */
.toolbar-actions .el-button + .el-button {
  margin-left: 0;
}
.tb-divider {
  width: 1px;
  height: 18px;
  background: #e8eaef;
  margin: 0 3px;
}
.tb-search {
  width: 210px;
}
.clickable-link {
  color: var(--el-color-primary);
  cursor: pointer;
  transition: color 0.15s;
}
.clickable-link:hover {
  color: var(--hpgc-primary-dark);
  text-decoration: underline;
}

/* ========================
   Shared Component Styles
   ======================== */
.filter-card {
  position: sticky;
  top: 0;
  z-index: 9;
  margin-bottom: 14px;
  border-radius: 12px !important;
  background: #fff;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.muted {
  color: #9ca3af;
  font-size: 12px;
}

.extract-box {
  margin-top: 10px;
  padding: 12px;
  background: var(--hpgc-status-active-bg);
  border-radius: 10px;
  border: 1px solid #d3f0e3;
}

.funding-text {
  white-space: pre-wrap;
  background: #fff;
  padding: 8px 10px;
  border-radius: 8px;
  max-height: 180px;
  overflow: auto;
  font-size: 13px;
  border: 1px solid #e6e9ef;
}

.drop-zone {
  padding: 34px 20px;
  text-align: center;
  border: 1.5px dashed #dde1e8;
  border-radius: 12px;
  background: #fafbfc;
  color: #6b7280;
  transition: border-color 0.2s, background-color 0.2s, color 0.2s;
}
.drop-zone.is-dragover {
  border-color: var(--el-color-primary);
  background: var(--hpgc-primary-soft);
  color: var(--el-color-primary);
}
.drop-zone .drop-icon {
  font-size: 36px;
  display: block;
  margin: 0 auto 10px;
  color: #b6bcc7;
}
.drop-zone.is-dragover .drop-icon {
  color: var(--el-color-primary);
}

.el-upload-dragger {
  border-radius: 12px !important;
  border: 1.5px dashed #dde1e8;
  transition: border-color 0.2s, background-color 0.2s;
}
.el-upload-dragger:hover,
.el-upload-dragger.is-dragover {
  border-color: var(--el-color-primary);
  background: var(--hpgc-primary-soft);
}

/* ========================
   Empty State
   ======================== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 20px;
  color: #9ca3af;
}
.empty-state .empty-icon {
  font-size: 44px;
  margin-bottom: 12px;
  opacity: 0.45;
}
.empty-state p {
  margin: 0 0 4px;
  font-size: 14px;
}

/* ========================
   CCF Tag Colors
   ======================== */
.tag-ccf-a {
  background: var(--hpgc-ccf-a-bg) !important;
  color: var(--hpgc-ccf-a) !important;
  border: 1px solid #f6dcda !important;
}
.tag-ccf-b {
  background: var(--hpgc-ccf-b-bg) !important;
  color: var(--hpgc-ccf-b) !important;
  border: 1px solid #f7e4d0 !important;
}
.tag-ccf-c {
  background: var(--hpgc-ccf-c-bg) !important;
  color: var(--hpgc-ccf-c) !important;
  border: 1px solid #d8e6f3 !important;
}

/* ========================
   Status Tag Colors
   ======================== */
.tag-status-active {
  background: var(--hpgc-status-active-bg) !important;
  color: var(--hpgc-status-active) !important;
  border: 1px solid #cdf0e1 !important;
}
.tag-status-graduated {
  background: var(--hpgc-status-graduated-bg) !important;
  color: var(--hpgc-status-graduated) !important;
  border: 1px solid #e4e6ea !important;
}
.tag-status-pending {
  background: var(--hpgc-status-pending-bg) !important;
  color: var(--hpgc-status-pending) !important;
  border: 1px solid #f9e7c6 !important;
}

/* ========================
   移动端兼容
   ======================== */
@media (max-width: 900px) {
  /* 弹窗/抽屉改为近全屏（覆盖组件内联宽度） */
  .el-dialog {
    width: calc(100vw - 24px) !important;
    margin: 8vh auto !important;
  }
  .el-drawer {
    width: 94vw !important;
    min-width: 0 !important;
  }
  /* 工具栏纵向堆叠 */
  .toolbar,
  .toolbar-actions {
    width: 100%;
  }
  .toolbar-actions {
    margin-left: 0;
  }
  .el-form--inline .el-form-item {
    display: block;
    width: 100%;
    margin-right: 0;
    margin-bottom: 10px;
  }
  .el-form--inline .el-form-item__content {
    flex-wrap: wrap;
    gap: 6px;
  }
  .el-card__body {
    padding: 12px;
  }
  .el-main {
    padding: 10px;
  }
  .el-message-box {
    width: calc(100vw - 32px) !important;
  }
}
</style>
