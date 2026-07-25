<script setup lang="ts">
import { computed, watch, type CSSProperties } from 'vue'
import { useBuilderPreview } from '../../composables/useBuilderPreview'
import type {
  BuilderPreviewScreen,
} from '../../types/builder-preview'
import type { InvitationScreenEditForm } from '../../types/screen'
import type { BuilderStepNumber } from '../../utils/builder'
import {
  BUILDER_PREVIEW_ACTIVITIES,
  BUILDER_PREVIEW_DATES,
  BUILDER_PREVIEW_DEVICES,
  BUILDER_PREVIEW_SCREEN_DEFINITIONS,
  getBuilderPreviewDevice,
  getBuilderPreviewScreenDefinition,
} from '../../utils/builderPreview'
import {
  getInvitationImageByKey,
  resolveInvitationImageUrl,
} from '../../utils/invitationImages'

const props = defineProps<{
  authorName: string
  builderStep: BuilderStepNumber
  message: string
  recipientName: string
  screens: Record<BuilderPreviewScreen, InvitationScreenEditForm>
}>()

const config = useRuntimeConfig()
const preview = useBuilderPreview(props.builderStep)
const device = computed(() => getBuilderPreviewDevice(preview.deviceId.value))
const activeDefinition = computed(() => (
  getBuilderPreviewScreenDefinition(preview.activeScreen.value)
))
const activeScreenConfig = computed(() => props.screens[preview.activeScreen.value])
const activeImage = computed(() => (
  getInvitationImageByKey(activeScreenConfig.value.image_key)
))
const activeImageUrl = computed(() => (
  activeImage.value
    ? resolveInvitationImageUrl(activeImage.value.assetPath, config.app.baseURL)
    : '/images/envelope-heart.svg'
))
const deviceStyle = computed<CSSProperties>(() => ({
  width: `${device.value.width}px`,
}))
const noButtonStyle = computed<CSSProperties>(() => ({
  transform: `translate3d(${preview.noButtonTransform.value.x}px, ${preview.noButtonTransform.value.y}px, 0) scale(${preview.noButtonTransform.value.scale})`,
}))
const screenStatus = computed(() => `Предпросмотр: ${activeDefinition.value.label}`)

watch(
  () => props.builderStep,
  step => preview.syncToBuilderStep(step),
)

function selectScreen(screen: BuilderPreviewScreen): void {
  preview.selectScreen(screen)
}

function handleNoPointerEnter(event: PointerEvent): void {
  if (event.pointerType === 'mouse') {
    preview.runAwayNoButton()
  }
}

function handleNoPointerDown(event: PointerEvent): void {
  if (event.pointerType !== 'mouse') {
    preview.runAwayNoButton()
  }
}

function handleNoClick(event: MouseEvent): void {
  if (event.detail === 0) {
    preview.runAwayNoButton()
  }
}
</script>

