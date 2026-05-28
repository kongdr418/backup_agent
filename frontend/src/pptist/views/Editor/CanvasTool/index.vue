<template>
  <div class="canvas-tool">
    <div class="left-handler">
      <span class="handler-item" :class="{ 'disable': !canUndo }" v-tooltip="tr('pptist.undo')" @click="undo()">
        <Undo2 :size="16" />
      </span>
      <span class="handler-item" :class="{ 'disable': !canRedo }" v-tooltip="tr('pptist.redo')" @click="redo()">
        <Redo2 :size="16" />
      </span>
      <div class="more">
        <Divider type="vertical" style="height: 20px;" />
        <Popover class="more-icon" trigger="click" v-model:value="moreVisible" :offset="10">
          <template #content>
            <PopoverMenuItem class="popover-menu-item" center @click="toggleNotesPanel(); moreVisible = false"><MessageSquare :size="16" class="icon" />{{ tr('pptist.comments') }}</PopoverMenuItem>
            <PopoverMenuItem class="popover-menu-item" center @click="toggleSelectPanel(); moreVisible = false"><Layers :size="16" class="icon" />{{ tr('pptist.selectionPane') }}</PopoverMenuItem>
            <PopoverMenuItem class="popover-menu-item" center @click="toggleSraechPanel(); moreVisible = false"><Search :size="16" class="icon" />{{ tr('pptist.searchReplace') }}</PopoverMenuItem>
          </template>
          <span class="handler-item">
            <MoreHorizontal :size="16" />
          </span>
        </Popover>
        <span class="handler-item" :class="{ 'active': showNotesPanel }" v-tooltip="tr('pptist.comments')" @click="toggleNotesPanel()">
          <MessageSquare :size="16" />
        </span>
        <span class="handler-item" :class="{ 'active': showSelectPanel }" v-tooltip="tr('pptist.selectionPane')" @click="toggleSelectPanel()">
          <Layers :size="16" />
        </span>
        <span class="handler-item" :class="{ 'active': showSearchPanel }" v-tooltip="tr('pptist.searchReplace')" @click="toggleSraechPanel()">
          <Search :size="16" />
        </span>
      </div>
    </div>

    <div class="add-element-handler">
      <div class="insert-handler-item group-btn" :class="{ 'active': creatingElement?.type === 'text' }" v-tooltip="tr('pptist.insertText')">
        <div class="group-btn-main" @click="drawText()"><Type :size="16" class="icon" /> <span class="text">{{ tr('pptist.textbox') }}</span></div>
        <Popover trigger="click" v-model:value="textTypeSelectVisible" style="height: 100%;" :offset="10">
          <template #content>
            <PopoverMenuItem center @click="() => { drawText(); textTypeSelectVisible = false }"><Type :size="16" class="icon" /> {{ tr('pptist.horizontalText') }}</PopoverMenuItem>
            <PopoverMenuItem center @click="() => { drawText(true); textTypeSelectVisible = false }"><CaseSensitive :size="16" class="icon" /> {{ tr('pptist.verticalText') }}</PopoverMenuItem>
          </template>
          <span class="arrow"><ChevronDown :size="12" /></span>
        </Popover>
      </div>
      <div class="insert-handler-item group-btn" :class="{ 'active': creatingCustomShape || creatingElement?.type === 'shape' }" v-tooltip="tr('pptist.insertShape')" :offset="10">
        <Popover trigger="click" style="height: 100%;" v-model:value="shapePoolVisible" :offset="10">
          <template #content>
            <ShapePool @select="shape => drawShape(shape)" />
          </template>
          <div class="group-btn-main"><Hexagon :size="16" class="icon" /> <span class="text">{{ tr('pptist.shape') }}</span></div>
        </Popover>
        <Popover trigger="click" v-model:value="shapeMenuVisible" style="height: 100%;" :offset="10">
          <template #content>
            <PopoverMenuItem center @click="shapeMenuVisible = false; shapePoolVisible = true"><Hexagon :size="16" class="icon" />{{ tr('pptist.presetShapes') }}</PopoverMenuItem>
            <PopoverMenuItem center @click="() => { drawCustomShape(); shapeMenuVisible = false }"><PenTool :size="16" class="icon" />{{ tr('pptist.freeDraw') }}</PopoverMenuItem>
          </template>
          <span class="arrow"><ChevronDown :size="12" /></span>
        </Popover>
      </div>
      <div class="insert-handler-item group-btn" v-tooltip="tr('pptist.insertImage')">
        <FileInput style="height: 100%;" @change="files => insertImageElement(files)">
          <div class="group-btn-main"><ImageIcon :size="16" class="icon" /> <span class="text">{{ tr('pptist.image') }}</span></div>
        </FileInput>
        <Popover trigger="click" v-model:value="imageMenuVisible" style="height: 100%;" :offset="10">
          <template #content>
            <FileInput @change="files => { insertImageElement(files); imageMenuVisible = false }">
              <PopoverMenuItem center><Upload :size="16" class="icon" /> {{ tr('pptist.uploadImage') }}</PopoverMenuItem>
            </FileInput>
            <PopoverMenuItem center @click="openImageLibPanel(); imageMenuVisible = false"><ImageIcon :size="16" class="icon" /> {{ tr('pptist.onlineGallery') }}</PopoverMenuItem>
          </template>
          <span class="arrow"><ChevronDown :size="12" /></span>
        </Popover>
      </div>
      <Popover trigger="click" v-model:value="linePoolVisible" :offset="10">
        <template #content>
          <LinePool @select="line => drawLine(line)" />
        </template>
        <div class="insert-handler-item" :class="{ 'active': creatingElement?.type === 'line' }" v-tooltip="tr('pptist.line')">
          <Minus :size="16" class="icon" /> <span class="text">{{ tr('pptist.line') }}</span>
        </div>
      </Popover>
      <Popover trigger="click" v-model:value="chartPoolVisible" :offset="10">
        <template #content>
          <ChartPool @select="chart => { createChartElement(chart); chartPoolVisible = false }" />
        </template>
        <div class="insert-handler-item" v-tooltip="tr('pptist.chart')">
          <BarChart3 :size="16" class="icon" /> <span class="text">{{ tr('pptist.chart') }}</span>
        </div>
      </Popover>
      <Popover trigger="click" v-model:value="tableGeneratorVisible" :offset="10">
        <template #content>
          <TableGenerator
            @close="tableGeneratorVisible = false"
            @insert="({ row, col }) => { createTableElement(row, col); tableGeneratorVisible = false }"
          />
        </template>
        <div class="insert-handler-item" v-tooltip="tr('pptist.table')">
          <Table2 :size="16" class="icon" /> <span class="text">{{ tr('pptist.table') }}</span>
        </div>
      </Popover>
      <div class="insert-handler-item" v-tooltip="tr('pptist.formula')" @click="latexEditorVisible = true">
        <Sigma :size="16" class="icon" /> <span class="text">{{ tr('pptist.formula') }}</span>
      </div>
      <Popover trigger="click" v-model:value="mediaInputVisible" :offset="10">
        <template #content>
          <MediaInput
            @close="mediaInputVisible = false"
            @insertVideo="({ src, ext }) => { createVideoElement(src, ext); mediaInputVisible = false }"
            @insertAudio="({ src, ext }) => { createAudioElement(src, ext); mediaInputVisible = false }"
          />
        </template>
        <div class="insert-handler-item" v-tooltip="tr('pptist.media')">
          <Video :size="16" class="icon" /> <span class="text">{{ tr('pptist.media') }}</span>
        </div>
      </Popover>
      <div class="insert-handler-item" :class="{ 'active': showSymbolPanel }" v-tooltip="tr('pptist.symbol')" @click="toggleSymbolPanel()">
        <Omega :size="16" class="icon" /> <span class="text">{{ tr('pptist.symbol') }}</span>
      </div>
    </div>

    <div class="right-handler">
      <span class="handler-item viewport-size" v-tooltip="tr('pptist.zoomOut')" @click="scaleCanvas('-')">
        <Minus :size="16" />
      </span>
      <Popover trigger="click" v-model:value="canvasScaleVisible">
        <template #content>
          <PopoverMenuItem
            center
            v-for="item in canvasScalePresetList"
            :key="item"
            @click="applyCanvasPresetScale(item)"
          >{{item}}%</PopoverMenuItem>
          <PopoverMenuItem center @click="resetCanvas(); canvasScaleVisible = false">适应屏幕</PopoverMenuItem>
        </template>
        <span class="text">{{ canvasScalePercentage }}</span>
      </Popover>
      <span class="handler-item viewport-size" v-tooltip="tr('pptist.zoomIn')" @click="scaleCanvas('+')">
        <Plus :size="16" />
      </span>
      <span class="handler-item viewport-size-adaptation" v-tooltip="tr('pptist.fitScreen')" @click="resetCanvas()">
        <Maximize :size="16" />
      </span>
    </div>

    <Modal
      v-model:visible="latexEditorVisible"
      :width="880"
    >
      <LaTeXEditor
        @close="latexEditorVisible = false"
        @update="data => { createLatexElement(data); latexEditorVisible = false }"
      />
    </Modal>
  </div>
