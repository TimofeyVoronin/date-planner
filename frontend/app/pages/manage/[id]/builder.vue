<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { useInvitationsApi } from '../../../../composables/useInvitationsApi'
import { useManagementToken } from '../../../../composables/useManagementToken'
import type { InvitationRecord } from '../../../../types/invitation'
import {
  BUILDER_STEPS,
  builderStepSessionKey,
  getBuilderAccessBlock,
  getBuilderStepDefinition,
  getNextBuilderStep,
  getPreviousBuilderStep,
  parseBuilderStep,
  resolveBuilderStep,
  type BuilderAccessBlock,
  type BuilderStepNumber,
} from '../../../../utils/builder'
import { isInvitationId, parseInvitationApiError } from '../../../../utils/invitations'

type BuilderPageState = 'blocked' | 'error' | 'loading' | 'missing-token' | 'ready'

const route = useRoute()
const router = useRouter()
const api = useInvitationsApi()
const pageState = ref<BuilderPageState>('loading')
const invitation = ref<InvitationRecord | null>(null)
const currentStep = ref<BuilderStepNumber>(1)
const accessBlock = ref<BuilderAccessBlock | null>(null)
const errorMessage = ref('')
const canRetry = ref(true)
const hasUnsavedBuilderChanges = ref(false)
const isStepNavigationReady = ref(false)
const invitationId = computed(() => typeof route.params.id === 'string' ? route.params.id : '')
const managementPath = computed(() => `/manage/${encodeURIComponent(invitationId.value)}`)
const { clearManagementToken, takeManagementToken } = useManagementToken(invitationId)
const activeStep = computed(() => getBuilderStepDefinition(currentStep.value))
const previousStep = computed(() => getPreviousBuilderStep(currentStep.value))
const nextStep = computed(() => getNextBuilderStep(currentStep.value))
const blockedPresentation = computed(() => {
  if (accessBlock.value === 'quick-mode') {
    return {
      icon: '⚡',
      title: 'Для быстрого приглашения конструктор не нужен',
      description: 'Переключи приглашение в расширенный режим на странице управления, затем вернись сюда.',
      action: 'Открыть настройки приглашения',
    }
  }

  return {
    icon: '💌',
    title: 'Опубликованное приглашение уже закрыто для конструктора',
    description: 'Сейчас конструктор доступен только расширенному черновику до публикации.',
    action: 'Вернуться к управлению',
  }
})

useHead({
  title: 'Конструктор приглашения — Date Planner',
  meta: [
    { name: 'robots', content: 'noindex,nofollow' },
    { name: 'referrer', content: 'no-referrer' },
  ],
})

function readStoredStep(): string | null {
  try {
    return window.sessionStorage.getItem(builderStepSessionKey(invitationId.value))
  }
  catch {
    return null
  }
}

function persistStep(step: BuilderStepNumber): void {
  try {
    window.sessionStorage.setItem(builderStepSessionKey(invitationId.value), String(step))
  }
  catch {
    // The URL still preserves the active step when session storage is unavailable.
  }
}

async function replaceStepQuery(step: BuilderStepNumber): Promise<void> {
  await router.replace({
    query: {
      ...route.query,
      step: String(step),
    },
  })
}

async function restoreStepNavigation(): Promise<void> {
  const queryStep = parseBuilderStep(route.query.step)
  const resolvedStep = resolveBuilderStep(route.query.step, readStoredStep())

  currentStep.value = resolvedStep
  persistStep(resolvedStep)

  if (queryStep !== resolvedStep || route.query.step !== String(resolvedStep)) {
    await replaceStepQuery(resolvedStep)
  }

  isStepNavigationReady.value = true
}

async function goToStep(step: BuilderStepNumber): Promise<void> {
  if (step === currentStep.value) {
    return
  }

  currentStep.value = step
  persistStep(step)
  await replaceStepQuery(step)
}

function goToPreviousStep(): void {
  if (previousStep.value) {
    void goToStep(previousStep.value)
  }
}

function goToNextStep(): void {
  if (nextStep.value) {
    void goToStep(nextStep.value)
  }
}

async function loadBuilder(): Promise<void> {
  pageState.value = 'loading'
  errorMessage.value = ''
  canRetry.value = true
  invitation.value = null
  accessBlock.value = null

  if (!isInvitationId(invitationId.value)) {
    errorMessage.value = 'Проверь адрес секретной ссылки.'
    pageState.value = 'error'
    return
  }

  const token = takeManagementToken()

  if (!token) {
    pageState.value = 'missing-token'
    return
  }

  try {
    const nextInvitation = await api.getManagedInvitation(invitationId.value, token)
    const block = getBuilderAccessBlock(nextInvitation)

    invitation.value = nextInvitation
    accessBlock.value = block
    pageState.value = block ? 'blocked' : 'ready'
  }
  catch (error: unknown) {
    const parsedError = parseInvitationApiError(error)

    if (parsedError.status === 401 || parsedError.status === 403) {
      clearManagementToken()
      canRetry.value = false
    }

    errorMessage.value = parsedError.message
    pageState.value = 'error'
  }
}

function warnBeforeUnload(event: BeforeUnloadEvent): void {
  if (!hasUnsavedBuilderChanges.value) {
    return
  }

  event.preventDefault()
  event.returnValue = ''
}

watch(
  () => route.query.step,
  (value) => {
    if (!isStepNavigationReady.value) {
      return
    }

    const parsedStep = parseBuilderStep(value)

    if (parsedStep) {
      currentStep.value = parsedStep
      persistStep(parsedStep)
      return
    }

    void replaceStepQuery(currentStep.value)
  },
)