<template>
  <aside class="builder-mobile-preview" aria-labelledby="builder-mobile-preview-title">
    <header class="builder-mobile-preview__heading">
      <div>
        <p>Интерактивный предпросмотр</p>
        <h3 id="builder-mobile-preview-title">Пройди приглашение как получатель</h3>
        <span>Демонстрационные дата и активность не сохраняются на сервере.</span>
      </div>
      <button type="button" class="builder-mobile-preview__reset" @click="preview.reset">
        Сбросить
      </button>
    </header>

    <div class="builder-mobile-preview__screen-switcher" role="group" aria-label="Экраны приглашения">
      <button
        v-for="definition in BUILDER_PREVIEW_SCREEN_DEFINITIONS"
        :key="definition.screen"
        type="button"
        :aria-pressed="preview.activeScreen.value === definition.screen"
        :aria-current="preview.activeScreen.value === definition.screen ? 'true' : undefined"
        :class="{
          'builder-mobile-preview__screen-button--active': preview.activeScreen.value === definition.screen,
        }"
        @click="selectScreen(definition.screen)"
      >
        <span aria-hidden="true">{{ definition.icon }}</span>
        <strong>{{ definition.label }}</strong>
      </button>
    </div>

    <fieldset class="builder-mobile-preview__devices">
      <legend>Размер телефона</legend>
      <button
        v-for="item in BUILDER_PREVIEW_DEVICES"
        :key="item.id"
        type="button"
        :aria-pressed="preview.deviceId.value === item.id"
        :class="{
          'builder-mobile-preview__device-button--active': preview.deviceId.value === item.id,
        }"
        @click="preview.deviceId.value = item.id"
      >
        {{ item.label }}
        <small>{{ item.width }} px</small>
      </button>
    </fieldset>

    <p class="sr-only" aria-live="polite">{{ screenStatus }}</p>

    <div class="builder-mobile-preview__viewport">
      <div class="builder-mobile-preview__phone" :style="deviceStyle">
        <div class="builder-mobile-preview__speaker" aria-hidden="true" />
        <section
          class="builder-mobile-preview__panel"
          role="region"
          :aria-label="activeDefinition.label"
        >
          <div class="builder-mobile-preview__image">
            <img
              :src="activeImageUrl"
              :alt="activeImage?.altText ?? ''"
              width="640"
              height="420"
            >
          </div>

          <div
            v-if="preview.activeScreen.value === 'invitation'"
            class="builder-mobile-preview__content builder-mobile-preview__content--invitation"
          >
            <p class="builder-mobile-preview__eyebrow">Для тебя с любовью</p>
            <h4>{{ activeScreenConfig.title || 'Ты пойдёшь со мной на свидание?' }}</h4>
            <p v-if="activeScreenConfig.subtitle" class="builder-mobile-preview__subtitle">
              {{ activeScreenConfig.subtitle }}
            </p>
            <p v-if="message.trim()" class="builder-mobile-preview__message">
              {{ message.trim() }}
            </p>
            <p v-if="authorName.trim()" class="builder-mobile-preview__signature">
              — {{ authorName.trim() }}
            </p>
            <div class="builder-mobile-preview__invitation-actions">
              <button
                type="button"
                class="builder-mobile-preview__yes-button"
                @click="selectScreen('acceptance')"
              >
                ♥ {{ activeScreenConfig.button_text || 'Да!' }}
              </button>
              <button
                type="button"
                class="builder-mobile-preview__no-button"
                :style="noButtonStyle"
                :aria-describedby="preview.noButtonLimitReached.value
                  ? 'builder-preview-no-help'
                  : undefined"
                @pointerenter="handleNoPointerEnter"
                @pointerdown="handleNoPointerDown"
                @click="handleNoClick"
              >
                {{ activeScreenConfig.secondary_button_text || 'Нет' }}
              </button>
            </div>
            <p
              v-if="preview.noButtonLimitReached.value"
              id="builder-preview-no-help"
              class="builder-mobile-preview__demo-note"
              role="status"
            >
              В настоящем приглашении отказ всё равно останется доступным.
            </p>
          </div>

          <div
            v-else-if="preview.activeScreen.value === 'acceptance'"
            class="builder-mobile-preview__content builder-mobile-preview__content--centered"
          >
            <p class="builder-mobile-preview__result-icon" aria-hidden="true">💘</p>
            <h4>{{ activeScreenConfig.title || 'Ура, договорились!' }}</h4>
            <p class="builder-mobile-preview__subtitle">
              {{ activeScreenConfig.subtitle || `Теперь ${recipientName || 'получатель'} может выбрать подходящий вариант.` }}
            </p>
            <button
              type="button"
              class="builder-mobile-preview__primary-button"
              @click="selectScreen('date_selection')"
            >
              {{ activeScreenConfig.button_text || 'Перейти к планированию' }}
            </button>
          </div>

          <div
            v-else-if="preview.activeScreen.value === 'date_selection'"
            class="builder-mobile-preview__content"
          >
            <p class="builder-mobile-preview__eyebrow">Демонстрационные варианты</p>
            <h4>{{ activeScreenConfig.title || 'Когда тебе будет удобно?' }}</h4>
            <p v-if="activeScreenConfig.subtitle" class="builder-mobile-preview__subtitle">
              {{ activeScreenConfig.subtitle }}
            </p>
            <div class="builder-mobile-preview__options" aria-label="Пример вариантов даты">
              <button
                v-for="option in BUILDER_PREVIEW_DATES"
                :key="option.id"
                type="button"
                :aria-pressed="preview.selectedDateId.value === option.id"
                :class="{
                  'builder-mobile-preview__option--selected': preview.selectedDateId.value === option.id,
                }"
                @click="preview.selectedDateId.value = option.id"
              >
                <strong>{{ option.label }}</strong>
                <span>{{ option.description }}</span>
              </button>
            </div>
            <button
              type="button"
              class="builder-mobile-preview__primary-button"
              @click="selectScreen('activity_selection')"
            >
              {{ activeScreenConfig.button_text || 'Выбрать дату' }}
            </button>
          </div>

          <div
            v-else-if="preview.activeScreen.value === 'activity_selection'"
            class="builder-mobile-preview__content"
          >
            <p class="builder-mobile-preview__eyebrow">Демонстрационные идеи</p>
            <h4>{{ activeScreenConfig.title || 'Чем займёмся?' }}</h4>
            <p v-if="activeScreenConfig.subtitle" class="builder-mobile-preview__subtitle">
              {{ activeScreenConfig.subtitle }}
            </p>
            <div class="builder-mobile-preview__options" aria-label="Пример вариантов активности">
              <button
                v-for="option in BUILDER_PREVIEW_ACTIVITIES"
                :key="option.id"
                type="button"
                :aria-pressed="preview.selectedActivityId.value === option.id"
                :class="{
                  'builder-mobile-preview__option--selected': preview.selectedActivityId.value === option.id,
                }"
                @click="preview.selectedActivityId.value = option.id"
              >
                <strong>{{ option.label }}</strong>
                <span>{{ option.description }}</span>
              </button>
            </div>
            <button
              type="button"
              class="builder-mobile-preview__primary-button"
              @click="selectScreen('final')"
            >
              {{ activeScreenConfig.button_text || 'Выбрать активность' }}
            </button>
          </div>

          <div
            v-else
            class="builder-mobile-preview__content builder-mobile-preview__content--centered"
          >
            <p class="builder-mobile-preview__result-icon" aria-hidden="true">💞</p>
            <h4>{{ activeScreenConfig.title || 'Тогда договорились!' }}</h4>
            <p class="builder-mobile-preview__subtitle">
              {{ activeScreenConfig.subtitle || 'Ваш примерный план уже собран.' }}
            </p>
            <dl class="builder-mobile-preview__plan">
              <div>
                <dt>Дата</dt>
                <dd>{{ preview.selectedDate.value.label }}</dd>
              </div>
              <div>
                <dt>Место</dt>
                <dd>{{ preview.selectedDate.value.description }}</dd>
              </div>
              <div>
                <dt>План</dt>
                <dd>{{ preview.selectedActivity.value.label }}</dd>
              </div>
            </dl>
            <button
              type="button"
              class="builder-mobile-preview__primary-button"
              @click="preview.reset"
            >
              Посмотреть сначала
            </button>
          </div>
        </section>
        <div class="builder-mobile-preview__home" aria-hidden="true" />
      </div>
    </div>

    <footer class="builder-mobile-preview__navigation" aria-label="Навигация внутри предпросмотра">
      <button
        type="button"
        :disabled="preview.previousScreen.value === null"
        @click="preview.goBack"
      >
        ← Предыдущий экран
      </button>
      <span>{{ activeDefinition.label }}</span>
      <button
        type="button"
        :disabled="preview.nextScreen.value === null"
        @click="preview.goForward"
      >
        Следующий экран →
      </button>
    </footer>
  </aside>
</template>