</template>

<script lang="ts" setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useMainStore, useSnapshotStore } from '@pptist/store'
import { getImageDataURL } from '@pptist/utils/image'
import type { ShapePoolItem } from '@pptist/configs/shapes'
import type { LinePoolItem } from '@pptist/configs/lines'
import useScaleCanvas from '@pptist/hooks/useScaleCanvas'
import useHistorySnapshot from '@pptist/hooks/useHistorySnapshot'
import useCreateElement from '@pptist/hooks/useCreateElement'

import {
  Undo2, Redo2, MoreHorizontal, MessageSquare, Layers, Search,
  Type, CaseSensitive, ChevronDown, Hexagon, PenTool, ImageIcon,
  Upload, Minus, Plus, BarChart3, Table2, Sigma, Video, Omega, Maximize,
} from 'lucide-vue-next'

import ShapePool from './ShapePool.vue'
import LinePool from './LinePool.vue'
import ChartPool from './ChartPool.vue'
import TableGenerator from './TableGenerator.vue'
import MediaInput from './MediaInput.vue'
import LaTeXEditor from '@pptist/components/LaTeXEditor/index.vue'
import FileInput from '@pptist/components/FileInput.vue'
import Modal from '@pptist/components/Modal.vue'
import Divider from '@pptist/components/Divider.vue'
import Popover from '@pptist/components/Popover.vue'
import PopoverMenuItem from '@pptist/components/PopoverMenuItem.vue'
import { pptistT } from '@pptist/i18n'