onBeforeRouteLeave(() => {
  if (!hasUnsavedBuilderChanges.value) {
    return true
  }

  return window.confirm('Есть несохранённые изменения конструктора. Покинуть страницу?')
})

onMounted(async () => {
  window.addEventListener('beforeunload', warnBeforeUnload)
  await restoreStepNavigation()
  await loadBuilder()
})

onUnmounted(() => {
  window.removeEventListener('beforeunload', warnBeforeUnload)
})
</script>

<template>
  <main class="detail-page detail-page--builder">
    <section class="builder-shell" aria-labelledby="builder-page-title">
      <div class="builder-shell__topbar">
        <NuxtLink class="brand-link" to="/" aria-label="Date Planner, перейти на главную">
          <img src="/images/envelope-heart.svg" alt="" width="46" height="40">
          <span>Date Planner</span>
        </NuxtLink>
        <NuxtLink class="builder-shell__manage-link" :to="managementPath">
          ← К управлению
        </NuxtLink>
      </div>

      <div v-if="pageState === 'loading'" class="state-card" role="status" aria-live="polite">
        <span class="state-card__icon state-card__icon--loading" aria-hidden="true">♥</span>
        <h1 id="builder-page-title">Открываем конструктор…</h1>
        <p>Проверяем черновик и секретный доступ автора.</p>
      </div>

      <div v-else-if="pageState === 'missing-token'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔑</span>
        <h1 id="builder-page-title">В этой вкладке нет секретного ключа</h1>
        <p>
          Сначала открой полную секретную ссылку автора. После этого перейти в конструктор можно со
          страницы управления.
        </p>
        <NuxtLink to="/">Вернуться на главную</NuxtLink>
      </div>

      <div v-else-if="pageState === 'error'" class="state-card" role="alert">
        <span class="state-card__icon" aria-hidden="true">🔐</span>
        <h1 id="builder-page-title">Конструктор недоступен</h1>
        <p>{{ errorMessage }}</p>
        <div class="state-card__actions">
          <button v-if="canRetry" type="button" @click="loadBuilder">
            Попробовать снова
          </button>
          <NuxtLink to="/">На главную</NuxtLink>
        </div>
      </div>

      <div v-else-if="pageState === 'blocked'" class="state-card" role="status">
        <span class="state-card__icon" aria-hidden="true">{{ blockedPresentation.icon }}</span>
        <h1 id="builder-page-title">{{ blockedPresentation.title }}</h1>
        <p>{{ blockedPresentation.description }}</p>
        <NuxtLink :to="managementPath">{{ blockedPresentation.action }}</NuxtLink>
      </div>

      <template v-else-if="invitation">
        <header class="builder-shell__heading">
          <p>Расширенный черновик</p>
          <h1 id="builder-page-title">Конструктор приглашения</h1>
          <span>
            {{ invitation.author_name }}, настрой сценарий для {{ invitation.recipient_name }}.
            Текущий шаг сохраняется в этой вкладке.
          </span>
        </header>

        <nav class="builder-progress" aria-label="Шаги конструктора">
          <ol>
            <li
              v-for="step in BUILDER_STEPS"
              :key="step.id"
              :class="{
                'builder-progress__item--active': step.number === currentStep,
                'builder-progress__item--visited': step.number < currentStep,
              }"
            >
              <button
                type="button"
                :aria-current="step.number === currentStep ? 'step' : undefined"
                :aria-label="`Шаг ${step.number}: ${step.label}`"
                @click="goToStep(step.number)"
              >
                <span aria-hidden="true">{{ step.number }}</span>
                <strong>{{ step.label }}</strong>
              </button>
            </li>
          </ol>
        </nav>

        <article class="builder-stage" :aria-labelledby="`builder-step-${activeStep.id}`">
          <div class="builder-stage__illustration" aria-hidden="true">
            {{ activeStep.icon }}
          </div>
          <div class="builder-stage__copy">
            <p>Шаг {{ currentStep }} из {{ BUILDER_STEPS.length }}</p>
            <h2 :id="`builder-step-${activeStep.id}`">{{ activeStep.label }}</h2>
            <span>{{ activeStep.description }}</span>
          </div>

          <section class="builder-stage__placeholder" aria-label="Содержимое будущего шага">
            <p>Каркас шага готов</p>
            <h3>Что появится здесь в следующих задачах</h3>
            <ul>
              <li v-for="feature in activeStep.plannedFeatures" :key="feature">
                <span aria-hidden="true">✓</span>
                {{ feature }}
              </li>
            </ul>
            <p class="builder-stage__notice">
              Сейчас шаги отвечают за безопасную навигацию и восстановление позиции. Поля и
              автосохранение будут подключаться отдельными проверяемыми итерациями.
            </p>
          </section>
        </article>

        <footer class="builder-actions" aria-label="Навигация по конструктору">
          <button
            type="button"
            class="builder-actions__secondary"
            :disabled="previousStep === null"
            @click="goToPreviousStep"
          >
            ← Назад
          </button>
          <div class="builder-actions__status" role="status" aria-live="polite">
            <strong>Шаг {{ currentStep }} из {{ BUILDER_STEPS.length }}</strong>
            <span>Позиция сохранена</span>
          </div>
          <button
            v-if="nextStep"
            type="button"
            class="builder-actions__primary"
            @click="goToNextStep"
          >
            Далее →
          </button>
          <NuxtLink v-else class="builder-actions__primary" :to="managementPath">
            Завершить обзор
          </NuxtLink>
        </footer>
      </template>
    </section>
  </main>
</template>