const mainStore = useMainStore()
const { creatingElement, creatingCustomShape, showSelectPanel, showSearchPanel, showNotesPanel, showSymbolPanel } = storeToRefs(mainStore)
const { canUndo, canRedo } = storeToRefs(useSnapshotStore())

const { redo, undo } = useHistorySnapshot()

const {
  scaleCanvas,
  setCanvasScalePercentage,
  resetCanvas,
  canvasScalePercentage,
} = useScaleCanvas()

const canvasScalePresetList = [200, 150, 125, 100, 75, 50]
const canvasScaleVisible = ref(false)
const tr = pptistT

const applyCanvasPresetScale = (value: number) => {
  setCanvasScalePercentage(value)
  canvasScaleVisible.value = false
}

const {
  createImageElement,
  createChartElement,
  createTableElement,
  createLatexElement,
  createVideoElement,
  createAudioElement,
} = useCreateElement()

const insertImageElement = (files: FileList) => {
  const imageFile = files[0]
  if (!imageFile) return
  getImageDataURL(imageFile).then(dataURL => createImageElement(dataURL))
}

const shapePoolVisible = ref(false)
const linePoolVisible = ref(false)
const chartPoolVisible = ref(false)
const tableGeneratorVisible = ref(false)
const mediaInputVisible = ref(false)
const latexEditorVisible = ref(false)
const textTypeSelectVisible = ref(false)
const shapeMenuVisible = ref(false)
const imageMenuVisible = ref(false)
const moreVisible = ref(false)

const drawText = (vertical = false) => {
  mainStore.setCreatingElement({ type: 'text', vertical })
}

const drawShape = (shape: ShapePoolItem) => {
  mainStore.setCreatingElement({ type: 'shape', data: shape })
  shapePoolVisible.value = false
}

const drawCustomShape = () => {
  mainStore.setCreatingCustomShapeState(true)
  shapePoolVisible.value = false
}

const drawLine = (line: LinePoolItem) => {
  mainStore.setCreatingElement({ type: 'line', data: line })
  linePoolVisible.value = false
}

const toggleSelectPanel = () => {
  mainStore.setSelectPanelState(!showSelectPanel.value)
}

const toggleSraechPanel = () => {
  mainStore.setSearchPanelState(!showSearchPanel.value)
}

const toggleNotesPanel = () => {
  mainStore.setNotesPanelState(!showNotesPanel.value)
}

const toggleSymbolPanel = () => {
  mainStore.setSymbolPanelState(!showSymbolPanel.value)
}

const openImageLibPanel = () => {
  mainStore.setImageLibPanelState(true)
}
</script>

<style lang="scss" scoped>
.canvas-tool {
  position: relative;
  border-bottom: 1px solid $borderColor;
  background-color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 10px;
  font-size: 13px;
  user-select: none;
  min-height: 40px;
}
.left-handler, .more {
  display: flex;
  align-items: center;
}
.more-icon {
  display: none;
}
.popover-menu-item {
  display: flex;
  align-items: center;
  padding: 8px 10px;

  &.center {
    justify-content: center;
  }

  .icon {
    margin-right: 8px;
  }
}
.add-element-handler {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;

  & > div {
    flex-shrink: 0;
  }

  .insert-handler-item {
    height: 30px;
    font-size: 14px;
    margin: 0 2px;
    padding: 0 10px;
    display: flex;
    justify-content: center;
    align-items: center;
    border-radius: $borderRadius;
    overflow: hidden;
    cursor: pointer;

    &:not(.group-btn):hover {
      background-color: #f1f1f1;
    }

    &.active {
      background-color: #f1f1f1;
    }

    .icon {
      margin-right: 4px;
      flex-shrink: 0;
    }

    .text {
      white-space: nowrap;
    }

    &.group-btn {
      margin-right: 6px;
      padding: 0;

      &:hover {
        background-color: #f3f3f3;
      }

      .group-btn-main {
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 0 8px;
        gap: 4px;

        &:hover {
          background-color: #e9e9e9;
        }
      }

      .arrow {
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        padding: 0 2px;

        &:hover {
          background-color: #e9e9e9;
        }
      }
    }
  }
}
.handler-item {
  height: 30px;
  font-size: 14px;
  margin: 0 2px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: $borderRadius;
  overflow: hidden;
  cursor: pointer;

  &.disable {
    opacity: .5;
  }
}
.left-handler, .right-handler {
  .handler-item {
    padding: 0 8px;

    &.active,
    &:not(.disable):hover {
      background-color: #f1f1f1;
    }
  }
}
.right-handler {
  display: flex;
  align-items: center;

  .text {
    display: inline-block;
    width: 40px;
    text-align: center;
    cursor: pointer;
    font-size: 12px;
  }

  .viewport-size {
    font-size: 13px;
  }
}

/* 响应式：窄屏隐藏文字，保留图标 */
@media screen and (width <= 1500px) {
  .canvas-tool {
    gap: 6px;
    padding: 0 6px;
  }
  .left-handler,
  .right-handler {
    flex: 0 0 auto;
  }
  .add-element-handler {
    position: static;
    flex: 1 1 auto;
    min-width: 0;
    justify-content: center;
    overflow: hidden;
    transform: none;

    .insert-handler-item {
      margin: 0 1px;
      padding: 0 7px;
    }
  }
  .handler-item {
    margin: 0 1px;
  }
}

@media screen and (width <= 1200px) {
  .add-element-handler .insert-handler-item .text {
    display: none;
  }
  .right-handler .text {
    display: none;
  }
  .more > .handler-item {
    display: none;
  }
  .more-icon {
    display: block;
  }
}

/* 不再完全隐藏左右工具栏，保留图标 */
@media screen and (width <= 1000px) {
  .add-element-handler .insert-handler-item {
    padding: 0 5px;
    margin: 0;
  }
}
</style>
